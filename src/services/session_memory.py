"""
Session memory service — persist and recall facts across sessions.

Ports: services/SessionMemory/sessionMemory.ts,
       services/SessionMemory/sessionMemoryUtils.ts,
       services/SessionMemory/prompts.ts
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MemoryEntry:
    """A single remembered fact."""
    key: str
    value: str
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryEntry":
        return cls(
            key=data["key"],
            value=data["value"],
            tags=data.get("tags", []),
            created_at=data.get("created_at", 0.0),
            updated_at=data.get("updated_at", 0.0),
        )


@dataclass
class SessionMemory:
    """
    Persistent key-value memory store for a session or project.

    Backed by a JSON file; survives restarts.
    """

    _entries: dict[str, MemoryEntry] = field(default_factory=dict)
    _path: Path | None = field(default=None, repr=False)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path) -> "SessionMemory":
        """Load from a JSON file, creating an empty store if it doesn't exist."""
        p = Path(path)
        obj = cls(_path=p)
        if p.exists():
            try:
                data = json.loads(p.read_text())
                obj._entries = {
                    k: MemoryEntry.from_dict(v) for k, v in data.get("entries", {}).items()
                }
            except (json.JSONDecodeError, KeyError):
                pass  # corrupt file → start fresh
        return obj

    def save(self) -> None:
        """Persist to disk (no-op if no path was set)."""
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {"entries": {k: v.to_dict() for k, v in self._entries.items()}}
        self._path.write_text(json.dumps(data, indent=2))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def set(self, key: str, value: str, tags: list[str] | None = None) -> None:
        """Store a fact. Creates or updates the entry."""
        now = time.time()
        if key in self._entries:
            self._entries[key].value = value
            self._entries[key].updated_at = now
            if tags is not None:
                self._entries[key].tags = tags
        else:
            self._entries[key] = MemoryEntry(
                key=key, value=value, tags=tags or [], created_at=now, updated_at=now
            )

    def get(self, key: str, default: str | None = None) -> str | None:
        """Return the value for *key* or *default*."""
        entry = self._entries.get(key)
        return entry.value if entry else default

    def delete(self, key: str) -> bool:
        """Remove an entry. Returns True if it existed."""
        return self._entries.pop(key, None) is not None

    def search(self, query: str, tag: str | None = None) -> list[MemoryEntry]:
        """
        Find entries whose key or value contains *query* (case-insensitive).
        Optionally filter by *tag*.
        """
        q = query.lower()
        results = []
        for entry in self._entries.values():
            if tag and tag not in entry.tags:
                continue
            if q in entry.key.lower() or q in entry.value.lower():
                results.append(entry)
        return results

    def all_entries(self) -> list[MemoryEntry]:
        """Return all entries sorted by key."""
        return sorted(self._entries.values(), key=lambda e: e.key)

    def by_tag(self, tag: str) -> list[MemoryEntry]:
        """Return entries with the given tag."""
        return [e for e in self._entries.values() if tag in e.tags]

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, key: str) -> bool:
        return key in self._entries

    # ------------------------------------------------------------------
    # Prompt generation (ports SessionMemory/prompts.ts)
    # ------------------------------------------------------------------

    def to_context_block(self, max_entries: int = 20) -> str:
        """
        Format memory entries as a markdown block suitable for injection
        into an LLM system prompt.
        """
        entries = self.all_entries()[:max_entries]
        if not entries:
            return ""
        lines = ["<session_memory>"]
        for e in entries:
            tag_str = f" [{', '.join(e.tags)}]" if e.tags else ""
            lines.append(f"  {e.key}{tag_str}: {e.value}")
        lines.append("</session_memory>")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# In-memory convenience instance (non-persistent)
# ---------------------------------------------------------------------------

def make_memory(path: str | Path | None = None) -> SessionMemory:
    """Create a SessionMemory, optionally backed by *path*."""
    if path:
        return SessionMemory.load(path)
    return SessionMemory()


__all__ = [
    "MemoryEntry",
    "SessionMemory",
    "make_memory",
]
