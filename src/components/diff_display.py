"""
Diff display for terminal output.

Ports: components/DiffView.tsx, components/FileDiff.tsx, components/PatchView.tsx
Renders unified and side-by-side diffs with syntax highlighting.
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Sequence

from .formatter import Color, style, terminal_width, strip_ansi


# ---------------------------------------------------------------------------
# Diff line types
# ---------------------------------------------------------------------------

@dataclass
class DiffLine:
    kind: str    # "context" | "added" | "removed" | "header" | "hunk"
    old_no: int | None
    new_no: int | None
    text: str


def parse_unified_diff(diff_text: str) -> list[DiffLine]:
    """Parse a unified diff string into DiffLine objects."""
    lines: list[DiffLine] = []
    old_no = 0
    new_no = 0

    for raw in diff_text.splitlines():
        if raw.startswith("--- ") or raw.startswith("+++ "):
            lines.append(DiffLine("header", None, None, raw))
        elif raw.startswith("@@ "):
            # Parse hunk header: @@ -old_start,old_len +new_start,new_len @@
            lines.append(DiffLine("hunk", None, None, raw))
            try:
                parts = raw.split(" ")
                old_part = parts[1]  # e.g. "-10,5"
                new_part = parts[2]  # e.g. "+12,7"
                old_no = int(old_part.lstrip("-").split(",")[0])
                new_no = int(new_part.lstrip("+").split(",")[0])
            except (IndexError, ValueError):
                pass
        elif raw.startswith("+"):
            lines.append(DiffLine("added", None, new_no, raw[1:]))
            new_no += 1
        elif raw.startswith("-"):
            lines.append(DiffLine("removed", old_no, None, raw[1:]))
            old_no += 1
        elif raw.startswith("\\"):
            lines.append(DiffLine("context", None, None, raw))
        else:
            lines.append(DiffLine("context", old_no, new_no, raw[1:] if raw.startswith(" ") else raw))
            old_no += 1
            new_no += 1

    return lines


# ---------------------------------------------------------------------------
# Diff rendering
# ---------------------------------------------------------------------------

_GUTTER = 5  # digits for line numbers


def _fmt_line_no(n: int | None, width: int = _GUTTER) -> str:
    if n is None:
        return style(" " * width, Color.DIM)
    return style(str(n).rjust(width), Color.DIM)


def render_unified_diff(
    diff_lines: list[DiffLine],
    show_line_numbers: bool = True,
    context_color: Color = Color.RESET,
    added_bg: str = "\033[48;5;22m",    # dark green bg
    removed_bg: str = "\033[48;5;52m",  # dark red bg
    width: int | None = None,
) -> str:
    """Render parsed diff lines as colored terminal output."""
    w = width or terminal_width()
    out: list[str] = []

    for dl in diff_lines:
        if dl.kind == "header":
            out.append(style(dl.text, Color.BOLD, Color.CYAN))
            continue

        if dl.kind == "hunk":
            out.append(style(dl.text, Color.CYAN))
            continue

        # Line number gutter
        if show_line_numbers:
            old_gutter = _fmt_line_no(dl.old_no)
            new_gutter = _fmt_line_no(dl.new_no)
            gutter = f"{old_gutter} {new_gutter} "
        else:
            gutter = ""

        text = dl.text.rstrip("\n")

        if dl.kind == "added":
            prefix = style("+", Color.BRIGHT_GREEN)
            line = f"{gutter}{prefix} {added_bg}{text}{Color.RESET.value}"
        elif dl.kind == "removed":
            prefix = style("-", Color.BRIGHT_RED)
            line = f"{gutter}{prefix} {removed_bg}{text}{Color.RESET.value}"
        else:
            prefix = style(" ", Color.DIM)
            line = f"{gutter}{prefix} {style(text, Color.DIM)}"

        out.append(line)

    return "\n".join(out)


def diff_strings(
    old: str,
    new: str,
    fromfile: str = "before",
    tofile: str = "after",
    context_lines: int = 3,
    **render_kwargs,
) -> str:
    """Generate and render a diff between two strings."""
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)

    raw_diff = "".join(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=fromfile,
            tofile=tofile,
            n=context_lines,
        )
    )

    if not raw_diff:
        return style("(no changes)", Color.DIM)

    parsed = parse_unified_diff(raw_diff)
    return render_unified_diff(parsed, **render_kwargs)


def diff_files(
    old_path: str,
    new_path: str,
    context_lines: int = 3,
    **render_kwargs,
) -> str:
    """Diff two files and render the result."""
    try:
        with open(old_path, encoding="utf-8", errors="replace") as f:
            old = f.read()
        with open(new_path, encoding="utf-8", errors="replace") as f:
            new = f.read()
    except OSError as e:
        return style(f"Error reading files: {e}", Color.RED)

    return diff_strings(old, new, fromfile=old_path, tofile=new_path, context_lines=context_lines, **render_kwargs)


# ---------------------------------------------------------------------------
# Side-by-side diff
# ---------------------------------------------------------------------------

def render_side_by_side(
    old: str,
    new: str,
    width: int | None = None,
) -> str:
    """Render a side-by-side diff view."""
    w = (width or terminal_width())
    col_w = (w - 3) // 2  # 3 chars for " │ " separator

    old_lines = old.splitlines()
    new_lines = new.splitlines()

    matcher = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    out: list[str] = []

    sep = style(" │ ", Color.DIM)

    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            for line in old_lines[i1:i2]:
                left = line[:col_w].ljust(col_w)
                right = line[:col_w].ljust(col_w)
                out.append(f"{style(left, Color.DIM)}{sep}{style(right, Color.DIM)}")

        elif op == "replace":
            old_chunk = old_lines[i1:i2]
            new_chunk = new_lines[j1:j2]
            for ol, nl in zip(old_chunk, new_chunk):
                left = style(ol[:col_w].ljust(col_w), Color.RED)
                right = style(nl[:col_w].ljust(col_w), Color.GREEN)
                out.append(f"{left}{sep}{right}")
            # Handle length mismatch
            for ol in old_chunk[len(new_chunk):]:
                left = style(ol[:col_w].ljust(col_w), Color.RED)
                right = " " * col_w
                out.append(f"{left}{sep}{right}")
            for nl in new_chunk[len(old_chunk):]:
                left = " " * col_w
                right = style(nl[:col_w].ljust(col_w), Color.GREEN)
                out.append(f"{left}{sep}{right}")

        elif op == "delete":
            for ol in old_lines[i1:i2]:
                left = style(ol[:col_w].ljust(col_w), Color.RED)
                right = " " * col_w
                out.append(f"{left}{sep}{right}")

        elif op == "insert":
            for nl in new_lines[j1:j2]:
                left = " " * col_w
                right = style(nl[:col_w].ljust(col_w), Color.GREEN)
                out.append(f"{left}{sep}{right}")

    return "\n".join(out)


# ---------------------------------------------------------------------------
# Compact summary
# ---------------------------------------------------------------------------

def diff_summary(old: str, new: str) -> str:
    """Return a one-line diff summary: '+N -M lines'."""
    old_lines = set(old.splitlines())
    new_lines = set(new.splitlines())
    added = len(new_lines - old_lines)
    removed = len(old_lines - new_lines)
    parts = []
    if added:
        parts.append(style(f"+{added}", Color.GREEN))
    if removed:
        parts.append(style(f"-{removed}", Color.RED))
    return " ".join(parts) if parts else style("no changes", Color.DIM)


__all__ = [
    "DiffLine",
    "parse_unified_diff",
    "render_unified_diff",
    "diff_strings",
    "diff_files",
    "render_side_by_side",
    "diff_summary",
]
