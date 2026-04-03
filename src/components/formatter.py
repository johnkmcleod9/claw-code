"""
Terminal output formatter.

Ports: components/OutputFormatter.tsx, components/FormattedText.tsx
Provides rich text formatting, wrapping, and styling for terminal output.
"""
from __future__ import annotations

import os
import shutil
import textwrap
from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence


# ---------------------------------------------------------------------------
# ANSI escape codes
# ---------------------------------------------------------------------------

class Color(str, Enum):
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    ITALIC  = "\033[3m"
    UNDER   = "\033[4m"
    BLINK   = "\033[5m"
    REVERSE = "\033[7m"
    STRIKE  = "\033[9m"

    # Foreground
    BLACK   = "\033[30m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"
    GRAY    = "\033[90m"

    BRIGHT_RED     = "\033[91m"
    BRIGHT_GREEN   = "\033[92m"
    BRIGHT_YELLOW  = "\033[93m"
    BRIGHT_BLUE    = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN    = "\033[96m"
    BRIGHT_WHITE   = "\033[97m"

    # Background
    BG_BLACK   = "\033[40m"
    BG_RED     = "\033[41m"
    BG_GREEN   = "\033[42m"
    BG_YELLOW  = "\033[43m"
    BG_BLUE    = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN    = "\033[46m"
    BG_WHITE   = "\033[47m"


def _no_color() -> bool:
    """Return True if color output should be suppressed."""
    return (
        os.environ.get("NO_COLOR") is not None
        or os.environ.get("TERM") == "dumb"
        or not os.isatty(1)
    )


def style(text: str, *codes: Color, force: bool = False) -> str:
    """Wrap text in ANSI codes (no-op if NO_COLOR or non-TTY)."""
    if not force and _no_color():
        return text
    prefix = "".join(c.value for c in codes)
    return f"{prefix}{text}{Color.RESET.value}"


def bold(text: str, **kw) -> str:
    return style(text, Color.BOLD, **kw)


def dim(text: str, **kw) -> str:
    return style(text, Color.DIM, **kw)


def italic(text: str, **kw) -> str:
    return style(text, Color.ITALIC, **kw)


def underline(text: str, **kw) -> str:
    return style(text, Color.UNDER, **kw)


def red(text: str, **kw) -> str:
    return style(text, Color.RED, **kw)


def green(text: str, **kw) -> str:
    return style(text, Color.GREEN, **kw)


def yellow(text: str, **kw) -> str:
    return style(text, Color.YELLOW, **kw)


def blue(text: str, **kw) -> str:
    return style(text, Color.BLUE, **kw)


def cyan(text: str, **kw) -> str:
    return style(text, Color.CYAN, **kw)


def gray(text: str, **kw) -> str:
    return style(text, Color.GRAY, **kw)


# ---------------------------------------------------------------------------
# Terminal width
# ---------------------------------------------------------------------------

def terminal_width(default: int = 80) -> int:
    """Get the current terminal column width."""
    try:
        return shutil.get_terminal_size((default, 24)).columns
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Text layout helpers
# ---------------------------------------------------------------------------

def wrap(text: str, width: int | None = None, indent: str = "") -> str:
    """Wrap text to terminal width."""
    w = width or terminal_width()
    return textwrap.fill(text, width=w, initial_indent=indent, subsequent_indent=indent)


def indent_block(text: str, spaces: int = 2) -> str:
    """Indent every line of a block."""
    prefix = " " * spaces
    return "\n".join(prefix + line for line in text.splitlines())


def truncate(text: str, max_len: int, suffix: str = "…") -> str:
    """Truncate a string to max_len, appending suffix if truncated."""
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix


def pad_right(text: str, width: int, char: str = " ") -> str:
    """Pad text on the right to at least `width` visible chars."""
    visible_len = len(strip_ansi(text))
    padding = max(0, width - visible_len)
    return text + char * padding


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    import re
    return re.sub(r"\033\[[0-9;]*[mGKHF]", "", text)


# ---------------------------------------------------------------------------
# Box / banner drawing
# ---------------------------------------------------------------------------

SINGLE = {"tl": "┌", "tr": "┐", "bl": "└", "br": "┘", "h": "─", "v": "│"}
DOUBLE = {"tl": "╔", "tr": "╗", "bl": "╚", "br": "╝", "h": "═", "v": "║"}
ROUND  = {"tl": "╭", "tr": "╮", "bl": "╰", "br": "╯", "h": "─", "v": "│"}


def box(
    text: str,
    title: str = "",
    style_chars: dict = SINGLE,
    width: int | None = None,
    padding: int = 1,
    color: Color | None = None,
) -> str:
    """Draw a Unicode box around text."""
    w = width or terminal_width()
    inner = w - 2  # left+right border chars
    lines = text.splitlines() or [""]

    ch = style_chars
    pad = " " * padding

    def border(s: str) -> str:
        return style(s, color) if color else s

    # Top
    if title:
        title_str = f" {title} "
        top = border(ch["tl"] + ch["h"] + title_str + ch["h"] * (inner - len(title_str) - 1) + ch["tr"])
    else:
        top = border(ch["tl"] + ch["h"] * inner + ch["tr"])

    # Middle
    rows = []
    for line in lines:
        visible = strip_ansi(line)
        filler = " " * max(0, inner - len(visible) - 2 * padding)
        rows.append(border(ch["v"]) + pad + line + filler + pad + border(ch["v"]))

    # Bottom
    bot = border(ch["bl"] + ch["h"] * inner + ch["br"])

    return "\n".join([top] + rows + [bot])


def banner(text: str, color: Color = Color.CYAN) -> str:
    """Simple full-width header banner."""
    w = terminal_width()
    line = "─" * w
    padded = text.center(w)
    return "\n".join([
        style(line, color),
        style(padded, color, Color.BOLD),
        style(line, color),
    ])


# ---------------------------------------------------------------------------
# Columnar output
# ---------------------------------------------------------------------------

@dataclass
class Column:
    header: str
    key: str
    width: int | None = None
    align: str = "left"  # "left" | "right" | "center"
    color: Color | None = None


def table(
    rows: Sequence[dict],
    columns: Sequence[Column],
    header_color: Color = Color.BOLD,
    row_separator: bool = False,
) -> str:
    """Render a list of dicts as a formatted table."""
    # Compute column widths
    col_widths: list[int] = []
    for col in columns:
        if col.width:
            col_widths.append(col.width)
        else:
            max_w = len(col.header)
            for row in rows:
                max_w = max(max_w, len(str(row.get(col.key, ""))))
            col_widths.append(max_w)

    def fmt_cell(text: str, width: int, align: str, color: Color | None) -> str:
        s = str(text)
        if align == "right":
            s = s.rjust(width)
        elif align == "center":
            s = s.center(width)
        else:
            s = s.ljust(width)
        return style(s, color) if color else s

    # Header
    header_parts = [
        style(col.header.ljust(w), header_color)
        for col, w in zip(columns, col_widths)
    ]
    sep = "  "
    lines = [sep.join(header_parts)]

    # Divider
    divider = sep.join("─" * w for w in col_widths)
    lines.append(style(divider, Color.DIM))

    # Data rows
    for i, row in enumerate(rows):
        parts = [
            fmt_cell(row.get(col.key, ""), w, col.align, col.color)
            for col, w in zip(columns, col_widths)
        ]
        lines.append(sep.join(parts))
        if row_separator and i < len(rows) - 1:
            lines.append(style(divider, Color.DIM))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Key-value display
# ---------------------------------------------------------------------------

def kv_list(
    items: dict | Sequence[tuple],
    key_color: Color = Color.CYAN,
    sep: str = ": ",
    indent: int = 0,
) -> str:
    """Format a key-value list for display."""
    if isinstance(items, dict):
        pairs = list(items.items())
    else:
        pairs = list(items)

    if not pairs:
        return ""

    max_key_len = max(len(str(k)) for k, _ in pairs)
    prefix = " " * indent
    out = []
    for k, v in pairs:
        key_str = str(k).ljust(max_key_len)
        out.append(f"{prefix}{style(key_str, key_color)}{sep}{v}")
    return "\n".join(out)


__all__ = [
    # Colors / styling
    "Color", "style", "bold", "dim", "italic", "underline",
    "red", "green", "yellow", "blue", "cyan", "gray",
    "strip_ansi",
    # Layout
    "terminal_width", "wrap", "indent_block", "truncate", "pad_right",
    # Boxes / banners
    "SINGLE", "DOUBLE", "ROUND", "box", "banner",
    # Tables / KV
    "Column", "table", "kv_list",
]
