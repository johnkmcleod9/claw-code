"""
Encoding detection and safe text I/O.

Ports: various file-reading helpers that need encoding fallbacks,
similar to what Claude Code uses when reading arbitrary project files.
"""
from __future__ import annotations

import codecs
from pathlib import Path

# Try to use chardet for best results; fall back to heuristics if not installed.
try:
    import chardet as _chardet
    _HAS_CHARDET = True
except ImportError:
    _HAS_CHARDET = False


# Ordered list of encodings to try when detection fails
_FALLBACK_ENCODINGS = [
    "utf-8",
    "utf-8-sig",  # UTF-8 with BOM
    "latin-1",
    "cp1252",
    "iso-8859-1",
]


def detect_encoding(data: bytes, default: str = "utf-8") -> str:
    """
    Detect the character encoding of *data*.

    Uses chardet if available, otherwise tries common encodings.
    Returns a codec name that Python's codecs module accepts.
    """
    if not data:
        return default

    # BOM detection first (most reliable)
    if data.startswith(b"\xff\xfe\x00\x00"):
        return "utf-32-le"
    if data.startswith(b"\x00\x00\xfe\xff"):
        return "utf-32-be"
    if data.startswith(b"\xff\xfe"):
        return "utf-16-le"
    if data.startswith(b"\xfe\xff"):
        return "utf-16-be"
    if data.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"

    if _HAS_CHARDET:
        result = _chardet.detect(data)
        if result and result.get("confidence", 0) >= 0.75 and result.get("encoding"):
            enc = result["encoding"]
            # Validate that Python knows this codec
            try:
                codecs.lookup(enc)
                return enc
            except LookupError:
                pass

    # Heuristic fallback: try UTF-8 first
    try:
        data.decode("utf-8")
        return "utf-8"
    except (UnicodeDecodeError, ValueError):
        pass

    return default


def read_file_text(
    path: str | Path,
    hint_encoding: str | None = None,
    errors: str = "replace",
) -> tuple[str, str]:
    """
    Read a text file, auto-detecting its encoding.

    Returns ``(text, encoding_used)`` tuple.

    Args:
        path: File to read.
        hint_encoding: Encoding to try first (e.g. from project config).
        errors: How to handle decode errors (``'replace'``, ``'ignore'``, ``'strict'``).
    """
    raw = Path(path).read_bytes()

    if hint_encoding:
        try:
            return raw.decode(hint_encoding, errors="strict"), hint_encoding
        except (UnicodeDecodeError, LookupError):
            pass

    detected = detect_encoding(raw)
    try:
        return raw.decode(detected, errors=errors), detected
    except (UnicodeDecodeError, LookupError):
        # Ultimate fallback
        return raw.decode("latin-1", errors="replace"), "latin-1"


def safe_decode(data: bytes, encoding: str = "utf-8", errors: str = "replace") -> str:
    """Decode *data* with *encoding*, falling back to latin-1 on failure."""
    try:
        return data.decode(encoding, errors=errors)
    except (UnicodeDecodeError, LookupError):
        return data.decode("latin-1", errors="replace")


def safe_encode(text: str, encoding: str = "utf-8", errors: str = "replace") -> bytes:
    """Encode *text* with *encoding*, replacing un-encodable characters."""
    try:
        return text.encode(encoding, errors=errors)
    except (UnicodeEncodeError, LookupError):
        return text.encode("utf-8", errors="replace")


def normalize_newlines(text: str, style: str = "\n") -> str:
    """
    Normalize line endings to *style* (default: Unix ``\n``).

    Handles ``\r\n``, ``\r``, and ``\n``.
    """
    # Replace Windows then old Mac line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if style != "\n":
        text = text.replace("\n", style)
    return text


def is_valid_utf8(data: bytes) -> bool:
    """Return True if *data* is valid UTF-8."""
    try:
        data.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def guess_language(path: str | Path) -> str:
    """
    Guess the programming language from a file extension.

    Returns a short language tag (e.g. ``'python'``, ``'typescript'``).
    """
    ext_map: dict[str, str] = {
        "py": "python",
        "pyw": "python",
        "ts": "typescript",
        "tsx": "typescript",
        "js": "javascript",
        "jsx": "javascript",
        "mjs": "javascript",
        "rb": "ruby",
        "go": "go",
        "rs": "rust",
        "java": "java",
        "kt": "kotlin",
        "swift": "swift",
        "c": "c",
        "h": "c",
        "cpp": "cpp",
        "cc": "cpp",
        "cxx": "cpp",
        "cs": "csharp",
        "sh": "bash",
        "bash": "bash",
        "zsh": "bash",
        "fish": "fish",
        "ps1": "powershell",
        "md": "markdown",
        "json": "json",
        "yaml": "yaml",
        "yml": "yaml",
        "toml": "toml",
        "xml": "xml",
        "html": "html",
        "htm": "html",
        "css": "css",
        "scss": "scss",
        "sql": "sql",
        "r": "r",
        "tf": "terraform",
        "hcl": "hcl",
        "lua": "lua",
        "vim": "vimscript",
        "dockerfile": "dockerfile",
    }
    p = Path(path)
    name = p.name.lower()
    if name in ("dockerfile", "makefile", "rakefile"):
        return name
    ext = p.suffix.lstrip(".").lower()
    return ext_map.get(ext, ext or "text")


__all__ = [
    "detect_encoding",
    "read_file_text",
    "safe_decode",
    "safe_encode",
    "normalize_newlines",
    "is_valid_utf8",
    "guess_language",
]
