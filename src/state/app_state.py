"""
Application-level state management.

Ports: state/AppState.tsx, state/AppStateStore.ts
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .observable import Observable, Store


class AppMode(Enum):
    """Main operating modes of the CLI."""
    INTERACTIVE = "interactive"
    PLAN = "plan"
    READONLY = "readonly"
    TASK = "task"
    TEAM = "team"


class ApprovalMode(Enum):
    """Tool approval modes."""
    ON = "on"
    OFF = "off"
    ALWAYS = "always"


@dataclass
class AppState:
    """
    Central application state container.

    This is the Python equivalent of the TypeScript AppState.tsx class.
    """
    mode: AppMode = AppMode.INTERACTIVE
    model: str = ""
    session_id: str = ""
    workdir: str = ""
    approval_mode: ApprovalMode = ApprovalMode.ON
    stream_enabled: bool = True
    compaction_threshold: int = 50_000
    team_mode: bool = False
    plan_mode: bool = False
    cost_limit_usd: float | None = None
    max_turns: int = 0
    # Internal metadata
    _custom: dict[str, Any] = field(default_factory=dict)


class AppStateStore:
    """
    Thread-safe store that owns a single global AppState.

    Provides type-safe accessors and integrates with the Observable system.
    Ports: state/AppStateStore.ts
    """

    _instance: "AppStateStore | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._state = Observable(AppState())
        self._store = Store()  # for arbitrary key-value extensions

    @classmethod
    def get_instance(cls) -> "AppStateStore":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (useful for testing)."""
        with cls._lock:
            cls._instance = None

    # ---- typed accessors -------------------------------------------------

    @property
    def mode(self) -> AppMode:
        return self._state.value.mode

    def set_mode(self, mode: AppMode) -> None:
        self._state.set(AppState(**{**self._state.value.__dict__, "mode": mode}))

    @property
    def model(self) -> str:
        return self._state.value.model

    def set_model(self, model: str) -> None:
        s = self._state.value
        self._state.set(AppState(**{**s.__dict__, "model": model}))

    @property
    def session_id(self) -> str:
        return self._state.value.session_id

    def set_session_id(self, session_id: str) -> None:
        s = self._state.value
        self._state.set(AppState(**{**s.__dict__, "session_id": session_id}))

    @property
    def workdir(self) -> str:
        return self._state.value.workdir

    def set_workdir(self, workdir: str) -> None:
        s = self._state.value
        self._state.set(AppState(**{**s.__dict__, "workdir": workdir}))

    @property
    def approval_mode(self) -> ApprovalMode:
        return self._state.value.approval_mode

    def set_approval_mode(self, mode: ApprovalMode) -> None:
        s = self._state.value
        self._state.set(AppState(**{**s.__dict__, "approval_mode": mode}))

    @property
    def is_plan_mode(self) -> bool:
        return self._state.value.plan_mode

    def set_plan_mode(self, enabled: bool) -> None:
        s = self._state.value
        self._state.set(AppState(**{**s.__dict__, "plan_mode": enabled, "mode": AppMode.PLAN if enabled else AppMode.INTERACTIVE}))

    # ---- change notifications --------------------------------------------

    def on_mode_change(self, cb) -> Callable[[], None]:
        """Register a callback for mode changes."""
        return self._state.on_change(
            lambda old, new: cb(new.mode) if old.mode != new.mode else None
        )

    def on_any_change(self, cb: Callable[[AppState, AppState], None]) -> Callable[[], None]:
        """Register a callback for any state change."""
        return self._state.on_change(cb)

    # ---- arbitrary extension ----------------------------------------------

    def set_extra(self, key: str, value: Any) -> None:
        self._store.set(key, value)

    def get_extra(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    # ---- snapshot ---------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Return a serializable dict of the current state."""
        s = self._state.value
        base = {
            "mode": s.mode.value,
            "model": s.model,
            "session_id": s.session_id,
            "workdir": s.workdir,
            "approval_mode": s.approval_mode.value,
            "stream_enabled": s.stream_enabled,
            "compaction_threshold": s.compaction_threshold,
            "team_mode": s.team_mode,
            "plan_mode": s.plan_mode,
            "cost_limit_usd": s.cost_limit_usd,
            "max_turns": s.max_turns,
        }
        base.update(self._store.snapshot())
        return base


__all__ = [
    "AppMode",
    "ApprovalMode",
    "AppState",
    "AppStateStore",
]
