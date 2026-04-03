"""
String manipulation utilities.

Ports: utils/array.ts, utils/argumentSubstitution.ts, and various
string-handling helpers from the Claude Code TypeScript codebase.
"""
from __future__ import annotations

import re
import textwrap
import unicodedata
from typing import Iterable


# ---------------------------------------------------------------------------
# Basic string operations
# ---------------------------------------------------------------------------

def truncate(text: str, max_len: int, suffix: str = "…") -> str:
    """Truncate *text* to *max_len* characters, appending *suffix* if cut."""
    if len(text) <= max_len:
        return text
    cut = max_len - len(suffix)
    if cut <= 0:
        return suffix[:max_len]
    return text[:cut] + suffix


def truncate_lines(text: str, max_lines: int, suffix: str = "…") -> str:
    """Truncate *text* to *max_lines* lines."""
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + "\n" + suffix


def indent(text: str, prefix: str = "  ") -> str:
    """Indent every non-empty line of *text* by *prefix*."""
    return textwrap.indent(text, prefix, predicate=lambda line: line.strip())


def dedent(text: str) -> str:
    """Remove common leading whitespace from all lines."""
    return textwrap.dedent(text)


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from *text*."""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


def slug(text: str, separator: str = "-") -> str:
    """
    Convert *text* to a URL/filename-safe slug.

    E.g. "Hello World!" → "hello-world"
    """
    # Normalize unicode
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    # Lowercase, replace non-alphanumeric with separator
    text = re.sub(r"[^\w\s]", "", text).lower()
    text = re.sub(r"[\s_]+", separator, text).strip(separator)
    return text


def camel_to_snake(name: str) -> str:
    """Convert camelCase or PascalCase to snake_case."""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def snake_to_camel(name: str, upper_first: bool = False) -> str:
    """Convert snake_case to camelCase or PascalCase."""
    parts = name.split("_")
    if upper_first:
        return "".join(p.capitalize() for p in parts)
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


# ---------------------------------------------------------------------------
# Argument substitution (ports utils/argumentSubstitution.ts)
# ---------------------------------------------------------------------------

def substitute_args(template: str, args: dict[str, str]) -> str:
    """
    Replace ``{key}`` placeholders in *template* with values from *args*.

    Unknown keys are left unchanged.  Double-braces ``{{`` escape to ``{``.

    Example::

        substitute_args("Hello {name}!", {"name": "world"})
        # → "Hello world!"
    """
    def replacer(m: re.Match) -> str:
        key = m.group(1)
        return args.get(key, m.group(0))

    return re.sub(r"\{(\w+)\}", replacer, template)


# ---------------------------------------------------------------------------
# Text analysis helpers
# ---------------------------------------------------------------------------

def word_count(text: str) -> int:
    """Count words in *text*."""
    return len(text.split())


def line_count(text: str) -> int:
    """Count lines in *text* (empty string = 0 lines)."""
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def first_line(text: str) -> str:
    """Return the first non-empty line of *text*."""
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def extract_code_blocks(text: str) -> list[tuple[str, str]]:
    """
    Extract fenced code blocks from markdown text.

    Returns list of (language, code) tuples.
    """
    pattern = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
    return [(m.group(1), m.group(2)) for m in pattern.finditer(text)]


# ---------------------------------------------------------------------------
# Collection / array helpers (ports utils/array.ts)
# ---------------------------------------------------------------------------

def unique(items: Iterable, key=None) -> list:
    """Return deduplicated list preserving order."""
    seen: set = set()
    result = []
    for item in items:
        k = key(item) if key else item
        if k not in seen:
            seen.add(k)
            result.append(item)
    return result


def chunk(lst: list, size: int) -> list[list]:
    """Split *lst* into chunks of *size*."""
    return [lst[i:i + size] for i in range(0, len(lst), size)]


def flatten(nested: Iterable) -> list:
    """Flatten one level of nesting."""
    result = []
    for item in nested:
        if isinstance(item, (list, tuple)):
            result.extend(item)
        else:
            result.append(item)
    return result


def partition(lst: list, predicate) -> tuple[list, list]:
    """Split *lst* into (matches, non_matches) based on *predicate*."""
    yes, no = [], []
    for item in lst:
        (yes if predicate(item) else no).append(item)
    return yes, no


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

def pluralize(count: int, singular: str, plural: str | None = None) -> str:
    """Return singular or plural form based on count."""
    if plural is None:
        plural = singular + "s"
    return singular if count == 1 else plural


def format_count(count: int, noun: str, plural: str | None = None) -> str:
    """E.g. format_count(3, 'file') → '3 files'."""
    return f"{count} {pluralize(count, noun, plural)}"


def safe_str(value: object, fallback: str = "") -> str:
    """Convert *value* to str, returning *fallback* on error."""
    try:
        return str(value)
    except Exception:
        return fallback


__all__ = [
    "truncate",
    "truncate_lines",
    "indent",
    "dedent",
    "strip_ansi",
    "slug",
    "camel_to_snake",
    "snake_to_camel",
    "substitute_args",
    "word_count",
    "line_count",
    "first_line",
    "extract_code_blocks",
    "unique",
    "chunk",
    "flatten",
    "partition",
    "pluralize",
    "format_count",
    "safe_str",
]
