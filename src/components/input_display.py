"""
Input prompt display and text input rendering.

Ports: components/BaseTextInput.tsx, components/PromptInput.tsx,
       components/InputHistory.tsx, components/AutocompleteDropdown.tsx
"""
from __future__ import annotations

import sys
import os
from typing import Sequence

from .formatter import Color, style, dim, bold, cyan, terminal_width, truncate


# ---------------------------------------------------------------------------
# Prompt prefix rendering
# ---------------------------------------------------------------------------

def render_prompt(
    prefix: str = "❯",
    color: Color = Color.GREEN,
    model: str = "",
    mode: str = "",
    cost: str = "",
) -> str:
    """
    Render the interactive CLI prompt prefix.

    Example output:  [claude-3.5-sonnet] ❯
    """
    parts = []
    if model:
        parts.append(dim(f"[{model}]"))
    if mode:
        parts.append(style(f"({mode})", Color.YELLOW))
    if cost:
        parts.append(dim(cost))

    prefix_str = style(prefix, color, Color.BOLD)
    if parts:
        return " ".join(parts) + " " + prefix_str
    return prefix_str


# ---------------------------------------------------------------------------
# User message display
# ---------------------------------------------------------------------------

def render_user_message(text: str, width: int | None = None) -> str:
    """Render a user message in the conversation view."""
    w = width or terminal_width()
    icon = style("❯", Color.GREEN, Color.BOLD)
    lines = text.strip().splitlines() or [""]

    if len(lines) == 1:
        return f"{icon} {lines[0]}"

    # Multi-line: indent continuation
    first = f"{icon} {lines[0]}"
    rest = [f"  {l}" for l in lines[1:]]
    return "\n".join([first] + rest)


# ---------------------------------------------------------------------------
# Suggestion / autocomplete display
# ---------------------------------------------------------------------------

def render_suggestions(
    suggestions: Sequence[str],
    selected: int = 0,
    max_display: int = 8,
    width: int | None = None,
) -> str:
    """
    Render an autocomplete dropdown.

    Ports: components/AutocompleteDropdown.tsx
    """
    if not suggestions:
        return ""

    w = width or terminal_width()
    display = suggestions[:max_display]
    overflow = len(suggestions) - max_display

    lines = []
    for i, suggestion in enumerate(display):
        truncated = truncate(suggestion, w - 6)
        if i == selected:
            line = style(f"  ▸ {truncated}", Color.CYAN, Color.BOLD)
        else:
            line = dim(f"    {truncated}")
        lines.append(line)

    if overflow > 0:
        lines.append(dim(f"    … {overflow} more"))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# File suggestion (slash-command / @ reference)
# ---------------------------------------------------------------------------

def render_file_suggestions(
    files: Sequence[str],
    query: str = "",
    selected: int = 0,
    max_display: int = 10,
    width: int | None = None,
) -> str:
    """Render file path autocomplete suggestions."""
    if not files:
        return ""

    w = width or terminal_width()
    display = files[:max_display]
    overflow = len(files) - max_display

    lines = []
    for i, path in enumerate(display):
        # Highlight matching portion
        if query and query.lower() in path.lower():
            idx = path.lower().find(query.lower())
            before = path[:idx]
            match = style(path[idx:idx + len(query)], Color.BRIGHT_YELLOW)
            after = path[idx + len(query):]
            label = before + match + after
        else:
            label = path

        label = truncate(label, w - 6)

        if i == selected:
            line = style("  ▸ ", Color.CYAN) + label
        else:
            line = dim("    ") + dim(label)
        lines.append(line)

    if overflow > 0:
        lines.append(dim(f"    … {overflow} more"))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Slash command hints
# ---------------------------------------------------------------------------

SLASH_COMMANDS = {
    "/help":    "Show available commands",
    "/clear":   "Clear conversation history",
    "/model":   "Switch model",
    "/compact": "Compact conversation to summary",
    "/cost":    "Show cost summary",
    "/status":  "Show session status",
    "/exit":    "Exit the session",
    "/debug":   "Toggle debug mode",
}


def render_slash_command_help(width: int | None = None) -> str:
    """Render a formatted list of available slash commands."""
    w = width or terminal_width()
    lines = [bold("  Available commands:"), ""]

    for cmd, desc in SLASH_COMMANDS.items():
        cmd_str = style(f"  {cmd}", Color.CYAN)
        lines.append(f"{cmd_str:<25}  {dim(desc)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Keyboard shortcut hints
# ---------------------------------------------------------------------------

def render_shortcut_hints(shortcuts: dict[str, str] | None = None) -> str:
    """Render keyboard shortcut hints at bottom of screen."""
    defaults = {
        "Tab":      "autocomplete",
        "↑/↓":      "history",
        "Ctrl+C":   "cancel",
        "Ctrl+D":   "exit",
        "Ctrl+R":   "search history",
    }
    hints = shortcuts or defaults
    parts = [f"{style(k, Color.DIM)} {dim(v)}" for k, v in hints.items()]
    return "  " + dim("  │  ").join(parts)


# ---------------------------------------------------------------------------
# Input history display
# ---------------------------------------------------------------------------

def render_history(
    history: Sequence[str],
    selected: int | None = None,
    max_display: int = 5,
    width: int | None = None,
) -> str:
    """Render recent input history for display."""
    if not history:
        return dim("  (no history)")

    w = width or terminal_width()
    display = list(history)[-max_display:]
    lines = [dim("  Recent:")]

    for i, entry in enumerate(reversed(display)):
        prefix = style("  ▸", Color.CYAN) if (selected is not None and i == selected) else "   "
        label = truncate(entry.splitlines()[0], w - 6)
        lines.append(f"{prefix} {dim(label)}")

    return "\n".join(lines)


__all__ = [
    "render_prompt",
    "render_user_message",
    "render_suggestions",
    "render_file_suggestions",
    "render_slash_command_help",
    "render_shortcut_hints",
    "render_history",
    "SLASH_COMMANDS",
]
