"""
Skill registry — central registration and lookup for all skills.

Ports: skills/skillRegistry.ts, skills/skillStore.ts

Maintains the authoritative map of name → Skill for a session.
Integrates with bundled skills, file-based skills, and MCP skills.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from .bundled import list_bundled_skills
from .cache import SkillCache, get_default_cache
from .discovery import build_skill_index
from .loader import Skill, list_skills, resolve_skill
from .types import SkillEvent


@dataclass
class RegistryStats:
    total: int = 0
    from_file: int = 0
    from_bundled: int = 0
    from_mcp: int = 0
    from_cache: int = 0


class SkillRegistry:
    """
    Thread-safe registry of Skill objects for a session.

    Skills from later calls to register() do NOT override earlier ones
    unless force=True, preserving priority semantics.
    """

    def __init__(
        self,
        cache: SkillCache | None = None,
        include_bundled: bool = True,
    ) -> None:
        self._skills: dict[str, Skill] = {}
        self._lock = threading.Lock()
        self.cache = cache or get_default_cache()
        self._events: list[SkillEvent] = []

        if include_bundled:
            for skill in list_bundled_skills():
                self._skills[skill.name] = skill

    # ── Registration ──────────────────────────────────────────────────────

    def register(self, skill: Skill, force: bool = False) -> bool:
        """
        Register a skill.

        Args:
            skill: The Skill to register.
            force: Overwrite existing registration if True.

        Returns:
            True if the skill was registered, False if skipped.
        """
        with self._lock:
            if skill.name in self._skills and not force:
                return False
            self._skills[skill.name] = skill
            self.cache.put(skill)
            self._events.append(SkillEvent("registered", skill.name))
            return True

    def register_all(self, skills: list[Skill], force: bool = False) -> int:
        """Bulk-register skills. Returns the count actually registered."""
        return sum(self.register(s, force=force) for s in skills)

    def unregister(self, name: str) -> bool:
        """Remove a skill from the registry. Returns True if it was present."""
        with self._lock:
            existed = name in self._skills
            self._skills.pop(name, None)
            self.cache.invalidate(name)
            if existed:
                self._events.append(SkillEvent("unregistered", name))
            return existed

    # ── Lookup ────────────────────────────────────────────────────────────

    def get(self, name: str) -> Skill | None:
        """Return a skill by name, or None."""
        with self._lock:
            return self._skills.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._skills

    def __len__(self) -> int:
        return len(self._skills)

    def __iter__(self) -> Iterator[Skill]:
        return iter(list(self._skills.values()))

    def names(self) -> list[str]:
        return sorted(self._skills.keys())

    def all_skills(self) -> list[Skill]:
        return list(self._skills.values())

    # ── Loading helpers ───────────────────────────────────────────────────

    def load_from_disk(self, cwd: Path | None = None) -> int:
        """
        Scan disk for skills and register them (lower priority than already-registered).

        Returns the number of newly registered skills.
        """
        disk_skills = list_skills(cwd)
        return self.register_all(disk_skills, force=False)

    def load_skill_by_name(self, name: str, cwd: Path | None = None) -> Skill | None:
        """
        Resolve and register a skill by name (file or bundled).

        Returns the Skill if found and registered, else None.
        """
        if name in self._skills:
            return self._skills[name]
        skill = resolve_skill(name, cwd=cwd)
        if skill:
            self.register(skill, force=True)
        return skill

    # ── Introspection ─────────────────────────────────────────────────────

    def stats(self) -> RegistryStats:
        stats = RegistryStats(total=len(self._skills))
        for skill in self._skills.values():
            if skill.source == "file":
                stats.from_file += 1
            elif skill.source == "bundled":
                stats.from_bundled += 1
            elif skill.source == "mcp":
                stats.from_mcp += 1
        return stats

    def drain_events(self) -> list[SkillEvent]:
        """Return and clear accumulated lifecycle events."""
        with self._lock:
            events = list(self._events)
            self._events.clear()
            return events


# ---------------------------------------------------------------------------
# Module-level default registry
# ---------------------------------------------------------------------------

_default_registry: SkillRegistry | None = None


def get_default_registry(cwd: Path | None = None) -> SkillRegistry:
    """Return (or create) the module-level default registry, loading from disk."""
    global _default_registry
    if _default_registry is None:
        _default_registry = SkillRegistry()
        _default_registry.load_from_disk(cwd)
    return _default_registry


def reset_default_registry() -> None:
    """Reset the module-level registry (useful in tests)."""
    global _default_registry
    _default_registry = None


__all__ = [
    "SkillRegistry",
    "RegistryStats",
    "get_default_registry",
    "reset_default_registry",
]
