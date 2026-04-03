"""
Status indicators and session status display.

Ports: components/StatusBar.tsx, components/SessionStatus.tsx,
       components/ModelInfo.tsx, components/MCPStatus.tsx
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .formatter import Color, style, dim, bold, green, red, yellow, cyan, terminal_width


# ---------------------------------------------------------------------------
# Status types
# ---------------------------------------------------------------------------

@dataclass
class MCPServerStatus:
    name: str
    connected: bool
    tool_count: int = 0
    error: str = ""


@dataclass
class SessionStatus:
    model: str = ""
    mode: str = ""              # "default" | "auto" | "bypassPermissions"
    mcp_servers: list[MCPServerStatus] = field(default_factory=list)
    tool_count: int = 0
    session_id: str = ""
    cwd: str = ""
    version: str = ""
    cost_usd: float = 0.0
    context_tokens: int = 0
    context_max: int = 200_000
    thinking_enabled: bool = False
    stream_enabled: bool = True


# ---------------------------------------------------------------------------
# Status line (compact, shown at prompt)
# ---------------------------------------------------------------------------

def render_status_line(status: SessionStatus, width: int | None = None) -> str:
    """Compact one-line status for the prompt area."""
    parts = []

    if status.model:
        parts.append(style(status.model, Color.CYAN))

    if status.mode and status.mode != "default":
        mode_color = Color.RED if status.mode == "bypassPermissions" else Color.YELLOW
        parts.append(style(f"[{status.mode}]", mode_color))

    if status.tool_count:
        parts.append(dim(f"{status.tool_count} tools"))

    if status.context_tokens:
        pct = status.context_tokens / max(1, status.context_max)
        ctx_color = Color.RED if pct > 0.9 else Color.YELLOW if pct > 0.7 else Color.DIM
        parts.append(style(f"ctx:{_fmt_tokens(status.context_tokens)}", ctx_color))

    if status.cost_usd > 0:
        parts.append(dim(f"${status.cost_usd:.3f}"))

    return "  " + dim("  │  ").join(parts)


def _fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.0f}K"
    return str(n)


# ---------------------------------------------------------------------------
# Full /status display
# ---------------------------------------------------------------------------

def render_session_status(status: SessionStatus, width: int | None = None) -> str:
    """Full session status display (for /status command)."""
    w = width or terminal_width()
    lines: list[str] = []

    lines.append("")
    lines.append(bold("  Session Status"))
    lines.append(dim("  " + "─" * (w - 4)))

    # Core info
    if status.model:
        lines.append(f"  {'Model:':<22} {style(status.model, Color.CYAN)}")
    if status.version:
        lines.append(f"  {'Version:':<22} {dim(status.version)}")
    if status.session_id:
        lines.append(f"  {'Session ID:':<22} {dim(status.session_id[:16] + '…')}")
    if status.cwd:
        lines.append(f"  {'Working dir:':<22} {dim(status.cwd)}")

    lines.append("")

    # Mode
    mode_color = {
        "bypassPermissions": Color.RED,
        "auto":              Color.YELLOW,
        "default":           Color.GREEN,
    }.get(status.mode, Color.WHITE)
    lines.append(f"  {'Mode:':<22} {style(status.mode or 'default', mode_color)}")

    # Context
    pct = status.context_tokens / max(1, status.context_max)
    ctx_color = Color.RED if pct > 0.9 else Color.YELLOW if pct > 0.7 else Color.GREEN
    lines.append(
        f"  {'Context:':<22} "
        f"{style(_fmt_tokens(status.context_tokens), ctx_color)}"
        f" / {dim(_fmt_tokens(status.context_max))}"
        f" {dim(f'({pct*100:.0f}%)')}"
    )

    # Cost
    if status.cost_usd > 0:
        lines.append(f"  {'Cost (session):':<22} ${status.cost_usd:.4f}")

    # Thinking
    if status.thinking_enabled:
        lines.append(f"  {'Thinking:':<22} {style('enabled', Color.CYAN)}")

    lines.append("")

    # MCP servers
    if status.mcp_servers:
        lines.append(dim("  MCP Servers:"))
        for srv in status.mcp_servers:
            icon = green("✓") if srv.connected else red("✗")
            name = style(srv.name, Color.CYAN)
            detail = dim(f"{srv.tool_count} tools") if srv.connected else red(f"  {srv.error}")
            lines.append(f"    {icon} {name}  {detail}")
        lines.append("")
    elif status.tool_count:
        lines.append(f"  {'Tools:':<22} {dim(str(status.tool_count))}")

    lines.append(dim("  " + "─" * (w - 4)))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MCP connectivity indicator (compact)
# ---------------------------------------------------------------------------

def render_mcp_status(servers: Sequence[MCPServerStatus]) -> str:
    """One-line MCP connectivity indicator."""
    if not servers:
        return dim("  No MCP servers")

    connected = sum(1 for s in servers if s.connected)
    total = len(servers)
    color = Color.GREEN if connected == total else Color.YELLOW if connected > 0 else Color.RED
    icon = style("⬡", color)
    label = style(f"{connected}/{total} MCP", color)

    if connected < total:
        failed = [s.name for s in servers if not s.connected]
        label += dim(f" (failed: {', '.join(failed)})")

    return f"  {icon} {label}"


# ---------------------------------------------------------------------------
# Mode change notification
# ---------------------------------------------------------------------------

def render_mode_change(old_mode: str, new_mode: str) -> str:
    """Display a mode change notification."""
    old_str = style(old_mode, Color.DIM)
    new_str = style(new_mode, Color.YELLOW, Color.BOLD)
    return f"  {style('◆', Color.MAGENTA)} Mode changed: {old_str} → {new_str}"


# ---------------------------------------------------------------------------
# Version / update status
# ---------------------------------------------------------------------------

def render_update_available(current: str, latest: str) -> str:
    """Show an update-available banner."""
    return (
        f"  {style('↑', Color.YELLOW)}  Update available: "
        f"{style(current, Color.DIM)} → {style(latest, Color.BRIGHT_YELLOW)}"
    )


def render_deprecation_warning(message: str) -> str:
    """Show a deprecation warning."""
    icon = style("⚠", Color.YELLOW)
    return f"  {icon}  {yellow(message)}"


# ---------------------------------------------------------------------------
# Auto-mode status
# ---------------------------------------------------------------------------

def render_auto_mode_status(
    turn: int,
    max_turns: int,
    interrupted: bool = False,
) -> str:
    """Render agentic mode turn counter."""
    color = Color.RED if interrupted else Color.CYAN
    icon = style("◈", color)
    turns_str = style(f"Turn {turn}/{max_turns}", color)
    if interrupted:
        return f"  {icon} {turns_str}  {red('(interrupted)')}"
    return f"  {icon} {turns_str}"


__all__ = [
    "MCPServerStatus",
    "SessionStatus",
    "render_status_line",
    "render_session_status",
    "render_mcp_status",
    "render_mode_change",
    "render_update_available",
    "render_deprecation_warning",
    "render_auto_mode_status",
]
