"""
SkillTool — Load and execute skill files (.md instructions).

Ported from rust/crates/tools/src/lib.rs execute_skill().
Skills are markdown files containing specialized instructions that get
injected into the agent's context. They live in:
  - ./skills/ (project-local)
  - ~/.claw-code/skills/ (global)
"""
from __future__ import annotations

import os
from pathlib import Path

from .base import Tool, ToolContext, ToolResult

GLOBAL_SKILLS_DIR = Path.home() / ".claw-code" / "skills"


def _find_skill_dirs(cwd: Path) -> list[Path]:
    """Find all skill directories (project-local + global)."""
    dirs = []
    # Project-local skills
    local = cwd / "skills"
    if local.is_dir():
        dirs.append(local)
    # Walk up to find project root skills
    parent = cwd.parent
    while parent != parent.parent:
        candidate = parent / "skills"
        if candidate.is_dir() and candidate != local:
            dirs.append(candidate)
            break
        parent = parent.parent
    # Global skills
    if GLOBAL_SKILLS_DIR.is_dir():
        dirs.append(GLOBAL_SKILLS_DIR)
    return dirs


def _list_skills(cwd: Path) -> list[dict[str, str]]:
    """List all available skills."""
    skills = []
    seen = set()
    for skill_dir in _find_skill_dirs(cwd):
        for md_file in sorted(skill_dir.glob("*.md")):
            name = md_file.stem
            if name not in seen:
                seen.add(name)
                # Read first line as description
                try:
                    first_line = md_file.read_text().split("\n")[0].strip()
                    if first_line.startswith("#"):
                        first_line = first_line.lstrip("# ").strip()
                    desc = first_line[:100]
                except Exception:
                    desc = ""
                skills.append({
                    "name": name,
                    "path": str(md_file),
                    "description": desc,
                    "source": str(skill_dir),
                })
    return skills


def _resolve_skill(name: str, cwd: Path) -> Path | None:
    """Find a skill file by name."""
    for skill_dir in _find_skill_dirs(cwd):
        candidate = skill_dir / f"{name}.md"
        if candidate.exists():
            return candidate
    return None


class SkillTool(Tool):
    @property
    def name(self) -> str:
        return "skill"

    @property
    def description(self) -> str:
        return (
            "Load a skill file containing specialized instructions. "
            "Skills are markdown files in skills/ directories that provide domain-specific "
            "knowledge and procedures. Use with skill='list' to see available skills, "
            "or provide a skill name to load it."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "skill": {
                    "type": "string",
                    "description": "Skill name to load, or 'list' to see available skills",
                },
                "args": {
                    "type": "string",
                    "description": "Optional arguments to pass to the skill",
                },
            },
            "required": ["skill"],
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        skill_name = args.get("skill", "").strip()

        if not skill_name:
            return ToolResult(success=False, output="", error="skill name is required")

        # List mode
        if skill_name.lower() == "list":
            skills = _list_skills(context.cwd)
            if not skills:
                return ToolResult(
                    success=True,
                    output="No skills found. Create .md files in ./skills/ or ~/.claw-code/skills/",
                )
            lines = ["Available skills:\n"]
            for s in skills:
                lines.append(f"- **{s['name']}**: {s['description']}")
                lines.append(f"  Source: {s['source']}")
            return ToolResult(success=True, output="\n".join(lines))

        # Load a specific skill
        skill_path = _resolve_skill(skill_name, context.cwd)
        if skill_path is None:
            available = _list_skills(context.cwd)
            names = [s["name"] for s in available]
            return ToolResult(
                success=False, output="",
                error=f"Skill '{skill_name}' not found. Available: {', '.join(names) or 'none'}",
            )

        try:
            content = skill_path.read_text()
            skill_args = args.get("args", "")

            lines = [
                f"## Skill: {skill_name}",
                f"Source: {skill_path}",
            ]
            if skill_args:
                lines.append(f"Args: {skill_args}")
            lines.append("")
            lines.append(content)

            return ToolResult(
                success=True,
                output="\n".join(lines),
                metadata={"skill": skill_name, "path": str(skill_path)},
            )

        except Exception as e:
            return ToolResult(success=False, output="", error=f"Failed to load skill: {e}")
