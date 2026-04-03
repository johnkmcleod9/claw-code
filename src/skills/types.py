"""
Core type definitions for the skills subsystem.

Provides shared data structures used across all skills modules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SkillSource(str, Enum):
    """Where a skill originated."""
    FILE = "file"
    BUNDLED = "bundled"
    MCP = "mcp"
    REMOTE = "remote"
    DYNAMIC = "dynamic"


class SkillStatus(str, Enum):
    """Lifecycle status of a skill."""
    AVAILABLE = "available"
    LOADING = "loading"
    CACHED = "cached"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class SkillMatch:
    """A scored skill match from the matcher."""
    skill_name: str
    score: float           # 0.0–1.0
    reason: str = ""       # human-readable match reason
    matched_tokens: list[str] = field(default_factory=list)

    def __lt__(self, other: "SkillMatch") -> bool:
        return self.score < other.score


@dataclass
class SkillResult:
    """Result of executing a skill."""
    skill_name: str
    success: bool
    output: Any = None
    error: str = ""
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillEvent:
    """A lifecycle event emitted by the skill subsystem."""
    event_type: str        # "loaded", "matched", "executed", "error", "cached"
    skill_name: str
    data: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "SkillSource",
    "SkillStatus",
    "SkillMatch",
    "SkillResult",
    "SkillEvent",
]
