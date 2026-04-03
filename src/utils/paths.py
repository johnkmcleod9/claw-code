"""
Path resolution and file-system helpers.

Ports: utils/Shell.ts (path portions), common file-system helpers
used throughout the Claude Code codebase.
"""
from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def resolve_path(path: str | Path, base: str | Path | None = None) -> Path:
    """
    Resolve a path relative to *base* (defaults to cwd).

    Handles ``~`` expansion and relative paths.
    """
    p = Path(path).expanduser()
    if p.is_absolute():
        return p.resolve()
    root = Path(base).expanduser() if base else Path.cwd()
    return (root / p).resolve()


def safe_relative(path: str | Path, base: str | Path) -> Path:
    """
    Return *path* relative to *base* if possible; otherwise return absolute.

    Does not raise ValueError like ``Path.relative_to`` does.
    """
    p = Path(path).resolve()
    b = Path(base).resolve()
    try:
        return p.relative_to(b)
    except ValueError:
        return p


def find_project_root(start: str | Path | None = None, markers: tuple[str, ...] = (".git", "pyproject.toml", "package.json", "CLAUDE.md", "AGENTS.md")) -> Path | None:
    """
    Walk up the directory tree to find a project root.

    Returns the first directory containing any of *markers*, or None.
    """
    current = Path(start or Path.cwd()).resolve()
    for ancestor in [current, *current.parents]:
        for marker in markers:
            if (ancestor / marker).exists():
                return ancestor
    return None


def ensure_dir(path: str | Path) -> Path:
    """Create directory (and parents) if it does not exist. Returns the Path."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def is_text_file(path: str | Path, sample_bytes: int = 8192) -> bool:
    """
    Heuristic check: is the file likely a text file?

    Reads up to *sample_bytes* and looks for null bytes.
    """
    p = Path(path)
    try:
        chunk = p.read_bytes()[:sample_bytes]
        return b"\x00" not in chunk
    except (OSError, PermissionError):
        return False


def is_executable(path: str | Path) -> bool:
    """Return True if the path is an executable file."""
    p = Path(path)
    return p.is_file() and bool(p.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))


def atomic_write(path: str | Path, content: str | bytes, encoding: str = "utf-8") -> None:
    """
    Write *content* to *path* atomically using a temp file + rename.

    Avoids partial-write issues on crash.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    is_bytes = isinstance(content, bytes)

    fd, tmp_path = tempfile.mkstemp(dir=p.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb" if is_bytes else "w", encoding=None if is_bytes else encoding) as fh:
            fh.write(content)
        os.replace(tmp_path, p)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def read_text_safe(path: str | Path, encoding: str = "utf-8", errors: str = "replace") -> str | None:
    """Read a text file; return None on any error."""
    try:
        return Path(path).read_text(encoding=encoding, errors=errors)
    except (OSError, PermissionError):
        return None


def write_text_safe(path: str | Path, content: str, encoding: str = "utf-8") -> bool:
    """Write text to a file; return False on error."""
    try:
        atomic_write(path, content, encoding=encoding)
        return True
    except Exception:
        return False


def glob_files(
    pattern: str,
    base: str | Path | None = None,
    exclude: tuple[str, ...] = ("**/node_modules/**", "**/.git/**", "**/__pycache__/**"),
) -> list[Path]:
    """
    Glob files matching *pattern* under *base*, excluding common noise dirs.

    Returns sorted list of matching paths.
    """
    root = Path(base or Path.cwd())
    matches = set(root.glob(pattern))
    for exc in exclude:
        matches -= set(root.glob(exc))
    return sorted(matches)


def file_size_str(size_bytes: int) -> str:
    """Human-readable file size string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes //= 1024
    return f"{size_bytes:.1f} PB"


def extension_of(path: str | Path) -> str:
    """Return lowercased extension without the dot, e.g. 'py', 'ts', ''."""
    return Path(path).suffix.lstrip(".").lower()


__all__ = [
    "resolve_path",
    "safe_relative",
    "find_project_root",
    "ensure_dir",
    "is_text_file",
    "is_executable",
    "atomic_write",
    "read_text_safe",
    "write_text_safe",
    "glob_files",
    "file_size_str",
    "extension_of",
]
