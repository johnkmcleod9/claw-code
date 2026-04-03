"""
Skill template engine — variable substitution in skill content.

Ports: skills/skillTemplate.ts

Supports ``{{variable}}`` placeholders in skill markdown.
Used to personalise bundled or shared skills at runtime.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .loader import Skill


_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


@dataclass
class TemplateResult:
    content: str
    filled: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


def render_skill_template(
    skill: Skill,
    variables: dict[str, str],
    strict: bool = False,
) -> TemplateResult:
    """
    Render a skill's content by substituting ``{{variable}}`` placeholders.

    Args:
        skill: The skill to render.
        variables: Mapping of variable name → value.
        strict: If True, raise KeyError for any missing variable.

    Returns:
        TemplateResult with filled content and lists of filled/missing vars.
    """
    filled: list[str] = []
    missing: list[str] = []

    def replacer(match: re.Match) -> str:
        key = match.group(1)
        if key in variables:
            filled.append(key)
            return variables[key]
        missing.append(key)
        if strict:
            raise KeyError(f"Missing template variable: '{key}'")
        return match.group(0)  # leave placeholder intact

    content = _PLACEHOLDER_RE.sub(replacer, skill.content)
    return TemplateResult(content=content, filled=filled, missing=list(set(missing)))


def extract_template_variables(skill: Skill) -> list[str]:
    """
    Return all ``{{variable}}`` names found in a skill's content.
    """
    return list(dict.fromkeys(_PLACEHOLDER_RE.findall(skill.content)))


def render_template_string(template: str, variables: dict[str, str]) -> str:
    """
    Render a raw template string (no Skill wrapper needed).
    """
    def replacer(match: re.Match) -> str:
        return variables.get(match.group(1), match.group(0))
    return _PLACEHOLDER_RE.sub(replacer, template)


__all__ = [
    "TemplateResult",
    "render_skill_template",
    "extract_template_variables",
    "render_template_string",
]
