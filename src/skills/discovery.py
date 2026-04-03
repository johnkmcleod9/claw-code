"""
Skill discovery engine.

Ports: skills/discoverSkills.ts, skills/skillIndex.ts

Scans all registered skill directories, builds an in-memory index, and
detects newly-added or removed skill files via inode/mtime comparison.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from .loader import Skill, find_skill_dirs, load_skill_from_path
from .types import SkillEvent, SkillSource


@dataclass
class SkillIndexEntry:
    """Single entry in the skill index."""
    name: str
    path: str
    source: str
    mtime: float = 0.0
    content_hash: str = ""
    description: str = ""


@dataclass
class SkillIndex:
    """
    In-memory index of all discovered skills, keyed by name.

    Supports incremental refresh — only re-reads files that changed.
    """
    entries: dict[str, SkillIndexEntry] = field(default_factory=dict)
    last_scan: float = 0.0
    scan_dirs: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.entries)

    def names(self) -> list[str]:
        return sorted(self.entries.keys())

    def get(self, name: str) -> SkillIndexEntry | None:
        return self.entries.get(name)

    def add(self, entry: SkillIndexEntry) -> None:
        self.entries[entry.name] = entry

    def remove(self, name: str) -> bool:
        return self.entries.pop(name, None) is not None


def _content_hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:12]


def build_skill_index(
    cwd: Path | None = None,
    extra_dirs: list[Path] | None = None,
) -> SkillIndex:
    """
    Build a fresh skill index by scanning all skill directories.

    Args:
        cwd: Working directory for project-local skill discovery.
        extra_dirs: Additional directories to include.

    Returns:
        Populated SkillIndex.
    """
    dirs = find_skill_dirs(cwd)
    if extra_dirs:
        dirs.extend(extra_dirs)

    index = SkillIndex(
        scan_dirs=[str(d) for d in dirs],
        last_scan=time.time(),
    )
    seen: set[str] = set()

    for dir_path in dirs:
        if not dir_path.is_dir():
            continue
        for md_path in sorted(dir_path.glob("*.md")):
            skill = load_skill_from_path(md_path)
            if skill and skill.name not in seen:
                seen.add(skill.name)
                try:
                    mtime = md_path.stat().st_mtime
                except OSError:
                    mtime = 0.0
                index.add(SkillIndexEntry(
                    name=skill.name,
                    path=str(md_path),
                    source=skill.source,
                    mtime=mtime,
                    content_hash=_content_hash(skill.content),
                    description=skill.description,
                ))

    return index


def refresh_skill_index(
    index: SkillIndex,
    cwd: Path | None = None,
) -> tuple[list[SkillEvent], SkillIndex]:
    """
    Incrementally refresh an existing index.

    Returns:
        A tuple of (events, updated_index).
        Events include "skill_added", "skill_updated", "skill_removed".
    """
    events: list[SkillEvent] = []
    new_index = build_skill_index(cwd=cwd)

    old_names = set(index.entries.keys())
    new_names = set(new_index.entries.keys())

    for name in new_names - old_names:
        events.append(SkillEvent("skill_added", name))

    for name in old_names - new_names:
        events.append(SkillEvent("skill_removed", name))

    for name in old_names & new_names:
        old_entry = index.entries[name]
        new_entry = new_index.entries[name]
        if old_entry.content_hash != new_entry.content_hash:
            events.append(SkillEvent("skill_updated", name))

    return events, new_index


def iter_skills_from_index(index: SkillIndex) -> Iterator[tuple[str, SkillIndexEntry]]:
    """Iterate over (name, entry) pairs sorted by name."""
    for name in index.names():
        yield name, index.entries[name]


__all__ = [
    "SkillIndex",
    "SkillIndexEntry",
    "build_skill_index",
    "refresh_skill_index",
    "iter_skills_from_index",
]
