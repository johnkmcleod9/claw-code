"""
State management hooks — Python equivalents of React hooks.

Ports: hooks/useAtom.ts, hooks/useLocalStorage.ts, hooks/useState.ts,
       hooks/useReducer.ts, hooks/useRef.ts, hooks/useMemo.ts
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Signal / observable value (replaces React useState / jotai atoms)
# ---------------------------------------------------------------------------

class Signal(Generic[T]):
    """
    Observable mutable value with subscriber callbacks.

    Python equivalent of React useState + jotai atom.
    Usage:
        count = Signal(0)
        count.subscribe(lambda v: print(f"count={v}"))
        count.set(1)          # triggers callbacks
        x = count.get()
    """

    def __init__(self, initial: T, name: str = ""):
        self._value: T = initial
        self._name = name
        self._subscribers: list[Callable[[T], None]] = []
        self._lock = threading.Lock()

    def get(self) -> T:
        with self._lock:
            return self._value

    def set(self, value: T) -> None:
        with self._lock:
            old = self._value
            self._value = value
            subs = list(self._subscribers)
        if old != value:
            for sub in subs:
                try:
                    sub(value)
                except Exception:
                    pass

    def update(self, fn: Callable[[T], T]) -> None:
        """Apply a transform function to the current value."""
        with self._lock:
            old = self._value
            new = fn(old)
            self._value = new
            subs = list(self._subscribers)
        if old != new:
            for sub in subs:
                try:
                    sub(new)
                except Exception:
                    pass

    def subscribe(self, callback: Callable[[T], None]) -> Callable[[], None]:
        """
        Subscribe to value changes. Returns an unsubscribe function.
        """
        with self._lock:
            self._subscribers.append(callback)

        def unsubscribe():
            with self._lock:
                try:
                    self._subscribers.remove(callback)
                except ValueError:
                    pass

        return unsubscribe

    def __repr__(self) -> str:
        name = f"Signal({self._name})" if self._name else "Signal"
        return f"{name}={self._value!r}"


# ---------------------------------------------------------------------------
# Derived / computed signal (replaces useMemo)
# ---------------------------------------------------------------------------

class Derived(Generic[T]):
    """
    A computed signal that recalculates when dependencies change.

    Python equivalent of React useMemo.
    """

    def __init__(self, compute: Callable[[], T], deps: list[Signal]):
        self._compute = compute
        self._deps = deps
        self._value: T = compute()
        self._lock = threading.Lock()
        self._subscribers: list[Callable[[T], None]] = []

        for dep in deps:
            dep.subscribe(self._on_dep_change)

    def _on_dep_change(self, _: Any) -> None:
        with self._lock:
            old = self._value
            new = self._compute()
            self._value = new
            subs = list(self._subscribers)
        if old != new:
            for sub in subs:
                try:
                    sub(new)
                except Exception:
                    pass

    def get(self) -> T:
        with self._lock:
            return self._value

    def subscribe(self, callback: Callable[[T], None]) -> Callable[[], None]:
        with self._lock:
            self._subscribers.append(callback)

        def unsubscribe():
            with self._lock:
                try:
                    self._subscribers.remove(callback)
                except ValueError:
                    pass

        return unsubscribe


# ---------------------------------------------------------------------------
# Ref (mutable container, no reactivity)
# ---------------------------------------------------------------------------

class Ref(Generic[T]):
    """
    Mutable reference — Python equivalent of React useRef.
    Holds a value without triggering re-renders.
    """

    def __init__(self, initial: T | None = None):
        self.current: T | None = initial

    def __repr__(self) -> str:
        return f"Ref({self.current!r})"


# ---------------------------------------------------------------------------
# Reducer pattern (replaces React useReducer)
# ---------------------------------------------------------------------------

Action = dict[str, Any]
Reducer = Callable[[T, Action], T]


class Store(Generic[T]):
    """
    Redux-style state store.

    Python equivalent of React useReducer / Redux store.
    """

    def __init__(self, reducer: Reducer, initial_state: T):
        self._reducer = reducer
        self._state = Signal(initial_state, name="store")
        self._middleware: list[Callable] = []

    @property
    def state(self) -> T:
        return self._state.get()

    def dispatch(self, action: Action) -> None:
        """Dispatch an action to update state."""
        current = self._state.get()
        new_state = self._reducer(current, action)
        self._state.set(new_state)

    def subscribe(self, callback: Callable[[T], None]) -> Callable[[], None]:
        return self._state.subscribe(callback)

    def select(self, selector: Callable[[T], Any]) -> Derived:
        """Create a derived signal from the store state."""
        return Derived(lambda: selector(self._state.get()), deps=[self._state])


# ---------------------------------------------------------------------------
# Persisted signal (replaces useLocalStorage)
# ---------------------------------------------------------------------------

class PersistedSignal(Signal[T]):
    """
    A signal that persists its value to a JSON file.

    Python equivalent of React useLocalStorage.
    """

    def __init__(self, key: str, initial: T, storage_dir: Path | None = None):
        self._key = key
        self._storage_path = (storage_dir or Path.home() / ".claw-code" / "state") / f"{key}.json"

        # Load persisted value
        loaded = self._load()
        super().__init__(loaded if loaded is not None else initial, name=f"persisted:{key}")

        # Subscribe to persist changes
        self.subscribe(self._save)

    def _load(self) -> T | None:
        try:
            if self._storage_path.exists():
                data = json.loads(self._storage_path.read_text())
                return data.get("value")
        except Exception:
            pass
        return None

    def _save(self, value: T) -> None:
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            self._storage_path.write_text(json.dumps({"value": value}))
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Event emitter (useEffect equivalent for side effects)
# ---------------------------------------------------------------------------

class EventEmitter:
    """
    Simple event emitter — Python equivalent of React useEffect with events.
    """

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = {}
        self._lock = threading.Lock()

    def on(self, event: str, handler: Callable) -> Callable[[], None]:
        """Register an event handler. Returns off() function."""
        with self._lock:
            self._handlers.setdefault(event, []).append(handler)

        def off():
            with self._lock:
                handlers = self._handlers.get(event, [])
                try:
                    handlers.remove(handler)
                except ValueError:
                    pass

        return off

    def once(self, event: str, handler: Callable) -> None:
        """Register a one-time handler."""
        def wrapper(*args, **kwargs):
            off()
            handler(*args, **kwargs)

        off = self.on(event, wrapper)

    def emit(self, event: str, *args, **kwargs) -> None:
        """Emit an event, calling all registered handlers."""
        with self._lock:
            handlers = list(self._handlers.get(event, []))
        for h in handlers:
            try:
                h(*args, **kwargs)
            except Exception:
                pass

    def off(self, event: str, handler: Callable | None = None) -> None:
        """Remove handler(s) for an event."""
        with self._lock:
            if handler is None:
                self._handlers.pop(event, None)
            else:
                handlers = self._handlers.get(event, [])
                try:
                    handlers.remove(handler)
                except ValueError:
                    pass


__all__ = [
    "Signal",
    "Derived",
    "Ref",
    "Store",
    "PersistedSignal",
    "EventEmitter",
    "Action",
    "Reducer",
]
