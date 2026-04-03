"""
Skill cache — fast in-memory and optional on-disk caching.

Ports: skills/skillCache.ts, skills/persistentCache.ts

Avoids repeated disk reads for frequently-used skills.
TTL-based expiry + LRU eviction to cap memory usage.
"""
from __future__ import annotations

import json
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

from .loader import Skill


# ---------------------------------------------------------------------------
# Cache entry
# ---------------------------------------------------------------------------

@dataclass
class CacheEntry:
    skill: Skill
    loaded_at: float = field(default_factory=time.time)
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.access_count += 1
        self.last_accessed = time.time()

    def is_expired(self, ttl_s: float) -> bool:
        return time.time() - self.loaded_at > ttl_s


# ---------------------------------------------------------------------------
# LRU skill cache
# ---------------------------------------------------------------------------

class SkillCache:
    """
    In-memory LRU cache for loaded Skill objects.

    Args:
        max_size: Maximum number of skills to cache.
        ttl_s: Time-to-live in seconds before a cached entry expires.
    """

    def __init__(self, max_size: int = 128, ttl_s: float = 300.0) -> None:
        self.max_size = max_size
        self.ttl_s = ttl_s
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()

    # ── Core operations ────────────────────────────────────────────────────

    def get(self, name: str) -> Skill | None:
        """Return cached skill or None if not present / expired."""
        entry = self._cache.get(name)
        if entry is None:
            return None
        if entry.is_expired(self.ttl_s):
            del self._cache[name]
            return None
        # LRU: move to end
        self._cache.move_to_end(name)
        entry.touch()
        return entry.skill

    def put(self, skill: Skill) -> None:
        """Insert or update a skill in the cache."""
        if skill.name in self._cache:
            self._cache.move_to_end(skill.name)
            entry = self._cache[skill.name]
            entry.skill = skill
            entry.loaded_at = time.time()
            return

        if len(self._cache) >= self.max_size:
            # Evict oldest
            self._cache.popitem(last=False)

        self._cache[skill.name] = CacheEntry(skill=skill)

    def invalidate(self, name: str) -> bool:
        """Remove a skill from the cache. Returns True if it was cached."""
        return self._cache.pop(name, None) is not None

    def clear(self) -> int:
        """Clear all entries. Returns the number evicted."""
        n = len(self._cache)
        self._cache.clear()
        return n

    def purge_expired(self) -> int:
        """Remove all expired entries. Returns the count removed."""
        now = time.time()
        expired = [k for k, v in self._cache.items() if now - v.loaded_at > self.ttl_s]
        for k in expired:
            del self._cache[k]
        return len(expired)

    # ── Metadata ──────────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, name: str) -> bool:
        return self.get(name) is not None

    def stats(self) -> dict:
        """Return cache statistics."""
        entries = list(self._cache.values())
        return {
            "size": len(entries),
            "max_size": self.max_size,
            "ttl_s": self.ttl_s,
            "total_accesses": sum(e.access_count for e in entries),
            "skills": sorted(self._cache.keys()),
        }


# ---------------------------------------------------------------------------
# Persistent disk cache (optional)
# ---------------------------------------------------------------------------

class PersistentSkillCache(SkillCache):
    """
    SkillCache with JSON persistence to disk.

    The cache file stores skill metadata (not full content) for warm startups.
    Full content is re-read from the source .md file on cache miss.
    """

    def __init__(
        self,
        cache_path: Path,
        max_size: int = 128,
        ttl_s: float = 300.0,
    ) -> None:
        super().__init__(max_size=max_size, ttl_s=ttl_s)
        self.cache_path = cache_path
        self._try_load()

    def _try_load(self) -> None:
        """Attempt to restore cache metadata from disk."""
        try:
            data = json.loads(self.cache_path.read_text())
            now = time.time()
            for item in data.get("entries", []):
                loaded_at = item.get("loaded_at", 0)
                if now - loaded_at < self.ttl_s:
                    skill = Skill(
                        name=item["name"],
                        description=item.get("description", ""),
                        content=item.get("content", ""),
                        source=item.get("source", "file"),
                        path=item.get("path", ""),
                        tags=item.get("tags", []),
                    )
                    entry = CacheEntry(skill=skill, loaded_at=loaded_at)
                    self._cache[skill.name] = entry
        except (OSError, json.JSONDecodeError, KeyError):
            pass

    def save(self) -> bool:
        """Persist cache metadata to disk."""
        try:
            entries = [
                {
                    "name": e.skill.name,
                    "description": e.skill.description,
                    "content": e.skill.content,
                    "source": e.skill.source,
                    "path": e.skill.path,
                    "tags": e.skill.tags,
                    "loaded_at": e.loaded_at,
                }
                for e in self._cache.values()
            ]
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(
                json.dumps({"entries": entries}, indent=2)
            )
            return True
        except OSError:
            return False


# ---------------------------------------------------------------------------
# Module-level default cache (singleton per process)
# ---------------------------------------------------------------------------

_default_cache: SkillCache | None = None


def get_default_cache(max_size: int = 128, ttl_s: float = 300.0) -> SkillCache:
    """Return (or create) the module-level default cache."""
    global _default_cache
    if _default_cache is None:
        _default_cache = SkillCache(max_size=max_size, ttl_s=ttl_s)
    return _default_cache


def reset_default_cache() -> None:
    """Reset the module-level cache (useful in tests)."""
    global _default_cache
    _default_cache = None


__all__ = [
    "CacheEntry",
    "SkillCache",
    "PersistentSkillCache",
    "get_default_cache",
    "reset_default_cache",
]
