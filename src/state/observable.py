"""
Observable state store with change notifications.

Ports: state/store.ts, state/AppStateStore.ts, state/onChangeAppState.ts
"""
from __future__ import annotations

import threading
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class Observable:
    """
    A thread-safe observable value.

    Notifies all registered callbacks whenever the value changes.
    """

    def __init__(self, initial: T) -> None:
        self._value = initial
        self._lock = threading.RLock()
        self._callbacks: list[Callable[[T, T], None]] = []

    @property
    def value(self) -> T:
        with self._lock:
            return self._value

    def set(self, new_value: T) -> None:
        with self._lock:
            old = self._value
            if old == new_value:
                return
            self._value = new_value
            old_snapshot = old
            new_snapshot = new_value
        # Notify outside the lock to avoid deadlock
        for cb in self._callbacks:
            cb(old_snapshot, new_snapshot)

    def on_change(self, callback: Callable[[T, T], None]) -> Callable[[], None]:
        """
        Register a callback to be called on every value change.

        Returns an unsubscribe function.
        """
        with self._lock:
            self._callbacks.append(callback)

        def unsubscribe() -> None:
            with self._lock:
                self._callbacks.remove(callback)

        return unsubscribe

    @property
    def observers(self) -> int:
        with self._lock:
            return len(self._callbacks)


class Store:
    """
    A simple key-value store with observable access.

    Ports: state/store.ts
    """

    def __init__(self, initial: dict[str, Any] | None = None) -> None:
        self._data = dict(initial or {})
        self._lock = threading.RLock()
        self._change_callbacks: dict[str, list[Callable[[Any, Any], None]]] = {}

    # ---- read -----------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        with self._lock:
            return self._data[key]

    def __contains__(self, key: str) -> bool:
        with self._lock:
            return key in self._data

    def keys(self) -> list[str]:
        with self._lock:
            return list(self._data.keys())

    def items(self) -> list[tuple[str, Any]]:
        with self._lock:
            return list(self._data.items())

    def snapshot(self) -> dict[str, Any]:
        """Return a copy of all stored data."""
        with self._lock:
            return dict(self._data)

    # ---- write ----------------------------------------------------------

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            old = self._data.get(key)
            self._data[key] = value
            if old is value and old == value:
                return
        self._notify(key, old, value)

    def update(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            self.set(key, value)

    def delete(self, key: str) -> bool:
        with self._lock:
            if key not in self._data:
                return False
            old = self._data.pop(key)
        self._notify(key, old, None)
        return True

    def clear(self) -> None:
        with self._lock:
            old_data = dict(self._data)
            self._data.clear()
        for k, v in old_data.items():
            self._notify(k, v, None)

    # ---- subscriptions --------------------------------------------------

    def watch(self, key: str, callback: Callable[[Any, Any], None]) -> Callable[[], None]:
        """Watch a specific key for changes. Returns unsubscribe function."""
        with self._lock:
            if key not in self._change_callbacks:
                self._change_callbacks[key] = []
            self._change_callbacks[key].append(callback)

        def unsubscribe() -> None:
            with self._lock:
                cbs = self._change_callbacks.get(key, [])
                if callback in cbs:
                    cbs.remove(callback)

        return unsubscribe

    def watch_all(self, callback: Callable[[str, Any, Any], None]) -> Callable[[], None]:
        """
        Watch all keys for changes.

        Callback receives (key, old_value, new_value).
        """
        with self._lock:
            wildcard = "__all__"
            if wildcard not in self._change_callbacks:
                self._change_callbacks[wildcard] = []
            self._change_callbacks[wildcard].append(callback)

        def unsubscribe() -> None:
            with self._lock:
                cbs = self._change_callbacks.get(wildcard, [])
                if callback in cbs:
                    cbs.remove(callback)

        return unsubscribe

    def _notify(self, key: str, old: Any, new: Any) -> None:
        with self._lock:
            for cb in self._change_callbacks.get(key, []):
                cb(old, new)
            for cb in self._change_callbacks.get("__all__", []):
                cb(key, old, new)


# ---------------------------------------------------------------------------
# Selectors (ports state/selectors.ts)
# ---------------------------------------------------------------------------

def select(store: Store, key: str, default: Any = None) -> Any:
    """Get a value from the store by key."""
    return store.get(key, default)


def select_many(store: Store, keys: list[str]) -> dict[str, Any]:
    """Get multiple values from the store."""
    with threading.Lock():
        return {k: store.get(k) for k in keys}


def select_where(store: Store, predicate: Callable[[str, Any], bool]) -> dict[str, Any]:
    """Select all key-value pairs where predicate returns True."""
    return {k: v for k, v in store.items() if predicate(k, v)}


# ---------------------------------------------------------------------------
# Teammate view helpers (ports state/teammateViewHelpers.ts)
# ---------------------------------------------------------------------------

def filter_private_keys(data: dict[str, Any], private_prefix: str = "_") -> dict[str, Any]:
    """Remove keys starting with private_prefix from a dict snapshot."""
    return {k: v for k, v in data.items() if not k.startswith(private_prefix)}


def make_teammate_view(store: Store) -> dict[str, Any]:
    """Return a filtered view of store data safe to share with teammates."""
    return filter_private_keys(store.snapshot())


def merge_state(local: dict[str, Any], remote: dict[str, Any], conflict_resolver: Callable[[str, Any, Any], Any] | None = None) -> dict[str, Any]:
    """
    Merge remote state into local state.

    Keys only in remote are added. Conflicting keys use *conflict_resolver*
    if provided, otherwise remote wins.
    """
    result = dict(local)
    for key, remote_value in remote.items():
        if key not in result:
            result[key] = remote_value
        elif conflict_resolver:
            result[key] = conflict_resolver(key, result[key], remote_value)
        else:
            result[key] = remote_value
    return result


__all__ = [
    "Observable",
    "Store",
    "select",
    "select_many",
    "select_where",
    "filter_private_keys",
    "make_teammate_view",
    "merge_state",
]
