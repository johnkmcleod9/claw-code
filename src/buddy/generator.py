"""
Buddy generator — deterministic pet generation from user identity.

Uses FNV-1a hash → Mulberry32 PRNG (matching Claude Code's approach).
Same user always gets the same buddy. No cheating.
"""
from __future__ import annotations

import getpass
import json
import os
import platform
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

from .species import SPECIES, Species

BUDDY_CONFIG = Path.home() / ".claw-code" / "buddy.json"
SALT = "claw-buddy-2026"

# ─── Rarity system ───

RARITY_TABLE = [
    ("Common", 0.60, 1, 5, False),    # (name, prob, stars, stat_floor, hat)
    ("Uncommon", 0.25, 2, 15, True),
    ("Rare", 0.10, 3, 25, True),
    ("Epic", 0.04, 4, 35, True),
    ("Legendary", 0.01, 5, 50, True),
]

HATS = [
    ("None", "Common"),
    ("Crown", "Uncommon"),
    ("Top Hat", "Uncommon"),
    ("Propeller", "Uncommon"),
    ("Halo", "Rare"),
    ("Wizard", "Rare"),
    ("Beanie", "Epic"),
    ("Tiny Duck", "Legendary"),
]

STAT_NAMES = ("DEBUGGING", "PATIENCE", "CHAOS", "WISDOM", "SNARK")

RARITY_MIN = {
    "Common": 0,
    "Uncommon": 1,
    "Rare": 2,
    "Epic": 3,
    "Legendary": 4,
}


@dataclass
class Buddy:
    species: str
    category: str
    rarity: str
    stars: int
    shiny: bool
    stats: dict[str, int]
    hat: str
    name: str = ""
    personality: str = ""
    hatched_at: str = ""

    def display_card(self) -> str:
        """Render the buddy as an ASCII stat card."""
        shiny_tag = " ✨ SHINY" if self.shiny else ""
        stars_str = "⭐" * self.stars

        lines = [
            f"╔══════════════════════════════╗",
            f"║  {self.name or self.species:<16} {stars_str:<10} ║",
            f"║  {self.species} ({self.category}){shiny_tag:<10}  ║",
            f"║  Rarity: {self.rarity:<20}║",
            f"╠══════════════════════════════╣",
        ]

        # ASCII art (frame 0)
        from .species import SPECIES_BY_NAME
        sp = SPECIES_BY_NAME.get(self.species)
        if sp:
            for art_line in sp.frames[0].split("\n"):
                lines.append(f"║  {art_line:<28}║")

        lines.append(f"╠══════════════════════════════╣")

        for stat, val in self.stats.items():
            bar_len = val // 5
            bar = "█" * bar_len + "░" * (20 - bar_len)
            lines.append(f"║ {stat:<10} {bar} {val:>3} ║")

        if self.hat != "None":
            lines.append(f"║  Hat: {self.hat:<23}║")

        if self.personality:
            # Wrap personality text
            words = self.personality.split()
            pline = ""
            for w in words:
                if len(pline) + len(w) + 1 > 26:
                    lines.append(f"║  {pline:<28}║")
                    pline = w
                else:
                    pline = f"{pline} {w}".strip()
            if pline:
                lines.append(f"║  {pline:<28}║")

        lines.append(f"╚══════════════════════════════╝")

        if self.hatched_at:
            lines.append(f"  Hatched: {self.hatched_at}")

        return "\n".join(lines)


# ─── Deterministic PRNG (Mulberry32) ───

def _fnv1a_hash(data: str) -> int:
    """FNV-1a hash (32-bit)."""
    h = 0x811C9DC5
    for byte in data.encode("utf-8"):
        h ^= byte
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


class Mulberry32:
    """Mulberry32 PRNG — deterministic, fast, matches JS implementation."""

    def __init__(self, seed: int):
        self.state = seed & 0xFFFFFFFF

    def next(self) -> float:
        self.state = (self.state + 0x6D2B79F5) & 0xFFFFFFFF
        t = self.state
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t = (t ^ (t + ((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 0xFFFFFFFF

    def next_int(self, max_val: int) -> int:
        return int(self.next() * max_val)


def _get_user_identity() -> str:
    """Get a stable user identity string."""
    username = getpass.getuser()
    hostname = platform.node()
    # Also check for a configured identity
    if BUDDY_CONFIG.exists():
        try:
            data = json.loads(BUDDY_CONFIG.read_text())
            if data.get("identity"):
                return data["identity"]
        except Exception:
            pass
    return f"{username}@{hostname}"


def generate_buddy(identity: str | None = None) -> Buddy:
    """Generate a deterministic buddy from user identity."""
    if identity is None:
        identity = _get_user_identity()

    seed = _fnv1a_hash(f"{SALT}:{identity}")
    rng = Mulberry32(seed)

    # Species selection
    species_idx = rng.next_int(len(SPECIES))
    species = SPECIES[species_idx]

    # Rarity roll
    roll = rng.next()
    cumulative = 0.0
    rarity_name = "Common"
    stars = 1
    stat_floor = 5
    gets_hat = False

    for name, prob, s, floor, hat in RARITY_TABLE:
        cumulative += prob
        if roll < cumulative:
            rarity_name = name
            stars = s
            stat_floor = floor
            gets_hat = hat
            break

    # Shiny check (independent 1%)
    shiny = rng.next() < 0.01

    # Stats generation
    stats = {}
    peak_stat = rng.next_int(len(STAT_NAMES))
    dump_stat = (peak_stat + 1 + rng.next_int(len(STAT_NAMES) - 1)) % len(STAT_NAMES)

    for i, stat_name in enumerate(STAT_NAMES):
        if i == peak_stat:
            val = min(100, stat_floor + 50 + rng.next_int(50))
        elif i == dump_stat:
            val = stat_floor + rng.next_int(10)
        else:
            val = stat_floor + rng.next_int(100 - stat_floor)
        stats[stat_name] = val

    # Hat selection
    hat = "None"
    if gets_hat:
        rarity_idx = RARITY_MIN.get(rarity_name, 0)
        eligible = [h for h, min_rarity in HATS if RARITY_MIN.get(min_rarity, 0) <= rarity_idx]
        if eligible:
            hat = eligible[rng.next_int(len(eligible))]

    return Buddy(
        species=species.name,
        category=species.category,
        rarity=rarity_name,
        stars=stars,
        shiny=shiny,
        stats=stats,
        hat=hat,
    )


def hatch_buddy(identity: str | None = None) -> Buddy:
    """Generate and persist a buddy (soul data: name, personality, hatch date)."""
    buddy = generate_buddy(identity)

    # Load existing soul data
    soul = {}
    if BUDDY_CONFIG.exists():
        try:
            soul = json.loads(BUDDY_CONFIG.read_text())
        except Exception:
            pass

    # Preserve soul (name, personality, hatch date) if species matches
    if soul.get("species") == buddy.species:
        buddy.name = soul.get("name", "")
        buddy.personality = soul.get("personality", "")
        buddy.hatched_at = soul.get("hatched_at", "")
    else:
        # New buddy — set hatch date, name/personality set later
        buddy.hatched_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Save (bones are recomputed, soul persists)
    save_data = {
        "identity": identity or _get_user_identity(),
        "species": buddy.species,
        "name": buddy.name,
        "personality": buddy.personality,
        "hatched_at": buddy.hatched_at,
    }
    BUDDY_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    BUDDY_CONFIG.write_text(json.dumps(save_data, indent=2))

    return buddy
