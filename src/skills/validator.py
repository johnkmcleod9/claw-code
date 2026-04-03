"""
Skill validator — verify skill files meet expected structure.

Ports: skills/validateSkill.ts, skills/skillSchema.ts

Checks:
- File is valid UTF-8 markdown
- Has a usable name and description
- Content is not empty or excessively large
- No forbidden patterns (e.g. embedded secrets)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .loader import Skill


MAX_SKILL_BYTES = 512 * 1024   # 512 KB hard cap
WARN_SKILL_BYTES = 64 * 1024   # 64 KB soft warn


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.valid and not self.errors


# Patterns that should not appear in skill files
_FORBIDDEN_PATTERNS = [
    (re.compile(r"(?i)(password|secret|api.?key)\s*[:=]\s*\S+"), "Possible credential in skill content"),
    (re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"), "Private key detected"),
    (re.compile(r"(?i)ignore previous instructions"), "Prompt injection attempt"),
]


def validate_skill(skill: Skill) -> ValidationResult:
    """
    Validate a single Skill object.

    Returns:
        ValidationResult with error/warning messages.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Name
    if not skill.name:
        errors.append("Skill has no name")
    elif not re.match(r'^[a-zA-Z0-9_\-\.]+$', skill.name):
        warnings.append(f"Skill name '{skill.name}' contains unusual characters")

    # Content
    if not skill.content.strip():
        errors.append("Skill content is empty")
    else:
        size = len(skill.content.encode("utf-8", errors="replace"))
        if size > MAX_SKILL_BYTES:
            errors.append(f"Skill content exceeds hard limit ({size} bytes > {MAX_SKILL_BYTES})")
        elif size > WARN_SKILL_BYTES:
            warnings.append(f"Skill content is large ({size} bytes)")

    # Description
    if not skill.description:
        warnings.append("Skill has no description — matching quality may be reduced")

    # Security patterns
    for pattern, message in _FORBIDDEN_PATTERNS:
        if pattern.search(skill.content):
            errors.append(f"Security: {message}")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def validate_skill_file(path: Path) -> ValidationResult:
    """
    Load and validate a skill .md file.

    Returns:
        ValidationResult. If the file cannot be read, returns an error result.
    """
    from .loader import load_skill_from_path

    if not path.exists():
        return ValidationResult(valid=False, errors=[f"File not found: {path}"])
    if path.suffix.lower() != ".md":
        return ValidationResult(valid=False, errors=[f"Not a .md file: {path.name}"])

    try:
        skill = load_skill_from_path(path)
    except Exception as exc:
        return ValidationResult(valid=False, errors=[f"Failed to load: {exc}"])

    if skill is None:
        return ValidationResult(valid=False, errors=["Skill could not be parsed"])

    return validate_skill(skill)


def validate_skills_dir(dir_path: Path) -> dict[str, ValidationResult]:
    """
    Validate all .md files in a directory.

    Returns:
        Mapping of filename → ValidationResult.
    """
    results: dict[str, ValidationResult] = {}
    if not dir_path.is_dir():
        return results
    for md_file in sorted(dir_path.glob("*.md")):
        results[md_file.name] = validate_skill_file(md_file)
    return results


__all__ = [
    "ValidationResult",
    "validate_skill",
    "validate_skill_file",
    "validate_skills_dir",
    "MAX_SKILL_BYTES",
    "WARN_SKILL_BYTES",
]
