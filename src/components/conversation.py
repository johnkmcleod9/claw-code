"""
Conversation history rendering.

Ports: components/ConversationView.tsx, components/MessageBlock.tsx,
       components/CompactSummary.tsx, components/AssistantMessage.tsx
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from .formatter import Color, style, dim, bold, gray, terminal_width, box, SINGLE
from .markdown import render_markdown
from .tool_result import render_tool_use, ToolResult, render_tool_result
from .cost_display import render_cost_inline, CostSummary


# ---------------------------------------------------------------------------
# Message data model
# ---------------------------------------------------------------------------

@dataclass
class Message:
    role: str                  # "user" | "assistant" | "system" | "tool"
    content: Any               # str | list[dict]
    tool_use_id: str = ""
    tool_name: str = ""
    is_error: bool = False
    metadata: dict = field(default_factory=dict)

    @property
    def text(self) -> str:
        if isinstance(self.content, str):
            return self.content
        if isinstance(self.content, list):
            parts = []
            for block in self.content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
            return "\n".join(parts)
        return str(self.content)


# ---------------------------------------------------------------------------
# Role display config
# ---------------------------------------------------------------------------

ROLE_CONFIG = {
    "user":      {"prefix": "❯", "color": Color.GREEN,   "label": "You"},
    "assistant": {"prefix": "◆", "color": Color.MAGENTA, "label": "Claude"},
    "system":    {"prefix": "⊞", "color": Color.GRAY,    "label": "System"},
    "tool":      {"prefix": "⬡", "color": Color.YELLOW,  "label": "Tool"},
}


def _role_prefix(role: str) -> str:
    cfg = ROLE_CONFIG.get(role, {"prefix": "·", "color": Color.WHITE, "label": role})
    return style(cfg["prefix"], cfg["color"], Color.BOLD)


def _role_label(role: str) -> str:
    cfg = ROLE_CONFIG.get(role, {"prefix": "·", "color": Color.WHITE, "label": role})
    return style(cfg["label"], cfg["color"])


# ---------------------------------------------------------------------------
# Individual message renderers
# ---------------------------------------------------------------------------

def render_message(
    msg: Message,
    width: int | None = None,
    markdown: bool = True,
    compact: bool = False,
) -> str:
    """Render a single conversation message."""
    w = width or terminal_width()
    role = msg.role

    prefix = _role_prefix(role)
    label = _role_label(role)

    # Tool use / tool result special cases
    if role == "tool":
        result = ToolResult(
            tool_name=msg.tool_name or "tool",
            tool_use_id=msg.tool_use_id,
            content=msg.content,
            is_error=msg.is_error,
        )
        return render_tool_result(result, width=w)

    text = msg.text

    if not text.strip():
        return f"{prefix} {label} {dim('(empty)')}"

    # Header line
    header = f"{prefix} {label}"

    if compact or len(text) < 100:
        # Single line or short message
        content = render_markdown(text, width=w - 4) if markdown and role == "assistant" else text
        if "\n" in content:
            indented = "\n".join("  " + l for l in content.splitlines())
            return f"{header}\n{indented}"
        return f"{header}  {content}"

    # Multi-line message with indented body
    content = render_markdown(text, width=w - 4) if markdown and role == "assistant" else text
    indented = "\n".join("  " + l for l in content.splitlines())
    return f"{header}\n{indented}"


# ---------------------------------------------------------------------------
# Full conversation view
# ---------------------------------------------------------------------------

def render_conversation(
    messages: Sequence[Message],
    width: int | None = None,
    markdown: bool = True,
    compact: bool = False,
    max_messages: int | None = None,
    cost_summary: CostSummary | None = None,
) -> str:
    """Render a full conversation history."""
    w = width or terminal_width()
    sep = dim("─" * w)

    msgs = list(messages)
    if max_messages is not None:
        msgs = msgs[-max_messages:]

    rendered = []
    for i, msg in enumerate(msgs):
        rendered.append(render_message(msg, width=w, markdown=markdown, compact=compact))
        if i < len(msgs) - 1 and not compact:
            rendered.append(sep)

    result = "\n".join(rendered)

    if cost_summary:
        result += "\n" + dim("─" * w) + "\n" + render_cost_inline(cost_summary)

    return result


# ---------------------------------------------------------------------------
# Compact summary block
# ---------------------------------------------------------------------------

def render_compact_summary(
    summary_text: str,
    original_message_count: int,
    width: int | None = None,
) -> str:
    """
    Render a compact conversation summary block.

    Ports: components/CompactSummary.tsx
    """
    w = width or terminal_width()
    icon = style("◇", Color.CYAN)
    label = bold(f" Conversation compacted")
    detail = dim(f" ({original_message_count} messages → summary)")

    inner = f"{icon}{label}{detail}\n\n{dim(summary_text)}"
    return box(inner, style_chars=SINGLE, width=w, color=Color.DIM)


# ---------------------------------------------------------------------------
# Thinking block display
# ---------------------------------------------------------------------------

def render_thinking(text: str, width: int | None = None, collapsed: bool = True) -> str:
    """
    Render extended thinking blocks.

    Ports: components/ThinkingBlock.tsx
    """
    w = width or terminal_width()
    icon = style("💭", Color.DIM)
    label = dim("Thinking…")

    if collapsed:
        preview = text[:80].replace("\n", " ")
        if len(text) > 80:
            preview += "…"
        return f"  {icon} {label}  {dim(preview)}"

    indented = "\n".join("  │ " + l for l in text.splitlines())
    return f"  {icon} {label}\n{dim(indented)}"


# ---------------------------------------------------------------------------
# System prompt display
# ---------------------------------------------------------------------------

def render_system_prompt(text: str, width: int | None = None, collapsed: bool = True) -> str:
    """Render the system prompt in a collapsible view."""
    w = width or terminal_width()
    icon = style("⊞", Color.GRAY)
    label = dim("System prompt")

    if collapsed:
        preview = text[:60].replace("\n", " ")
        if len(text) > 60:
            preview += "…"
        return f"  {icon} {label}  {dim(preview)}"

    content = dim(text)
    return box(content, title="System", width=w, color=Color.DIM)


# ---------------------------------------------------------------------------
# Agent turn summary (for agentic mode)
# ---------------------------------------------------------------------------

def render_agent_turn_summary(
    turn_num: int,
    tool_calls: int,
    cost_usd: float,
    elapsed_s: float,
    width: int | None = None,
) -> str:
    """Render a summary line for an agent turn."""
    w = width or terminal_width()
    sep = dim("─" * w)
    icon = style("◆", Color.MAGENTA)
    turn = dim(f"Turn {turn_num}")
    tools = dim(f"{tool_calls} tool calls")
    cost = dim(f"${cost_usd:.4f}")
    elapsed = dim(f"{elapsed_s:.1f}s")
    return f"{sep}\n  {icon} {turn}  {tools}  {cost}  {elapsed}"


__all__ = [
    "Message",
    "ROLE_CONFIG",
    "render_message",
    "render_conversation",
    "render_compact_summary",
    "render_thinking",
    "render_system_prompt",
    "render_agent_turn_summary",
]
