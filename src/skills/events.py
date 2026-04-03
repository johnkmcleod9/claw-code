"""
Skill event bus — publish/subscribe for skill lifecycle events.

Ports: skills/skillEvents.ts, skills/eventEmitter.ts

Lightweight in-process event bus; no external dependencies.
"""
from __future__ import annotations

import threading
from collections import defaultdict
from typing import Callable

from .types import SkillEvent


EventHandler = Callable[[SkillEvent], None]


class SkillEventBus:
    """
    Thread-safe publish/subscribe event bus for skill lifecycle events.

    Supported event types:
        registered, unregistered, loaded, matched,
        executed, error, cached, skill_added, skill_updated, skill_removed
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._wildcard: list[EventHandler] = []
        self._lock = threading.Lock()
        self._history: list[SkillEvent] = []
        self._max_history: int = 500

    def on(self, event_type: str, handler: EventHandler) -> "SkillEventBus":
        """Subscribe to a specific event type. Returns self for chaining."""
        with self._lock:
            self._handlers[event_type].append(handler)
        return self

    def on_any(self, handler: EventHandler) -> "SkillEventBus":
        """Subscribe to ALL event types. Returns self for chaining."""
        with self._lock:
            self._wildcard.append(handler)
        return self

    def off(self, event_type: str, handler: EventHandler) -> bool:
        """Unsubscribe a handler. Returns True if it was found."""
        with self._lock:
            handlers = self._handlers.get(event_type, [])
            if handler in handlers:
                handlers.remove(handler)
                return True
        return False

    def emit(self, event: SkillEvent) -> None:
        """Publish an event to all registered handlers."""
        with self._lock:
            handlers = list(self._handlers.get(event.event_type, []))
            wildcards = list(self._wildcard)
            # Record history
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        for handler in handlers + wildcards:
            try:
                handler(event)
            except Exception:
                pass

    def emit_many(self, events: list[SkillEvent]) -> None:
        """Publish multiple events."""
        for event in events:
            self.emit(event)

    def history(self, event_type: str | None = None, limit: int = 50) -> list[SkillEvent]:
        """Return recent events, optionally filtered by type."""
        with self._lock:
            events = self._history[-limit:]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events

    def clear_handlers(self, event_type: str | None = None) -> None:
        """Remove handlers (all, or for one event_type)."""
        with self._lock:
            if event_type:
                self._handlers.pop(event_type, None)
            else:
                self._handlers.clear()
                self._wildcard.clear()


# ---------------------------------------------------------------------------
# Module-level default bus
# ---------------------------------------------------------------------------

_default_bus: SkillEventBus | None = None


def get_event_bus() -> SkillEventBus:
    """Return (or create) the module-level default event bus."""
    global _default_bus
    if _default_bus is None:
        _default_bus = SkillEventBus()
    return _default_bus


def emit_skill_event(event: SkillEvent) -> None:
    """Emit an event on the default bus."""
    get_event_bus().emit(event)


__all__ = [
    "SkillEventBus",
    "EventHandler",
    "get_event_bus",
    "emit_skill_event",
]
