"""
Python memdir subsystem — ported from 8 archived TypeScript modules.

Provides memory directory management:

- ``memdir``  MemoryEntry, MemoryType, MemoryDirectory, singleton
- ``paths``   Memory directory paths, team memory paths
"""
from __future__ import annotations

from .memdir import (
    MemoryDirectory,
    MemoryEntry,
    MemoryType,
    get_memory_directory,
)
from .paths import (
    TEAM_MEM_SUBDIR,
    ensure_mem_dirs,
    get_mem_dir,
    get_mem_dir_for_type,
    get_mem_index_path,
    get_shared_mem_dir,
    get_team_mem_dir,
)

import json as _json
from pathlib import Path as _Path

_SNAPSHOT_PATH = _Path(__file__).resolve().parent.parent / "reference_data" / "subsystems" / "memdir.json"
_SNAPSHOT = _json.loads(_SNAPSHOT_PATH.read_text())

ARCHIVE_NAME = _SNAPSHOT["archive_name"]
MODULE_COUNT = _SNAPSHOT["module_count"]
SAMPLE_FILES = tuple(_SNAPSHOT["sample_files"])
PORTING_NOTE = (
    f"Ported Python package for '{ARCHIVE_NAME}' — "
    f"{MODULE_COUNT} archived TypeScript modules → 2 Python memdir modules."
)

__all__ = [
    "MemoryDirectory",
    "MemoryEntry",
    "MemoryType",
    "get_memory_directory",
    "TEAM_MEM_SUBDIR",
    "ensure_mem_dirs",
    "get_mem_dir",
    "get_mem_dir_for_type",
    "get_mem_index_path",
    "get_shared_mem_dir",
    "get_team_mem_dir",
    "ARCHIVE_NAME",
    "MODULE_COUNT",
    "PORTING_NOTE",
    "SAMPLE_FILES",
]
