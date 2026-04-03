"""
Skill directory loader.

Ports: skills/loadSkillsDir.ts, skills/bundledSkills.ts
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Skill:
    """A single skill — loaded from a .md file or bundled."""
    name: str
    description: str = ""
    content: str = ""
    source: str = ""  # "file", "bundled", "mcp"
    path: str = ""
    tags: list[str] = field(default_factory=list)

    def is_bundled(self) -> bool:
        return self.source == "bundled"


# ---------------------------------------------------------------------------
# Skill directory scanning
# ---------------------------------------------------------------------------

GLOBAL_SKILLS_DIR = Path.home() / ".claw-code" / "skills"
GLOBAL_SKILLS_DIR_LEGACY = Path.home() / ".clawd" / "skills"


def find_skill_dirs(cwd: Path | None = None) -> list[Path]:
    """
    Find all skill search directories ordered by priority:
    1. Project-local ./skills/
    2. Nearest ancestor ./skills/ (outside project root)
    3. ~/.clawd/skills/ (legacy global)
    4. ~/.claw-code/skills/ (global)
    """
    root = cwd or Path.cwd()
    dirs: list[Path] = []

    # Project-local
    local = root / "skills"
    if local.is_dir():
        dirs.append(local)

    # Walk up for nearest ancestor skills
    parent = root.parent
    while parent != parent.parent:
        candidate = parent / "skills"
        if candidate.is_dir() and candidate not in dirs:
            dirs.append(candidate)
            break
        parent = parent.parent

    # Global dirs
    for gdir in (GLOBAL_SKILLS_DIR_LEGACY, GLOBAL_SKILLS_DIR):
        if gdir.is_dir() and gdir not in dirs:
            dirs.append(gdir)

    return dirs


def load_skill_from_path(path: Path) -> Skill | None:
    """Load a single skill from a .md file."""
    if path.suffix.lower() != ".md":
        return None
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return None

    lines = raw.splitlines()
    name = path.stem
    description = ""

    # Use first non-empty line as description (strip markdown heading)
    for line in lines:
        stripped = line.strip()
        if stripped:
            if stripped.startswith("#"):
                stripped = stripped.lstrip("#").strip()
            description = stripped[:200]
            break

    return Skill(
        name=name,
        description=description,
        content=raw,
        source="file",
        path=str(path),
    )


def scan_skill_dir(dir_path: Path) -> list[Skill]:
    """Scan a skill directory and return all found skills."""
    skills: list[Skill] = []
    if not dir_path.is_dir():
        return skills
    for md_file in sorted(dir_path.glob("*.md")):
        skill = load_skill_from_path(md_file)
        if skill:
            skills.append(skill)
    return skills


def list_skills(cwd: Path | None = None) -> list[Skill]:
    """
    Find and load all available skills from all search directories.

    Skills from earlier directories in the search path take precedence.
    """
    skills: list[Skill] = []
    seen: set[str] = set()

    for dir_path in find_skill_dirs(cwd):
        for skill in scan_skill_dir(dir_path):
            if skill.name not in seen:
                seen.add(skill.name)
                skills.append(skill)

    return skills


def resolve_skill(name: str, cwd: Path | None = None) -> Skill | None:
    """Find a skill by name, searching in priority order."""
    for dir_path in find_skill_dirs(cwd):
        path = dir_path / f"{name}.md"
        if path.exists():
            return load_skill_from_path(path)
    return None


# ---------------------------------------------------------------------------
# Search / filter
# ---------------------------------------------------------------------------

def search_skills(
    query: str,
    cwd: Path | None = None,
    tags: list[str] | None = None,
    limit: int = 20,
) -> list[Skill]:
    """
    Search skills by name or description.

    Args:
        query: Substring to match in name or description.
        cwd: Working directory for skill search.
        tags: Filter to skills with any of these tags.
        limit: Maximum results to return.
    """
    q = query.lower().strip()
    all_skills = list_skills(cwd)

    results: list[tuple[int, Skill]] = []  # (score, skill)

    for skill in all_skills:
        if tags:
            if not any(t in skill.tags for t in tags):
                continue

        if not q:
            results.append((0, skill))
            continue

        name_match = skill.name.lower().count(q)
        desc_match = skill.description.lower().count(q)
        score = name_match * 3 + desc_match

        if score > 0:
            results.append((score, skill))

    results.sort(key=lambda x: -x[0])
    return [s for _, s in results[:limit]]


__all__ = [
    "Skill",
    "find_skill_dirs",
    "scan_skill_dir",
    "list_skills",
    "resolve_skill",
    "search_skills",
]
