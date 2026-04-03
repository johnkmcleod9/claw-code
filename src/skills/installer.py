"""
Skill installer — install, remove, and update skill files.

Ports: skills/installSkill.ts, skills/skillUpdater.ts

Handles copying .md skill files into a target skill directory,
version checking, and safe removal.
"""
from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from .loader import load_skill_from_path, Skill
from .validator import validate_skill_file, ValidationResult


GLOBAL_SKILLS_DIR = Path.home() / ".claw-code" / "skills"


@dataclass
class InstallResult:
    success: bool
    skill_name: str
    dest_path: str
    error: str = ""
    was_upgrade: bool = False


def install_skill(
    source_path: Path,
    dest_dir: Path | None = None,
    *,
    overwrite: bool = True,
    validate: bool = True,
) -> InstallResult:
    """
    Install a skill from *source_path* into *dest_dir*.

    Args:
        source_path: Path to the .md skill file to install.
        dest_dir: Target directory. Defaults to GLOBAL_SKILLS_DIR.
        overwrite: Replace existing skill if True.
        validate: Validate the skill before installing.

    Returns:
        InstallResult.
    """
    dest_dir = dest_dir or GLOBAL_SKILLS_DIR
    skill_name = source_path.stem

    if validate:
        vr = validate_skill_file(source_path)
        if not vr.valid:
            return InstallResult(
                success=False,
                skill_name=skill_name,
                dest_path="",
                error="; ".join(vr.errors),
            )

    dest_path = dest_dir / source_path.name
    was_upgrade = dest_path.exists()

    if was_upgrade and not overwrite:
        return InstallResult(
            success=False,
            skill_name=skill_name,
            dest_path=str(dest_path),
            error="Skill already installed. Use overwrite=True to upgrade.",
        )

    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest_path)
    except (OSError, shutil.Error) as exc:
        return InstallResult(
            success=False,
            skill_name=skill_name,
            dest_path=str(dest_path),
            error=str(exc),
        )

    return InstallResult(
        success=True,
        skill_name=skill_name,
        dest_path=str(dest_path),
        was_upgrade=was_upgrade,
    )


def uninstall_skill(
    skill_name: str,
    skill_dir: Path | None = None,
) -> bool:
    """
    Remove a skill file from the skill directory.

    Args:
        skill_name: Name of the skill (without .md extension).
        skill_dir: Directory to search. Defaults to GLOBAL_SKILLS_DIR.

    Returns:
        True if the file was found and removed.
    """
    skill_dir = skill_dir or GLOBAL_SKILLS_DIR
    path = skill_dir / f"{skill_name}.md"
    if path.exists():
        path.unlink()
        return True
    return False


def list_installed_skills(skill_dir: Path | None = None) -> list[Path]:
    """Return sorted list of installed .md skill file paths."""
    skill_dir = skill_dir or GLOBAL_SKILLS_DIR
    if not skill_dir.is_dir():
        return []
    return sorted(skill_dir.glob("*.md"))


def backup_skill(
    skill_name: str,
    skill_dir: Path | None = None,
) -> Path | None:
    """
    Create a timestamped backup of an existing skill file.

    Returns the backup path, or None if the source was not found.
    """
    skill_dir = skill_dir or GLOBAL_SKILLS_DIR
    src = skill_dir / f"{skill_name}.md"
    if not src.exists():
        return None
    ts = int(time.time())
    backup = skill_dir / f"{skill_name}.{ts}.bak.md"
    shutil.copy2(src, backup)
    return backup


__all__ = [
    "InstallResult",
    "install_skill",
    "uninstall_skill",
    "list_installed_skills",
    "backup_skill",
    "GLOBAL_SKILLS_DIR",
]
