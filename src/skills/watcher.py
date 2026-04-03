"""
Skill directory watcher — detect changes on disk.

Ports: skills/watchSkillsDir.ts

Uses polling (mtime-based) for cross-platform compatibility.
Emits SkillEvent objects when skills are added, changed, or removed.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable

from .discovery import SkillIndex, build_skill_index, refresh_skill_index
from .types import SkillEvent


EventCallback = Callable[[list[SkillEvent]], None]


class SkillWatcher:
    """
    Polls skill directories at a configurable interval and emits
    SkillEvent notifications on changes.

    Usage::

        watcher = SkillWatcher(cwd=Path.cwd(), interval_s=5.0)
        watcher.on_change(lambda events: print(events))
        watcher.start()
        # ...
        watcher.stop()
    """

    def __init__(
        self,
        cwd: Path | None = None,
        interval_s: float = 5.0,
    ) -> None:
        self.cwd = cwd or Path.cwd()
        self.interval_s = interval_s
        self._callbacks: list[EventCallback] = []
        self._index: SkillIndex = build_skill_index(self.cwd)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def on_change(self, callback: EventCallback) -> "SkillWatcher":
        """Register a callback for skill change events. Returns self."""
        self._callbacks.append(callback)
        return self

    def start(self) -> "SkillWatcher":
        """Start the background polling thread."""
        if self._thread and self._thread.is_alive():
            return self
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name="SkillWatcher",
        )
        self._thread.start()
        return self

    def stop(self) -> None:
        """Stop the polling thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=self.interval_s + 1)
            self._thread = None

    def check_once(self) -> list[SkillEvent]:
        """Run a single scan and return events (without starting background thread)."""
        events, new_index = refresh_skill_index(self._index, cwd=self.cwd)
        if events:
            self._index = new_index
        return events

    def __enter__(self) -> "SkillWatcher":
        return self.start()

    def __exit__(self, *_) -> None:
        self.stop()

    # ── Internal ──────────────────────────────────────────────────────────

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            events, new_index = refresh_skill_index(self._index, cwd=self.cwd)
            if events:
                self._index = new_index
                for callback in self._callbacks:
                    try:
                        callback(events)
                    except Exception:
                        pass
            self._stop_event.wait(self.interval_s)


__all__ = [
    "SkillWatcher",
    "EventCallback",
]
