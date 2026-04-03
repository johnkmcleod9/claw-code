"""
Buddy REPL commands — /buddy, /buddy name, /buddy stats.
"""
from __future__ import annotations

import sys

from .generator import hatch_buddy, BUDDY_CONFIG
from .species import SPECIES_BY_NAME


def buddy_command(args: str = "") -> str:
    """Handle /buddy command. Returns display string."""
    parts = args.strip().split(maxsplit=1)
    subcmd = parts[0].lower() if parts else ""
    arg = parts[1] if len(parts) > 1 else ""

    if subcmd == "help":
        return (
            "🐾 Buddy Commands:\n"
            "  /buddy          — View your buddy\n"
            "  /buddy name X   — Name your buddy\n"
            "  /buddy stats    — View detailed stats\n"
            "  /buddy animate  — Watch your buddy animate\n"
            "  /buddy species  — List all 18 species\n"
            "  /buddy help     — This help\n"
        )

    buddy = hatch_buddy()

    if not buddy.name and subcmd != "name":
        # First hatch!
        card = buddy.display_card()
        return (
            f"🥚 A wild {buddy.species} hatched!\n\n"
            f"{card}\n\n"
            f"Use `/buddy name <name>` to name your companion!"
        )

    if subcmd == "name":
        if not arg:
            return "Usage: /buddy name <name>"
        buddy.name = arg
        # Save name
        import json
        config = {}
        if BUDDY_CONFIG.exists():
            config = json.loads(BUDDY_CONFIG.read_text())
        config["name"] = arg
        BUDDY_CONFIG.write_text(json.dumps(config, indent=2))
        return f"✨ Your {buddy.species} is now named **{arg}**!"

    if subcmd == "stats":
        lines = [f"📊 {buddy.name or buddy.species} Stats\n"]
        for stat, val in buddy.stats.items():
            bar = "█" * (val // 5) + "░" * (20 - val // 5)
            lines.append(f"  {stat:<10} {bar} {val:>3}")
        lines.append(f"\n  Rarity: {buddy.rarity} {'⭐' * buddy.stars}")
        if buddy.shiny:
            lines.append("  ✨ SHINY VARIANT ✨")
        if buddy.hat != "None":
            lines.append(f"  Hat: {buddy.hat}")
        return "\n".join(lines)

    if subcmd == "animate":
        species = SPECIES_BY_NAME.get(buddy.species)
        if not species:
            return "No animation data"
        lines = [f"🎬 {buddy.name or buddy.species} Animation\n"]
        for i, frame in enumerate(species.frames):
            lines.append(f"  Frame {i + 1}:")
            for fline in frame.split("\n"):
                lines.append(f"    {fline}")
            lines.append("")
        return "\n".join(lines)

    if subcmd == "species":
        lines = ["🐾 All 18 Buddy Species\n"]
        by_cat: dict[str, list[str]] = {}
        from .species import SPECIES as ALL
        for s in ALL:
            by_cat.setdefault(s.category, []).append(s.name)
        for cat, names in by_cat.items():
            lines.append(f"  {cat}: {', '.join(names)}")
        return "\n".join(lines)

    # Default: show card
    return buddy.display_card()
