"""
Screen definitions and state machines.

Ports: screens/Doctor.tsx, screens/REPL.tsx, screens/ResumeConversation.tsx

Each "screen" is represented as a data class with the information needed
to render it. The actual React rendering lives in the TypeScript frontend.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Screen type enum
# ---------------------------------------------------------------------------

class ScreenType(str, Enum):
    DOCTOR              = "doctor"
    REPL                = "repl"
    RESUME_CONVERSATION = "resume_conversation"


# ---------------------------------------------------------------------------
# Base screen
# ---------------------------------------------------------------------------

@dataclass
class Screen:
    """Base screen with common fields."""
    type: ScreenType
    title: str = ""
    data: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Doctor screen (screens/Doctor.tsx)
# ---------------------------------------------------------------------------

@dataclass
class DoctorScreen(Screen):
    """
    Environment diagnostic screen.

    Shows Python version, API key status, network reachability,
    installed packages, etc.
    """
    type: ScreenType = field(init=False, default=ScreenType.DOCTOR)
    title: str = "Environment Doctor"
    checks: list[dict[str, Any]] = field(default_factory=list)

    def add_check(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append({"name": name, "passed": passed, "detail": detail})

    @property
    def all_passed(self) -> bool:
        return all(c["passed"] for c in self.checks)


# ---------------------------------------------------------------------------
# REPL screen (screens/REPL.tsx)
# ---------------------------------------------------------------------------

@dataclass
class REPLScreen(Screen):
    """
    Interactive REPL screen state.

    Holds session context, command history, and output buffer.
    """
    type: ScreenType = field(init=False, default=ScreenType.REPL)
    title: str = "claw REPL"
    prompt: str = "claw> "
    history: list[str] = field(default_factory=list)
    output: list[dict[str, Any]] = field(default_factory=list)  # [{role, text}]
    session_id: str = ""

    def append_output(self, role: str, text: str) -> None:
        self.output.append({"role": role, "text": text, "ts": len(self.output)})

    def add_to_history(self, command: str) -> None:
        if command and (not self.history or self.history[-1] != command):
            self.history.append(command)


# ---------------------------------------------------------------------------
# Resume Conversation screen (screens/ResumeConversation.tsx)
# ---------------------------------------------------------------------------

@dataclass
class ResumeScreen(Screen):
    """
    Screen shown when resuming an interrupted conversation.

    Lists available session transcripts with timestamps and previews.
    """
    type: ScreenType = field(init=False, default=ScreenType.RESUME_CONVERSATION)
    title: str = "Resume Conversation"
    sessions: list[dict[str, Any]] = field(default_factory=list)  # [{id, title, ts, preview}]
    selected_index: int = 0

    def select_next(self) -> None:
        if self.sessions:
            self.selected_index = (self.selected_index + 1) % len(self.sessions)

    def select_prev(self) -> None:
        if self.sessions:
            self.selected_index = (self.selected_index - 1) % len(self.sessions)

    @property
    def selected_session(self) -> dict[str, Any] | None:
        if self.sessions:
            return self.sessions[self.selected_index]
        return None


# ---------------------------------------------------------------------------
# Screen registry
# ---------------------------------------------------------------------------

SCREEN_FACTORIES: dict[ScreenType, type[Screen]] = {
    ScreenType.DOCTOR:              DoctorScreen,
    ScreenType.REPL:                REPLScreen,
    ScreenType.RESUME_CONVERSATION: ResumeScreen,
}


def make_screen(screen_type: ScreenType) -> Screen:
    factory = SCREEN_FACTORIES.get(screen_type, Screen)
    return factory()


__all__ = [
    "DoctorScreen",
    "REPLScreen",
    "ResumeScreen",
    "Screen",
    "ScreenType",
    "make_screen",
]
