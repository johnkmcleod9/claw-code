"""
Buddy companion state and lifecycle.

Ports: buddy/companion.ts, buddy/types.ts
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Stats (buddy/types.ts)
# ---------------------------------------------------------------------------

@dataclass
class BuddyStats:
    """Statistical attributes of a buddy companion."""
    energy: float = 100.0    # 0–100; depletes with use
    happiness: float = 80.0  # 0–100; affects responses
    xp: int = 0              # Experience points earned
    level: int = 1
    streak_days: int = 0     # Consecutive days of interaction

    @property
    def mood(self) -> str:
        if self.happiness >= 80:
            return "thrilled"
        if self.happiness >= 60:
            return "happy"
        if self.happiness >= 40:
            return "neutral"
        if self.happiness >= 20:
            return "sad"
        return "miserable"

    def can_level_up(self) -> bool:
        return self.xp >= self.xp_for_next_level()

    def xp_for_next_level(self) -> int:
        return self.level * 100


@dataclass
class BuddyAppearance:
    """Visual appearance descriptor of a buddy companion."""
    sprite_key: str = "default"
    colour: str = "#888888"
    size_category: str = "medium"  # tiny | small | medium | large | huge
    pattern: str = "solid"


# ---------------------------------------------------------------------------
# Buddy companion (buddy/companion.ts)
# ---------------------------------------------------------------------------

@dataclass
class BuddyCompanion:
    """
    A virtual companion that lives alongside the user in the terminal.

    Ports: buddy/companion.ts BuddyCompanion
    """
    name: str
    species: str
    personality: str = "curious"
    stats: BuddyStats = field(default_factory=BuddyStats)
    appearance: BuddyAppearance = field(default_factory=BuddyAppearance)
    created_at: float = field(default_factory=time.time)
    last_interaction: float = field(default_factory=time.time)
    total_interactions: int = 0
    vocabulary: list[str] = field(default_factory=list)
    nicknames: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # ---- interaction decay -----------------------------------------------

    def interact(self) -> None:
        """Record an interaction and apply stat changes."""
        self.last_interaction = time.time()
        self.total_interactions += 1
        self.stats.energy = max(0.0, self.stats.energy - 2.0)
        self.stats.happiness = min(100.0, self.stats.happiness + 5.0)
        self.stats.xp += 10
        if self.stats.can_level_up():
            self._level_up()

    def idle_tick(self, idle_seconds: float) -> None:
        """Apply decay when the user is idle."""
        hours = idle_seconds / 3600.0
        self.stats.energy = max(0.0, self.stats.energy - hours * 5.0)
        self.stats.happiness = max(0.0, self.stats.happiness - hours * 2.0)
        if idle_seconds > 86400:
            self.stats.streak_days = 0

    def feed(self, amount: float = 15.0) -> None:
        self.stats.energy = min(100.0, self.stats.energy + amount)

    def pet(self) -> None:
        self.stats.happiness = min(100.0, self.stats.happiness + 10.0)

    def _level_up(self) -> None:
        self.stats.level += 1
        self.stats.xp = 0

    # ---- serialization ---------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "species": self.species,
            "personality": self.personality,
            "stats": {
                "energy": self.stats.energy,
                "happiness": self.stats.happiness,
                "xp": self.stats.xp,
                "level": self.stats.level,
                "streak_days": self.stats.streak_days,
            },
            "appearance": {
                "sprite_key": self.appearance.sprite_key,
                "colour": self.appearance.colour,
                "size_category": self.appearance.size_category,
                "pattern": self.appearance.pattern,
            },
            "created_at": self.created_at,
            "last_interaction": self.last_interaction,
            "total_interactions": self.total_interactions,
            "vocabulary": self.vocabulary,
            "nicknames": self.nicknames,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BuddyCompanion":
        stats_data = data.get("stats", {})
        stats = BuddyStats(
            energy=stats_data.get("energy", 100.0),
            happiness=stats_data.get("happiness", 80.0),
            xp=stats_data.get("xp", 0),
            level=stats_data.get("level", 1),
            streak_days=stats_data.get("streak_days", 0),
        )
        app_data = data.get("appearance", {})
        appearance = BuddyAppearance(
            sprite_key=app_data.get("sprite_key", "default"),
            colour=app_data.get("colour", "#888888"),
            size_category=app_data.get("size_category", "medium"),
            pattern=app_data.get("pattern", "solid"),
        )
        return cls(
            name=data.get("name", "Buddy"),
            species=data.get("species", "unknown"),
            personality=data.get("personality", "curious"),
            stats=stats,
            appearance=appearance,
            created_at=data.get("created_at", time.time()),
            last_interaction=data.get("last_interaction", time.time()),
            total_interactions=data.get("total_interactions", 0),
            vocabulary=data.get("vocabulary", []),
            nicknames=data.get("nicknames", []),
            metadata=data.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# Companion store
# ---------------------------------------------------------------------------

_buddy_instance: BuddyCompanion | None = None


def get_buddy() -> BuddyCompanion | None:
    return _buddy_instance


def set_buddy(buddy: BuddyCompanion) -> None:
    global _buddy_instance
    _buddy_instance = buddy


__all__ = [
    "BuddyAppearance",
    "BuddyCompanion",
    "BuddyStats",
    "get_buddy",
    "set_buddy",
]
