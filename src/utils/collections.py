"""
Useful data-structure utilities.

Ports: utils/CircularBuffer.ts, utils/QueryGuard.ts, and collection helpers.
"""
from __future__ import annotations

import threading
from collections import deque
from typing import Generic, Iterator, TypeVar

T = TypeVar("T")


class CircularBuffer(Generic[T]):
    """
    Fixed-size circular buffer (ring buffer).

    When full, adding a new item overwrites the oldest.
    Ports: utils/CircularBuffer.ts
    """

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        self._buf: deque[T] = deque(maxlen=capacity)

    @property
    def capacity(self) -> int:
        return self._buf.maxlen  # type: ignore[return-value]

    def __len__(self) -> int:
        return len(self._buf)

    def __iter__(self) -> Iterator[T]:
        return iter(self._buf)

    def push(self, item: T) -> None:
        """Add *item*; discards oldest if buffer is full."""
        self._buf.append(item)

    def pop(self) -> T:
        """Remove and return the oldest item."""
        return self._buf.popleft()

    def peek(self) -> T | None:
        """Return the oldest item without removing it, or None if empty."""
        return self._buf[0] if self._buf else None

    def peek_latest(self) -> T | None:
        """Return the most-recently-added item without removing it."""
        return self._buf[-1] if self._buf else None

    def to_list(self) -> list[T]:
        """Return all items as a list (oldest first)."""
        return list(self._buf)

    def clear(self) -> None:
        self._buf.clear()

    @property
    def is_full(self) -> bool:
        return len(self._buf) == self._buf.maxlen

    @property
    def is_empty(self) -> bool:
        return len(self._buf) == 0


class QueryGuard:
    """
    Rate / concurrency guard for repeated queries.

    Prevents duplicate or too-frequent calls to the same key.
    Ports: utils/QueryGuard.ts
    """

    def __init__(self, cooldown_seconds: float = 1.0) -> None:
        self._cooldown = cooldown_seconds
        self._last_call: dict[str, float] = {}
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        """Return True if the query for *key* is currently permitted."""
        import time
        with self._lock:
            now = time.monotonic()
            last = self._last_call.get(key, 0.0)
            if now - last >= self._cooldown:
                self._last_call[key] = now
                return True
            return False

    def reset(self, key: str | None = None) -> None:
        """Reset cooldown for *key* (or all keys if None)."""
        with self._lock:
            if key is None:
                self._last_call.clear()
            else:
                self._last_call.pop(key, None)


class LRUCache(Generic[T]):
    """
    Simple LRU cache with a maximum size.
    """

    def __init__(self, maxsize: int = 128) -> None:
        from collections import OrderedDict
        self._cache: "OrderedDict[str, T]" = __import__("collections").OrderedDict()
        self._maxsize = maxsize

    def get(self, key: str, default: T | None = None) -> T | None:
        if key not in self._cache:
            return default
        self._cache.move_to_end(key)
        return self._cache[key]

    def set(self, key: str, value: T) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

    def __contains__(self, key: str) -> bool:
        return key in self._cache

    def __len__(self) -> int:
        return len(self._cache)

    def clear(self) -> None:
        self._cache.clear()


class FrozenDict(dict):
    """An immutable dictionary."""

    def __hash__(self):  # type: ignore[override]
        return hash(tuple(sorted(self.items())))

    def _raise(self, *args, **kwargs):
        raise TypeError("FrozenDict does not support item assignment")

    __setitem__ = __delitem__ = clear = update = setdefault = pop = popitem = _raise  # type: ignore[assignment]


__all__ = [
    "CircularBuffer",
    "QueryGuard",
    "LRUCache",
    "FrozenDict",
]
