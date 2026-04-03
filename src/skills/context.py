"""
Skill context injection — merge skill content into model context.

Ports: skills/skillContext.ts, skills/contextInjector.ts

Provides helpers that decide WHICH skills to inject for a given query,
and how to compose them into the final system prompt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .cache import get_default_cache
from .loader import Skill, resolve_skill
from .matcher import match_skills
from .registry import SkillRegistry, get_default_registry
from .types import SkillMatch


@dataclass
class InjectionPlan:
    """Describes which skills will be injected and why."""
    skills: list[Skill] = field(default_factory=list)
    matches: list[SkillMatch] = field(default_factory=list)
    total_chars: int = 0
    capped: bool = False


MAX_INJECTION_CHARS = 32_000   # rough context budget for injected skills


def plan_injection(
    query: str,
    registry: SkillRegistry | None = None,
    cwd: Path | None = None,
    top_k: int = 3,
    min_score: float = 0.2,
    char_budget: int = MAX_INJECTION_CHARS,
) -> InjectionPlan:
    """
    Decide which skills to inject for a given query.

    Selects top-K matching skills, then trims to stay within the
    char_budget to avoid blowing out the context window.

    Args:
        query: The user's message / intent.
        registry: Skill registry to search (uses default if None).
        cwd: Working directory for skill discovery.
        top_k: Max skills to consider.
        min_score: Minimum match score.
        char_budget: Maximum characters to inject.

    Returns:
        InjectionPlan.
    """
    reg = registry or get_default_registry(cwd)
    all_skills = reg.all_skills()

    matches = match_skills(query, skills=all_skills, top_k=top_k, min_score=min_score)

    plan = InjectionPlan(matches=matches)
    char_used = 0

    for match in matches:
        skill = reg.get(match.skill_name)
        if skill is None:
            skill = resolve_skill(match.skill_name, cwd=cwd)
        if skill is None:
            continue

        size = len(skill.content)
        if char_used + size > char_budget:
            plan.capped = True
            break

        plan.skills.append(skill)
        char_used += size

    plan.total_chars = char_used
    return plan


def build_injection_block(plan: InjectionPlan) -> str:
    """
    Build the string to prepend to the system prompt.

    Returns empty string if no skills were planned.
    """
    if not plan.skills:
        return ""

    blocks: list[str] = []
    for skill in plan.skills:
        blocks.append(f'<skill name="{skill.name}">\n{skill.content.strip()}\n</skill>')

    return "\n\n".join(blocks)


def inject_skills_into_system(
    query: str,
    system_prompt: str = "",
    registry: SkillRegistry | None = None,
    cwd: Path | None = None,
    top_k: int = 3,
    min_score: float = 0.2,
) -> tuple[str, InjectionPlan]:
    """
    One-step helper: plan + build + compose system prompt.

    Returns:
        (new_system_prompt, plan) where new_system_prompt has skill
        content prepended to *system_prompt*.
    """
    plan = plan_injection(
        query=query,
        registry=registry,
        cwd=cwd,
        top_k=top_k,
        min_score=min_score,
    )
    block = build_injection_block(plan)

    if block:
        new_system = block + ("\n\n" + system_prompt if system_prompt else "")
    else:
        new_system = system_prompt

    return new_system, plan


__all__ = [
    "InjectionPlan",
    "plan_injection",
    "build_injection_block",
    "inject_skills_into_system",
    "MAX_INJECTION_CHARS",
]
