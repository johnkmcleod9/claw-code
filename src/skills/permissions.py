"""
Skill permissions — control which skills can execute in what contexts.

Ports: skills/skillPermissions.ts, skills/skillGuard.ts

Skills can be restricted by:
- Allowlist / blocklist of skill names
- Execution mode (read-only vs. tool-calling)
- Skill source (bundled only, no MCP, etc.)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .loader import Skill
from .types import SkillSource


class SkillPermission(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    PROMPT = "prompt"   # ask user before executing


@dataclass
class SkillPolicy:
    """
    A policy that governs which skills are allowed to run.

    Rules are evaluated in order:
    1. If skill name is in ``deny_list`` → DENY
    2. If ``allow_list`` is set and skill is NOT in it → DENY
    3. If source is in ``denied_sources`` → DENY
    4. Default: ALLOW
    """
    allow_list: list[str] = field(default_factory=list)   # empty = allow all
    deny_list: list[str] = field(default_factory=list)
    denied_sources: list[str] = field(default_factory=list)
    require_validation: bool = True
    max_skills_per_request: int = 5

    def check(self, skill: Skill) -> SkillPermission:
        """
        Evaluate policy for a skill.

        Returns:
            ALLOW, DENY, or PROMPT.
        """
        if skill.name in self.deny_list:
            return SkillPermission.DENY

        if self.allow_list and skill.name not in self.allow_list:
            return SkillPermission.DENY

        if skill.source in self.denied_sources:
            return SkillPermission.DENY

        return SkillPermission.ALLOW

    def filter_skills(self, skills: list[Skill]) -> list[Skill]:
        """
        Return only the skills permitted by this policy.

        Also enforces max_skills_per_request.
        """
        allowed = [s for s in skills if self.check(s) == SkillPermission.ALLOW]
        return allowed[:self.max_skills_per_request]

    @classmethod
    def permissive(cls) -> "SkillPolicy":
        """Create a policy that allows everything."""
        return cls()

    @classmethod
    def bundled_only(cls) -> "SkillPolicy":
        """Allow only bundled skills, deny file and MCP sources."""
        return cls(denied_sources=[SkillSource.FILE.value, SkillSource.MCP.value])

    @classmethod
    def no_mcp(cls) -> "SkillPolicy":
        """Allow file and bundled skills, deny MCP."""
        return cls(denied_sources=[SkillSource.MCP.value])


# ---------------------------------------------------------------------------
# Guard helper
# ---------------------------------------------------------------------------

class SkillGuard:
    """
    Wraps a SkillPolicy and provides guarded execution helpers.
    """

    def __init__(self, policy: SkillPolicy | None = None) -> None:
        self.policy = policy or SkillPolicy.permissive()

    def is_allowed(self, skill: Skill) -> bool:
        return self.policy.check(skill) == SkillPermission.ALLOW

    def assert_allowed(self, skill: Skill) -> None:
        """Raise PermissionError if the skill is denied."""
        if not self.is_allowed(skill):
            raise PermissionError(
                f"Skill '{skill.name}' (source={skill.source}) is denied by policy."
            )

    def filter(self, skills: list[Skill]) -> list[Skill]:
        return self.policy.filter_skills(skills)


__all__ = [
    "SkillPermission",
    "SkillPolicy",
    "SkillGuard",
]
