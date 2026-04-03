"""
Skill CLI command handlers.

Ports: skills/cliSkillCommands.ts, skills/skillCommandParser.ts

Provides handler functions for /skills, /skill-use, /skill-list, etc.
These are invoked by the main CLI command dispatcher.
"""
from __future__ import annotations

from pathlib import Path

from .cache import get_default_cache
from .installer import install_skill, uninstall_skill, list_installed_skills
from .loader import list_skills, resolve_skill
from .matcher import match_skills
from .registry import get_default_registry
from .renderer import (
    format_skill_detail,
    format_skill_list,
    format_skill_matches,
)
from .validator import validate_skill_file


def cmd_skills_list(cwd: Path | None = None, *, colour: bool = True) -> str:
    """
    Handle: /skills  or  /skills list

    Returns formatted list of available skills.
    """
    skills = list_skills(cwd)
    return format_skill_list(skills, colour=colour)


def cmd_skills_show(name: str, cwd: Path | None = None, *, colour: bool = True) -> str:
    """
    Handle: /skills show <name>

    Returns detail view of a single skill.
    """
    skill = resolve_skill(name, cwd=cwd)
    if skill is None:
        return f"Skill '{name}' not found."
    return format_skill_detail(skill, colour=colour)


def cmd_skills_search(query: str, cwd: Path | None = None, *, colour: bool = True) -> str:
    """
    Handle: /skills search <query>

    Returns matched skills.
    """
    skills = list_skills(cwd)
    matches = match_skills(query, skills=skills, top_k=10, min_score=0.05)
    return format_skill_matches(matches, colour=colour)


def cmd_skills_validate(path_str: str, *, colour: bool = True) -> str:
    """
    Handle: /skills validate <path>

    Validates a skill .md file and reports issues.
    """
    path = Path(path_str).expanduser()
    vr = validate_skill_file(path)
    lines: list[str] = [f"Validating: {path.name}", ""]

    if vr.valid:
        lines.append("✅ Skill is valid.")
    else:
        lines.append("❌ Skill has errors:")
        for err in vr.errors:
            lines.append(f"  • {err}")

    if vr.warnings:
        lines.append("\n⚠️  Warnings:")
        for warn in vr.warnings:
            lines.append(f"  • {warn}")

    return "\n".join(lines)


def cmd_skills_install(path_str: str, *, colour: bool = True) -> str:
    """
    Handle: /skills install <path>

    Installs a skill file to the global skill directory.
    """
    path = Path(path_str).expanduser()
    result = install_skill(path)
    if result.success:
        action = "upgraded" if result.was_upgrade else "installed"
        return f"✅ Skill '{result.skill_name}' {action} → {result.dest_path}"
    return f"❌ Install failed: {result.error}"


def cmd_skills_uninstall(name: str, *, colour: bool = True) -> str:
    """
    Handle: /skills uninstall <name>

    Removes a skill from the global skill directory.
    """
    removed = uninstall_skill(name)
    if removed:
        return f"✅ Skill '{name}' removed."
    return f"Skill '{name}' was not installed."


def cmd_skills_cache_stats(*, colour: bool = True) -> str:
    """
    Handle: /skills cache

    Returns skill cache statistics.
    """
    stats = get_default_cache().stats()
    lines = ["Skill Cache Stats", "─" * 30]
    for k, v in stats.items():
        if k == "skills":
            lines.append(f"  cached skills : {', '.join(v) or '(none)'}")
        else:
            lines.append(f"  {k:<18}: {v}")
    return "\n".join(lines)


def dispatch_skill_command(
    command: str,
    args: list[str],
    cwd: Path | None = None,
    colour: bool = True,
) -> str:
    """
    Dispatch a skill sub-command.

    Args:
        command: Sub-command name (list, show, search, validate, install, uninstall, cache).
        args: Remaining arguments.
        cwd: Working directory.
        colour: Enable ANSI colour output.

    Returns:
        Response string.
    """
    cmd = command.lower().strip()

    if cmd in ("", "list"):
        return cmd_skills_list(cwd=cwd, colour=colour)
    elif cmd == "show" and args:
        return cmd_skills_show(args[0], cwd=cwd, colour=colour)
    elif cmd == "search" and args:
        return cmd_skills_search(" ".join(args), cwd=cwd, colour=colour)
    elif cmd == "validate" and args:
        return cmd_skills_validate(args[0], colour=colour)
    elif cmd == "install" and args:
        return cmd_skills_install(args[0], colour=colour)
    elif cmd == "uninstall" and args:
        return cmd_skills_uninstall(args[0], colour=colour)
    elif cmd == "cache":
        return cmd_skills_cache_stats(colour=colour)
    else:
        return (
            "Usage: /skills [list|show <name>|search <query>|"
            "validate <path>|install <path>|uninstall <name>|cache]"
        )


__all__ = [
    "cmd_skills_list",
    "cmd_skills_show",
    "cmd_skills_search",
    "cmd_skills_validate",
    "cmd_skills_install",
    "cmd_skills_uninstall",
    "cmd_skills_cache_stats",
    "dispatch_skill_command",
]
