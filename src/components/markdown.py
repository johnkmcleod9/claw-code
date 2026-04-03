"""
Terminal markdown renderer.

Ports: components/MarkdownRenderer.tsx, components/AssistantMessage.tsx (text blocks),
       components/CodeBlock.tsx, components/BlockQuote.tsx
Renders Markdown for terminal display with ANSI formatting.
"""
from __future__ import annotations

import re
import textwrap
from typing import Callable

from .formatter import (
    Color, style, bold, dim, italic, underline, cyan, yellow, green, red,
    terminal_width, strip_ansi, SINGLE, ROUND, box,
)


# ---------------------------------------------------------------------------
# Simple inline markdown rendering
# ---------------------------------------------------------------------------

def render_inline(text: str, strip_color: bool = False) -> str:
    """
    Apply inline Markdown formatting:
    - **bold**
    - *italic* / _italic_
    - `code`
    - ~~strikethrough~~
    - [link](url)
    """
    # Bold
    text = re.sub(
        r"\*\*(.+?)\*\*|__(.+?)__",
        lambda m: bold(m.group(1) or m.group(2)),
        text,
    )
    # Italic
    text = re.sub(
        r"\*(.+?)\*|_([^_]+?)_",
        lambda m: italic(m.group(1) or m.group(2)),
        text,
    )
    # Inline code
    text = re.sub(
        r"`([^`]+?)`",
        lambda m: style(m.group(1), Color.BRIGHT_YELLOW),
        text,
    )
    # Strikethrough
    text = re.sub(
        r"~~(.+?)~~",
        lambda m: style(m.group(1), Color.DIM, Color.STRIKE),
        text,
    )
    # Links — show text (url)
    text = re.sub(
        r"\[(.+?)\]\((.+?)\)",
        lambda m: f"{underline(m.group(1))} {dim(f'({m.group(2)})')}",
        text,
    )

    if strip_color:
        text = strip_ansi(text)
    return text


# ---------------------------------------------------------------------------
# Block-level rendering
# ---------------------------------------------------------------------------

_HEADING_COLORS = [
    Color.BRIGHT_CYAN,    # H1
    Color.CYAN,           # H2
    Color.BRIGHT_BLUE,    # H3
    Color.BLUE,           # H4
    Color.WHITE,          # H5
    Color.DIM,            # H6
]

_HEADING_CHARS = ["═", "─", "·", "·", "·", "·"]


def _render_heading(level: int, text: str, width: int) -> str:
    color = _HEADING_COLORS[min(level - 1, 5)]
    prefix = "#" * level + " "
    content = render_inline(text)
    label = style(prefix + content, color, Color.BOLD)

    if level <= 2:
        char = _HEADING_CHARS[level - 1]
        underln = style(char * min(len(strip_ansi(label)), width), color)
        return f"\n{label}\n{underln}\n"
    return f"\n{label}\n"


def _render_code_block(lang: str, code: str, width: int) -> str:
    """Render a fenced code block with optional language label."""
    lines = code.rstrip("\n").splitlines()
    w = width

    # Language badge
    if lang:
        badge = style(f" {lang} ", Color.BLACK, Color.BG_CYAN)
        header = f"{badge}\n"
    else:
        header = ""

    # Code content (with line numbers for longer blocks)
    show_numbers = len(lines) > 5
    formatted_lines = []
    for i, line in enumerate(lines, 1):
        if show_numbers:
            num = style(f"{i:3d} ", Color.DIM)
        else:
            num = "    "
        formatted_lines.append(f"{num}{style(line, Color.BRIGHT_YELLOW)}")

    inner = "\n".join(formatted_lines)
    # Surround with subtle border
    top_border = style("┌" + "─" * (w - 2) + "┐", Color.DIM)
    bot_border = style("└" + "─" * (w - 2) + "┘", Color.DIM)
    indented = "\n".join("│ " + l for l in inner.splitlines())
    return f"\n{header}{top_border}\n{indented}\n{bot_border}\n"


def _render_blockquote(text: str, width: int) -> str:
    """Render a blockquote block."""
    w = width - 4
    wrapped = textwrap.fill(render_inline(text), width=w)
    lines = wrapped.splitlines()
    bar = style("▌", Color.CYAN)
    inner = "\n".join(f"{bar} {style(l, Color.DIM)}" for l in lines)
    return f"\n{inner}\n"


def _render_list_item(
    text: str,
    depth: int,
    ordered: bool,
    number: int,
    width: int,
) -> str:
    indent = "  " * depth
    if ordered:
        bullet = style(f"{number}.", Color.CYAN)
    else:
        bullets = ["•", "◦", "▸", "▹"]
        bullet = style(bullets[min(depth, len(bullets) - 1)], Color.CYAN)
    content = render_inline(text)
    return f"{indent}{bullet} {content}"


def _render_hr(width: int) -> str:
    return "\n" + style("─" * width, Color.DIM) + "\n"


def _render_table_md(lines: list[str], width: int) -> str:
    """Render a Markdown table."""
    rows = []
    for line in lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(cells)

    if not rows:
        return ""

    # Filter out separator rows
    filtered = [r for r in rows if not all(re.match(r"^[-:]+$", c) for c in r)]
    if not filtered:
        return ""

    num_cols = max(len(r) for r in filtered)
    col_widths = [0] * num_cols

    for row in filtered:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(strip_ansi(render_inline(cell))))

    def fmt_row(row: list[str], header: bool = False) -> str:
        parts = []
        for i, cell in enumerate(row):
            rendered = render_inline(cell)
            if header:
                rendered = bold(cell)
            w = col_widths[i] if i < len(col_widths) else 10
            pad = " " * max(0, w - len(strip_ansi(rendered)))
            parts.append(rendered + pad)
        return " │ ".join(parts)

    out = []
    for i, row in enumerate(filtered):
        out.append(fmt_row(row, header=(i == 0)))
        if i == 0:
            divider = "─" * (sum(col_widths) + 3 * (num_cols - 1))
            out.append(style(divider, Color.DIM))

    return "\n" + "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Main renderer
# ---------------------------------------------------------------------------

def render_markdown(
    text: str,
    width: int | None = None,
    compact: bool = False,
) -> str:
    """
    Render Markdown text for terminal display.

    Handles:
    - Headings (H1-H6)
    - Fenced code blocks
    - Inline code
    - Bold, italic, strikethrough
    - Blockquotes
    - Unordered / ordered lists
    - Horizontal rules
    - Tables
    - Links
    """
    w = width or terminal_width()
    lines = text.splitlines()
    output: list[str] = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Fenced code block
        fence_match = re.match(r"^(`{3,}|~{3,})(\w*)\s*$", line)
        if fence_match:
            fence_char = fence_match.group(1)
            lang = fence_match.group(2)
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].startswith(fence_char):
                code_lines.append(lines[i])
                i += 1
            output.append(_render_code_block(lang, "\n".join(code_lines), w))
            i += 1
            continue

        # Heading
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            level = len(heading_match.group(1))
            text_part = heading_match.group(2)
            output.append(_render_heading(level, text_part, w))
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^[-*_]{3,}\s*$", line):
            output.append(_render_hr(w))
            i += 1
            continue

        # Blockquote
        if line.startswith("> "):
            quote_lines = []
            while i < len(lines) and lines[i].startswith("> "):
                quote_lines.append(lines[i][2:])
                i += 1
            output.append(_render_blockquote(" ".join(quote_lines), w))
            continue

        # Table — collect rows
        if "|" in line and i + 1 < len(lines) and re.match(r"^\|[-| :]+\|?\s*$", lines[i + 1]):
            table_lines = []
            while i < len(lines) and "|" in lines[i]:
                table_lines.append(lines[i])
                i += 1
            output.append(_render_table_md(table_lines, w))
            continue

        # Unordered list
        ul_match = re.match(r"^(\s*)[-*+]\s+(.+)$", line)
        if ul_match:
            depth = len(ul_match.group(1)) // 2
            output.append(_render_list_item(ul_match.group(2), depth, False, 0, w))
            i += 1
            continue

        # Ordered list
        ol_match = re.match(r"^(\s*)(\d+)\.\s+(.+)$", line)
        if ol_match:
            depth = len(ol_match.group(1)) // 2
            num = int(ol_match.group(2))
            output.append(_render_list_item(ol_match.group(3), depth, True, num, w))
            i += 1
            continue

        # Empty line
        if not line.strip():
            if not compact:
                output.append("")
            i += 1
            continue

        # Regular paragraph line
        output.append(render_inline(line))
        i += 1

    result = "\n".join(output)
    # Collapse multiple blank lines
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result


# ---------------------------------------------------------------------------
# Convenience renderers
# ---------------------------------------------------------------------------

def render_assistant_message(content: str, width: int | None = None) -> str:
    """Render an assistant message with markdown formatting."""
    return render_markdown(content, width=width)


def render_code(code: str, lang: str = "", width: int | None = None) -> str:
    """Render a code block directly."""
    w = width or terminal_width()
    return _render_code_block(lang, code, w)


__all__ = [
    "render_inline",
    "render_markdown",
    "render_assistant_message",
    "render_code",
    # Sub-renderers (for testing / custom use)
    "_render_heading",
    "_render_code_block",
    "_render_blockquote",
]
