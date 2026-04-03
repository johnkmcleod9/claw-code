"""
Memory directory paths.

Ports: memdir/paths.ts, memdir/teamMemPaths.ts
"""
from __future__ import annotations

import os
from pathlib import Path


# ---------------------------------------------------------------------------
# Base paths (memdir/paths.ts)
# ---------------------------------------------------------------------------

def get_mem_dir() -> Path:
    """Return the memory directory root (``~/.claw/memory``)."""
    return Path(os.environ.get("CLAW_MEM_DIR", Path.home() / ".claw" / "memory"))


def get_mem_index_path() -> Path:
    """Return the path to the memory index file."""
    return get_mem_dir() / "index.json"


def get_mem_dir_for_type(memory_type: str) -> Path:
    """Return the sub-directory for a given memory type."""
    d = get_mem_dir() / "types" / memory_type
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Team memory paths (memdir/teamMemPaths.ts)
# ---------------------------------------------------------------------------

TEAM_MEM_SUBDIR = "team-memory"


def get_team_mem_dir(team_id: str | None = None) -> Path:
    """
    Return the team memory directory.

    If *team_id* is None, returns the shared team root.
    """
    base = get_mem_dir() / TEAM_MEM_SUBDIR
    if team_id:
        return base / team_id
    return base


def get_shared_mem_dir() -> Path:
    """Return the directory for memories shared across all team members."""
    return get_team_mem_dir() / "shared"


# ---------------------------------------------------------------------------
# Ensure directories exist
# ---------------------------------------------------------------------------

def ensure_mem_dirs() -> None:
    """Create all memory directories if they don't exist."""
    get_mem_dir().mkdir(parents=True, exist_ok=True)
    for subdir in ["types", TEAM_MEM_SUBDIR]:
        (get_mem_dir() / subdir).mkdir(parents=True, exist_ok=True)


__all__ = [
    "TEAM_MEM_SUBDIR",
    "ensure_mem_dirs",
    "get_mem_dir",
    "get_mem_dir_for_type",
    "get_mem_index_path",
    "get_shared_mem_dir",
    "get_team_mem_dir",
]
