"""
Skill renderer — format skills for display in the terminal.

Ports: skills/skillRenderer.ts, skills/skillFormatter.ts

Produces human-readable summaries, detail views, and lists for CLI output.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

from .loader import Skill, list_skills
from .types import SkillMatch


# ANSI colour helpers (degrade gracefully when colours are disabled)
def _bold(s: str, use_colour: bool = True) -> str:
    return f"\033[1m{s}\033[0m" if use_colour else s

def _dim(s: str, use_colour: bool = True) -> str:
    return f"\033[2m{s}\033[0m" if use_colour else s

def _green(s: str, use_colour: bool = True) -> str:
    return f"\033[32m{s}\033[0m" if use_colour else s

def _yellow(s: str, use_colour: bool = True) -> str:
    return f"\033[33m{s}\033[0m" if use_colour else s

def _cyan(s: str, use_colour: bool = True) -> str:
    return f"\033[36m{s}\033[0m" if use_colour else s


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def format_skill_one_line(skill: Skill, *, colour: bool = True, width: int = 80) -> str:
    """
    Single-line format: ``name  —  description``

    Example::

        debug  —  Debug a failing test or runtime error
    """
    name_part = _bold(f"{skill.name:<20}", colour)
    desc = skill.description[:width - 22]
    return f"  {name_part} {_dim('—', colour)} {desc}"


def format_skill_detail(skill: Skill, *, colour: bool = True) -> str:
    """
    Multi-line detail view of a single skill.
    """
    lines: list[str] = []

    lines.append(_bold(f"Skill: {skill.name}", colour))
    lines.append("─" * 60)

    if skill.description:
        lines.append(f"Description : {skill.description}")

    source_label = {
        "file": "📄 File",
        "bundled": "📦 Bundled",
        "mcp": "🔌 MCP",
    }.get(skill.source, skill.source)

    lines.append(f"Source      : {source_label}")

    if skill.path:
        lines.append(f"Path        : {skill.path}")

    if skill.tags:
        lines.append(f"Tags        : {', '.join(skill.tags)}")

    lines.append("")
    content_preview = skill.content[:500].strip()
    if len(skill.content) > 500:
        content_preview += "\n  … (truncated)"
    lines.append(textwrap.indent(content_preview, "  "))

    return "\n".join(lines)


def format_skill_list(
    skills: list[Skill],
    *,
    colour: bool = True,
    header: str = "Available Skills",
    width: int = 80,
) -> str:
    """
    Format a list of skills for terminal display.
    """
    lines: list[str] = [_bold(header, colour), ""]
    if not skills:
        lines.append(_dim("  (no skills found)", colour))
    else:
        for skill in sorted(skills, key=lambda s: s.name):
            lines.append(format_skill_one_line(skill, colour=colour, width=width))
    lines.append("")
    lines.append(_dim(f"  {len(skills)} skill(s) total", colour))
    return "\n".join(lines)


def format_skill_matches(
    matches: list[SkillMatch],
    *,
    colour: bool = True,
) -> str:
    """
    Format match results for terminal display.
    """
    if not matches:
        return _dim("No matching skills found.", colour)

    lines = [_bold("Skill Matches", colour), ""]
    for i, match in enumerate(matches, 1):
        score_bar = _green("█" * int(match.score * 10), colour) + _dim("░" * (10 - int(match.score * 10)), colour)
        lines.append(f"  {i}. {_bold(match.skill_name, colour)}")
        lines.append(f"     Score: {score_bar} {match.score:.2f}")
        if match.reason:
            lines.append(f"     Reason: {_dim(match.reason, colour)}")
        lines.append("")

    return "\n".join(lines)


def format_injection_block(
    skill_name: str,
    content: str,
    *,
    colour: bool = True,
) -> str:
    """
    Show what would be injected into the system prompt.
    """
    header = _cyan(f"<skill name=\"{skill_name}\">", colour)
    footer = _cyan("</skill>", colour)
    return f"{header}\n{content.strip()}\n{footer}"


__all__ = [
    "format_skill_one_line",
    "format_skill_detail",
    "format_skill_list",
    "format_skill_matches",
    "format_injection_block",
]
