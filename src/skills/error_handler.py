"""
Skill error handling and recovery.

Ports: skills/skillErrors.ts, skills/errorRecovery.ts

Defines skill-specific exceptions and recovery strategies.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

class SkillError(Exception):
    """Base class for all skill-related errors."""
    def __init__(self, message: str, skill_name: str = "") -> None:
        super().__init__(message)
        self.skill_name = skill_name


class SkillNotFoundError(SkillError):
    """Raised when a requested skill cannot be located."""


class SkillLoadError(SkillError):
    """Raised when a skill file exists but cannot be parsed/loaded."""


class SkillValidationError(SkillError):
    """Raised when a skill fails validation."""
    def __init__(self, message: str, skill_name: str = "", errors: list[str] | None = None) -> None:
        super().__init__(message, skill_name)
        self.errors = errors or []


class SkillExecutionError(SkillError):
    """Raised when skill execution fails."""
    def __init__(
        self,
        message: str,
        skill_name: str = "",
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, skill_name)
        self.cause = cause


class SkillPermissionError(SkillError):
    """Raised when a skill is denied by policy."""


class SkillTimeoutError(SkillError):
    """Raised when skill execution exceeds the configured timeout."""


# ---------------------------------------------------------------------------
# Recovery
# ---------------------------------------------------------------------------

@dataclass
class RecoveryAction:
    strategy: str        # "fallback", "retry", "skip", "abort"
    fallback_skill: str = ""
    retry_max: int = 1
    message: str = ""


def suggest_recovery(error: SkillError) -> RecoveryAction:
    """
    Suggest a recovery action for a skill error.

    Args:
        error: The skill error to handle.

    Returns:
        A RecoveryAction with a recommended strategy.
    """
    if isinstance(error, SkillNotFoundError):
        return RecoveryAction(
            strategy="skip",
            message=f"Skill '{error.skill_name}' not found — skipping.",
        )
    elif isinstance(error, SkillValidationError):
        return RecoveryAction(
            strategy="skip",
            message=f"Skill '{error.skill_name}' failed validation — skipping.",
        )
    elif isinstance(error, SkillPermissionError):
        return RecoveryAction(
            strategy="abort",
            message=f"Skill '{error.skill_name}' is not permitted.",
        )
    elif isinstance(error, SkillTimeoutError):
        return RecoveryAction(
            strategy="retry",
            retry_max=1,
            message=f"Skill '{error.skill_name}' timed out — retrying once.",
        )
    elif isinstance(error, SkillExecutionError):
        return RecoveryAction(
            strategy="fallback",
            message=f"Skill '{error.skill_name}' execution failed — trying fallback.",
        )
    else:
        return RecoveryAction(
            strategy="abort",
            message=f"Unhandled skill error: {error}",
        )


def format_skill_error(error: SkillError) -> str:
    """Return a user-friendly error message."""
    type_name = type(error).__name__
    msg = str(error)
    if error.skill_name:
        return f"[{type_name}] Skill '{error.skill_name}': {msg}"
    return f"[{type_name}] {msg}"


__all__ = [
    "SkillError",
    "SkillNotFoundError",
    "SkillLoadError",
    "SkillValidationError",
    "SkillExecutionError",
    "SkillPermissionError",
    "SkillTimeoutError",
    "RecoveryAction",
    "suggest_recovery",
    "format_skill_error",
]
