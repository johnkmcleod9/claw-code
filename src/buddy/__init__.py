"""
Buddy — Terminal Tamagotchi companion for Claw Code.

Inspired by Claude Code's /buddy system (leaked March 2026).
Deterministic pet generation from user identity, ASCII art sprites,
stats, rarity tiers, and personality.

Modules:
- ``companion``  BuddyCompanion state, BuddyStats, interaction lifecycle
- ``generator``  Deterministic generation from user identity
- ``prompt``     System prompt and greeting builders
- ``species``    Species definitions and ASCII art sprites
- ``commands``   CLI command handler for /buddy
"""
from __future__ import annotations

from .companion import (
    BuddyAppearance,
    BuddyCompanion,
    BuddyStats,
    get_buddy,
    set_buddy,
)
from .generator import (
    Buddy,
    generate_buddy,
    hatch_buddy,
)
from .prompt import (
    build_buddy_greeting,
    build_buddy_response,
    build_buddy_system_prompt,
)
from .species import Species
from .commands import buddy_command

__all__ = [
    "Buddy",
    "BuddyAppearance",
    "BuddyCompanion",
    "BuddyStats",
    "Species",
    "buddy_command",
    "build_buddy_greeting",
    "build_buddy_response",
    "build_buddy_system_prompt",
    "generate_buddy",
    "get_buddy",
    "hatch_buddy",
    "set_buddy",
]
