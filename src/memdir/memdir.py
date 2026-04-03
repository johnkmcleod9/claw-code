"""
Memory directory core types.

Ports: memdir/memdir.ts, memdir/memoryTypes.ts
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Memory types (memdir/memoryTypes.ts)
# ---------------------------------------------------------------------------

class MemoryType(str, Enum):
    """Classification of a memory entry."""
    EPISODIC   = "episodic"    # A specific event or conversation
    PROCEDURAL = "procedural"  # How to do something (steps, rules)
    SEMANTIC   = "semantic"    # Facts, concepts, definitions
    WORKING     = "working"     # Current task context (short-lived)
    TEAM       = "team"        # Shared across team members


@dataclass
class MemoryEntry:
    """
    A single memory item stored in the memory directory.

    Ports: memdir/memoryTypes.ts MemoryEntry
    """
    id: str
    content: str
    memory_type: MemoryType
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    importance: float = 1.0       # 0.0 – 1.0; higher = more important
    tags: list[str] = field(default_factory=list)
    source: str = ""              # file path, URL, or session ID
    embedding: list[float] | None = None  # vector for semantic search
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def age_hours(self) -> float:
        return (time.time() - self.created_at) / 3600

    @property
    def age_days(self) -> float:
        return self.age_hours / 24

    def relevance_score(self, query: str) -> float:
        """
        Simple keyword-overlap relevance score.

        Production systems would use vector similarity instead.
        """
        query_words = set(query.lower().split())
        content_words = set(self.content.lower().split())
        if not query_words:
            return 0.0
        overlap = len(query_words & content_words)
        return overlap / len(query_words)


# ---------------------------------------------------------------------------
# Memory directory (memdir/memdir.ts)
# ---------------------------------------------------------------------------

class MemoryDirectory:
    """
    In-memory directory of MemoryEntry objects.

    Ports: memdir/memdir.ts
    """

    def __init__(self, base_dir: str | Path | None = None) -> None:
        self._entries: dict[str, MemoryEntry] = {}
        self._base_dir = Path(base_dir) if base_dir else Path.home() / ".claw" / "memory"

    def add(self, entry: MemoryEntry) -> None:
        self._entries[entry.id] = entry

    def get(self, entry_id: str) -> MemoryEntry | None:
        return self._entries.get(entry_id)

    def remove(self, entry_id: str) -> bool:
        return self._entries.pop(entry_id, None) is not None

    def update(self, entry: MemoryEntry) -> None:
        entry.updated_at = time.time()
        self._entries[entry.id] = entry

    def list_all(self) -> list[MemoryEntry]:
        return list(self._entries.values())

    def list_by_type(self, memory_type: MemoryType) -> list[MemoryEntry]:
        return [e for e in self._entries.values() if e.memory_type == memory_type]

    def list_by_tag(self, tag: str) -> list[MemoryEntry]:
        return [e for e in self._entries.values() if tag in e.tags]

    def search(self, query: str, top_k: int = 10) -> list[tuple[MemoryEntry, float]]:
        """
        Search memories by keyword relevance.

        Returns (entry, score) tuples sorted by relevance descending.
        """
        scored = [
            (entry, entry.relevance_score(query))
            for entry in self._entries.values()
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def most_recent(self, n: int = 20) -> list[MemoryEntry]:
        return sorted(self._entries.values(), key=lambda e: e.created_at, reverse=True)[:n]

    def clear(self) -> None:
        self._entries.clear()

    @property
    def count(self) -> int:
        return len(self._entries)


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_memdir: MemoryDirectory | None = None


def get_memory_directory() -> MemoryDirectory:
    global _memdir
    if _memdir is None:
        _memdir = MemoryDirectory()
    return _memdir


__all__ = [
    "MemoryDirectory",
    "MemoryEntry",
    "MemoryType",
    "get_memory_directory",
]
