"""
Python utils subsystem — ported from 564 archived TypeScript modules.

This package provides core utilities used throughout the claw-code project:

- ``collections``  CircularBuffer, QueryGuard, LRUCache, FrozenDict
- ``encoding``     Encoding detection, safe text I/O, language guessing
- ``http``         HTTP request helpers with retry support
- ``ids``          Session/agent ID generation
- ``logging``      Consistent log formatting
- ``paths``        Path resolution, file helpers, atomic writes
- ``retry``        Retry/backoff decorators and CircuitBreaker
- ``shell``        Subprocess helpers (sync + async)
- ``strings``      String manipulation, argument substitution, array helpers
"""
from __future__ import annotations

# Re-export the most commonly needed symbols for convenience.
from .collections import CircularBuffer, LRUCache, QueryGuard
from .encoding import detect_encoding, guess_language, read_file_text, safe_decode
from .http import HttpResponse, build_url, http_get, http_post
from .ids import agent_id, new_session_id, new_short_id, timestamp_id
from .logging import configure_logging, get_logger
from .paths import (
    atomic_write,
    ensure_dir,
    extension_of,
    file_size_str,
    find_project_root,
    glob_files,
    is_text_file,
    read_text_safe,
    resolve_path,
    safe_relative,
    write_text_safe,
)
from .retry import CircuitBreaker, RetryExhausted, retry_async, retry_sync, with_retry
from .shell import ShellResult, git_root, run, run_async, which
from .strings import (
    camel_to_snake,
    chunk,
    extract_code_blocks,
    first_line,
    flatten,
    format_count,
    indent,
    line_count,
    pluralize,
    slug,
    snake_to_camel,
    strip_ansi,
    substitute_args,
    truncate,
    truncate_lines,
    unique,
    word_count,
)

# Backward-compat shim: keep the old archive metadata accessible
from pathlib import Path as _Path
import json as _json

_SNAPSHOT_PATH = _Path(__file__).resolve().parent.parent / "reference_data" / "subsystems" / "utils.json"
_SNAPSHOT = _json.loads(_SNAPSHOT_PATH.read_text())

ARCHIVE_NAME = _SNAPSHOT["archive_name"]
MODULE_COUNT = _SNAPSHOT["module_count"]
SAMPLE_FILES = tuple(_SNAPSHOT["sample_files"])
PORTING_NOTE = (
    f"Ported Python package for '{ARCHIVE_NAME}' — "
    f"{MODULE_COUNT} archived TypeScript modules → 9 Python utility modules."
)

__all__ = [
    # collections
    "CircularBuffer",
    "LRUCache",
    "QueryGuard",
    # encoding
    "detect_encoding",
    "guess_language",
    "read_file_text",
    "safe_decode",
    # http
    "HttpResponse",
    "build_url",
    "http_get",
    "http_post",
    # ids
    "agent_id",
    "new_session_id",
    "new_short_id",
    "timestamp_id",
    # logging
    "configure_logging",
    "get_logger",
    # paths
    "atomic_write",
    "ensure_dir",
    "extension_of",
    "file_size_str",
    "find_project_root",
    "glob_files",
    "is_text_file",
    "read_text_safe",
    "resolve_path",
    "safe_relative",
    "write_text_safe",
    # retry
    "CircuitBreaker",
    "RetryExhausted",
    "retry_async",
    "retry_sync",
    "with_retry",
    # shell
    "ShellResult",
    "git_root",
    "run",
    "run_async",
    "which",
    # strings
    "camel_to_snake",
    "chunk",
    "extract_code_blocks",
    "first_line",
    "flatten",
    "format_count",
    "indent",
    "line_count",
    "pluralize",
    "slug",
    "snake_to_camel",
    "strip_ansi",
    "substitute_args",
    "truncate",
    "truncate_lines",
    "unique",
    "word_count",
    # legacy archive metadata
    "ARCHIVE_NAME",
    "MODULE_COUNT",
    "PORTING_NOTE",
    "SAMPLE_FILES",
]
