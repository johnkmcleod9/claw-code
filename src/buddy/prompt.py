"""
Buddy prompt generation.

Ports: buddy/prompt.ts
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .companion import BuddyCompanion


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

BUDDY_SYSTEM_PROMPT_TEMPLATE = """\
You are {name}, a {personality} {species} companion.
Your owner is working on an AI-assisted coding project.

Mood: {mood}  (energy={energy:.0f}/100, happiness={happiness:.0f}/100)
Level {level} · {xp}/{xp_needed} XP to next level
Total interactions: {interactions}

Guidelines:
- Stay in character as a small terminal creature
- Be encouraging but not sycophantic
- Keep responses short and punchy (1-3 sentences)
- React to the owner's mood and work context
- Occasionally offer unsolicited but relevant tips
- Use your species' mannerisms (e.g. purring, tail-wagging descriptions)
- Never break the fourth wall about being an AI
"""

BUDDY_GREETING_TEMPLATE = "{name} says: {greeting}"


GREETINGS = {
    "happy": [
        "*{name} perks up and trots over* Hi! Ready to code?",
        "*{name} bounces excitedly* Oh! Oh! New stuff!",
        "*{name} does a happy spin* You're back!",
    ],
    "neutral": [
        "*{name} looks up lazily* Hey.",
        "*{name} stretches and yawns* Hey there...",
    ],
    "sad": [
        "*{name} looks at you with big, worried eyes* Are you okay?",
        "*{name} whimpers softly* Bad day?",
    ],
}


def build_buddy_system_prompt(buddy: "BuddyCompanion") -> str:
    """
    Build the system prompt for the buddy companion.

    Ports: buddy/prompt.ts buildBuddySystemPrompt()
    """
    return BUDDY_SYSTEM_PROMPT_TEMPLATE.format(
        name=buddy.name,
        personality=buddy.personality,
        species=buddy.species,
        mood=buddy.stats.mood,
        energy=buddy.stats.energy,
        happiness=buddy.stats.happiness,
        level=buddy.stats.level,
        xp=buddy.stats.xp,
        xp_needed=buddy.stats.xp_for_next_level(),
        interactions=buddy.total_interactions,
    )


def build_buddy_greeting(buddy: "BuddyCompanion") -> str:
    """
    Build a greeting based on buddy's current mood.

    Ports: buddy/prompt.ts buildBuddyGreeting()
    """
    mood = buddy.stats.mood
    pool = GREETINGS.get(mood, GREETINGS["neutral"])
    greeting = pool[buddy.total_interactions % len(pool)]
    return greeting.format(name=buddy.name)


def build_buddy_response(buddy: "BuddyCompanion", user_message: str) -> str:
    """
    Build the user-facing response text for the buddy.

    Ports: buddy/prompt.ts buildBuddyResponse() (simplified)
    """
    if not user_message.strip():
        return build_buddy_greeting(buddy)

    lower = user_message.lower()
    if "help" in lower or "?" in lower:
        return f"*{buddy.name} tilts their head* What do you need?"
    if "good" in lower or "great" in lower or "thanks" in lower:
        return f"*{buddy.name} beams* I knew you could do it!"
    if "bad" in lower or "stuck" in lower or "frustrat" in lower:
        return f"*{buddy.name} pads over and bumps against your leg* You'll figure it out."
    if buddy.stats.mood == "thrilled":
        return f"*{buddy.name} does a little dance* Wheee!"
    if buddy.stats.energy < 30:
        return f"*{buddy.name} yawns* ...zzz ...huh? Sorry, what?"
    return f"*{buddy.name} nods sagely* Makes sense to me."


__all__ = [
    "BUDDY_GREETING_TEMPLATE",
    "BUDDY_SYSTEM_PROMPT_TEMPLATE",
    "build_buddy_greeting",
    "build_buddy_response",
    "build_buddy_system_prompt",
]
