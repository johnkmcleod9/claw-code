"""
Tool result rendering for terminal output.

Ports: components/ToolResult.tsx, components/ToolResultBlock.tsx,
       components/BashToolResult.tsx, components/FileToolResult.tsx,
       components/AssistantMessage.tsx (tool_use blocks)
"""
from __future__ import annotations

import json
import textwrap
from dataclasses import dataclass, field
from typing import Any

from .formatter import (
    Color, style, bold, dim, green, red, yellow, cyan, gray,
    box, ROUND, terminal_width, wrap, truncate,
)


# ---------------------------------------------------------------------------
# Tool result data model
# ---------------------------------------------------------------------------

@dataclass
class ToolResult:
    """Unified tool result container."""
    tool_name: str
    tool_use_id: str = ""
    content: Any = None          # str | list[dict] | dict
    is_error: bool = False
    elapsed_ms: float | None = None
    metadata: dict = field(default_factory=dict)

    @property
    def text_content(self) -> str:
        """Extract plain text from content."""
        if isinstance(self.content, str):
            return self.content
        if isinstance(self.content, list):
            parts = []
            for block in self.content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(block.get("text", ""))
                    elif block.get("type") == "image":
                        parts.append(f"[image: {block.get('source', {}).get('url', 'embedded')}]")
                else:
                    parts.append(str(block))
            return "\n".join(parts)
        if isinstance(self.content, dict):
            return json.dumps(self.content, indent=2)
        return str(self.content) if self.content is not None else ""


# ---------------------------------------------------------------------------
# Tool name → icon / color mapping
# ---------------------------------------------------------------------------

TOOL_ICONS: dict[str, str] = {
    "bash":            "⬡",
    "computer":        "⊞",
    "edit":            "✎",
    "list_files":      "⊟",
    "read_file":       "⊞",
    "write_file":      "⊟",
    "search":          "⊕",
    "grep":            "⊕",
    "glob":            "⊕",
    "find":            "⊕",
    "web_search":      "🌐",
    "web_fetch":       "🌐",
    "browser":         "🌐",
    "task":            "⊞",
    "memory":          "⊟",
    "todo":            "⊟",
    "mcp":             "⊞",
}

TOOL_COLORS: dict[str, Color] = {
    "bash":        Color.YELLOW,
    "computer":    Color.MAGENTA,
    "edit":        Color.BLUE,
    "write_file":  Color.BLUE,
    "read_file":   Color.CYAN,
    "list_files":  Color.CYAN,
    "search":      Color.GREEN,
    "grep":        Color.GREEN,
    "web_search":  Color.BRIGHT_BLUE,
    "web_fetch":   Color.BRIGHT_BLUE,
}


def _tool_icon(name: str) -> str:
    return TOOL_ICONS.get(name.lower(), "⬡")


def _tool_color(name: str) -> Color:
    return TOOL_COLORS.get(name.lower(), Color.CYAN)


# ---------------------------------------------------------------------------
# Tool use header (before execution)
# ---------------------------------------------------------------------------

def render_tool_use(
    tool_name: str,
    input_data: dict | str | None = None,
    tool_use_id: str = "",
    compact: bool = False,
) -> str:
    """Render the 'about to call tool' header."""
    color = _tool_color(tool_name)
    icon = style(_tool_icon(tool_name), color)
    name_str = style(tool_name, color, Color.BOLD)

    if compact:
        return f"{icon} {name_str}"

    lines = [f"{icon} {name_str}"]

    if input_data:
        if isinstance(input_data, str):
            preview = truncate(input_data, 120)
            lines.append(dim(f"  › {preview}"))
        elif isinstance(input_data, dict):
            # Show key inputs concisely
            for k, v in list(input_data.items())[:4]:
                v_str = truncate(str(v).replace("\n", "↵"), 80)
                lines.append(dim(f"  {k}: {v_str}"))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Bash result renderer
# ---------------------------------------------------------------------------

def _render_bash_result(result: ToolResult, max_lines: int = 50, width: int | None = None) -> str:
    w = width or terminal_width()
    text = result.text_content
    lines = text.splitlines()

    color = Color.RED if result.is_error else Color.GREEN
    icon = style("✗" if result.is_error else "✓", color)

    elapsed = ""
    if result.elapsed_ms is not None:
        elapsed = style(f" ({result.elapsed_ms/1000:.2f}s)", Color.DIM)

    header = f"{icon} bash{elapsed}"

    if not text.strip():
        return f"{header} {dim('(no output)')}"

    if len(lines) > max_lines:
        shown = lines[:max_lines]
        hidden = len(lines) - max_lines
        body = "\n".join(shown) + f"\n{dim(f'… {hidden} more lines')}"
    else:
        body = text

    # Indent output
    indented = "\n".join("  " + l for l in body.splitlines())
    return f"{header}\n{dim(indented)}"


# ---------------------------------------------------------------------------
# File result renderer
# ---------------------------------------------------------------------------

def _render_file_result(result: ToolResult, max_lines: int = 30) -> str:
    text = result.text_content
    lines = text.splitlines()

    path = result.metadata.get("path", "")
    path_str = style(path, Color.CYAN) if path else ""

    if result.is_error:
        return f"{style('✗', Color.RED)} {result.tool_name} {path_str}\n  {red(text)}"

    if not text.strip():
        return f"{style('○', Color.DIM)} {result.tool_name} {path_str} {dim('(empty)')}"

    header = f"{style('✓', Color.GREEN)} {style(result.tool_name, Color.BOLD)} {path_str}"

    if len(lines) > max_lines:
        shown = "\n".join(lines[:max_lines])
        hidden = len(lines) - max_lines
        body = shown + f"\n{dim(f'… {hidden} more lines')}"
    else:
        body = text

    indented = "\n".join("  " + l for l in body.splitlines())
    return f"{header}\n{dim(indented)}"


# ---------------------------------------------------------------------------
# Generic / JSON result renderer
# ---------------------------------------------------------------------------

def _render_json_result(result: ToolResult) -> str:
    color = _tool_color(result.tool_name)
    icon = style(_tool_icon(result.tool_name), color)
    name_str = style(result.tool_name, color, Color.BOLD)

    if result.is_error:
        icon = style("✗", Color.RED)
        color = Color.RED

    header = f"{icon} {name_str}"

    content = result.content
    if isinstance(content, (dict, list)):
        body = json.dumps(content, indent=2, default=str)
    else:
        body = str(content) if content is not None else ""

    if not body.strip():
        return f"{header} {dim('(empty response)')}"

    # Truncate large JSON
    if len(body) > 2000:
        body = body[:2000] + f"\n{dim('… (truncated)')}"

    indented = "\n".join("  " + l for l in body.splitlines())
    return f"{header}\n{dim(indented)}"


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

_BASH_TOOLS = {"bash", "computer", "terminal", "shell", "execute"}
_FILE_TOOLS  = {"read_file", "write_file", "list_files", "glob", "find", "edit"}


def render_tool_result(
    result: ToolResult,
    verbose: bool = False,
    width: int | None = None,
) -> str:
    """
    Render a ToolResult for terminal display.

    Dispatches to tool-specific renderers.
    """
    name = result.tool_name.lower()

    if name in _BASH_TOOLS:
        return _render_bash_result(result, width=width)
    elif name in _FILE_TOOLS:
        return _render_file_result(result)
    else:
        return _render_json_result(result)


# ---------------------------------------------------------------------------
# Error display
# ---------------------------------------------------------------------------

def render_error(
    message: str,
    title: str = "Error",
    hint: str = "",
    width: int | None = None,
) -> str:
    """Render an error block."""
    w = width or terminal_width()
    parts = [style(f"  {message}", Color.RED)]
    if hint:
        parts.append(dim(f"  Hint: {hint}"))
    body = "\n".join(parts)
    return box(body, title=title, color=Color.RED, width=w)


def render_warning(message: str, hint: str = "") -> str:
    """Render a warning line."""
    icon = style("⚠", Color.YELLOW)
    msg = yellow(message)
    if hint:
        msg += "\n  " + dim(hint)
    return f"{icon}  {msg}"


# ---------------------------------------------------------------------------
# Success / info
# ---------------------------------------------------------------------------

def render_success(message: str, detail: str = "") -> str:
    icon = style("✓", Color.GREEN)
    msg = green(message)
    if detail:
        msg += "\n  " + dim(detail)
    return f"{icon}  {msg}"


def render_info(message: str, detail: str = "") -> str:
    icon = style("ℹ", Color.BLUE)
    if detail:
        message += "\n  " + dim(detail)
    return f"{icon}  {message}"


# ---------------------------------------------------------------------------
# Tool result list (for display in conversation)
# ---------------------------------------------------------------------------

def render_tool_results_block(
    results: list[ToolResult],
    width: int | None = None,
) -> str:
    """Render multiple tool results as a collated block."""
    if not results:
        return ""
    rendered = [render_tool_result(r, width=width) for r in results]
    return "\n\n".join(rendered)


__all__ = [
    "ToolResult",
    "TOOL_ICONS", "TOOL_COLORS",
    "render_tool_use",
    "render_tool_result",
    "render_tool_results_block",
    "render_error",
    "render_warning",
    "render_success",
    "render_info",
]
