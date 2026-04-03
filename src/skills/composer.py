"""
Skill composer — combine multiple skills into compound prompts.

Ports: skills/skillComposer.ts, skills/compoundSkill.ts

Allows grouping skills into named compositions that are applied together.
Useful for persona packs, workflow bundles, etc.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .loader import Skill


@dataclass
class SkillComposition:
    """
    A named group of skills that are applied together.

    Example::

        debug_pack = SkillComposition(
            name="debug-pack",
            description="Full debugging workflow",
            skill_names=["debug", "security", "verify"],
        )
    """
    name: str
    description: str = ""
    skill_names: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    separator: str = "\n\n---\n\n"

    def compose(self, available: dict[str, Skill]) -> str:
        """
        Build combined skill content for all named skills that are available.

        Args:
            available: Mapping of skill_name → Skill.

        Returns:
            Combined markdown content string.
        """
        blocks: list[str] = []
        for name in self.skill_names:
            skill = available.get(name)
            if skill:
                blocks.append(f'<skill name="{name}">\n{skill.content.strip()}\n</skill>')
        return self.separator.join(blocks)

    def missing_skills(self, available: dict[str, Skill]) -> list[str]:
        """Return names of skills in this composition that aren't available."""
        return [n for n in self.skill_names if n not in available]


class SkillComposer:
    """
    Registry of SkillCompositions with lookup and apply helpers.
    """

    def __init__(self) -> None:
        self._compositions: dict[str, SkillComposition] = {}

    def register(self, composition: SkillComposition) -> None:
        self._compositions[composition.name] = composition

    def get(self, name: str) -> SkillComposition | None:
        return self._compositions.get(name)

    def list_compositions(self) -> list[SkillComposition]:
        return list(self._compositions.values())

    def apply(
        self,
        composition_name: str,
        available_skills: dict[str, Skill],
    ) -> str | None:
        """
        Apply a named composition using the available skills.

        Returns combined content string, or None if not found.
        """
        comp = self._compositions.get(composition_name)
        if not comp:
            return None
        return comp.compose(available_skills)

    def to_skill(self, composition: SkillComposition, available: dict[str, Skill]) -> Skill:
        """Convert a composition into a synthetic Skill object."""
        return Skill(
            name=composition.name,
            description=composition.description,
            content=composition.compose(available),
            source="dynamic",
            tags=composition.tags,
        )


# ---------------------------------------------------------------------------
# Built-in compositions
# ---------------------------------------------------------------------------

def default_composer() -> SkillComposer:
    """Return a SkillComposer pre-loaded with sensible default compositions."""
    composer = SkillComposer()

    composer.register(SkillComposition(
        name="debug-pack",
        description="Debugging + verification + security review",
        skill_names=["debug", "verify", "security"],
        tags=["debugging", "review"],
    ))

    composer.register(SkillComposition(
        name="api-review-pack",
        description="API design, security, and update-config checks",
        skill_names=["api-review", "security", "update-config"],
        tags=["api", "review"],
    ))

    composer.register(SkillComposition(
        name="stuck-pack",
        description="Unsticking + simplification + remember",
        skill_names=["stuck", "simplify", "remember"],
        tags=["workflow"],
    ))

    return composer


__all__ = [
    "SkillComposition",
    "SkillComposer",
    "default_composer",
]
