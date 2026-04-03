"""
Lifecycle hooks — Python equivalents of React lifecycle / effect hooks.

Ports: hooks/useAfterFirstRender.ts, hooks/useMount.ts,
       hooks/useUnmount.ts, hooks/useInterval.ts, hooks/useTimeout.ts,
       hooks/useDebounce.ts, hooks/useThrottle.ts, hooks/usePrevious.ts
"""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from typing import Any, Callable, Generator, TypeVar

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Debounce
# ---------------------------------------------------------------------------

class Debouncer:
    """
    Debounce a callable — only executes after `delay` seconds of quiet.

    Python equivalent of React useDebounce.
    """

    def __init__(self, fn: Callable, delay: float):
        self._fn = fn
        self._delay = delay
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def __call__(self, *args, **kwargs) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(
                self._delay, self._fn, args=args, kwargs=kwargs
            )
            self._timer.daemon = True
            self._timer.start()

    def flush(self) -> None:
        """Cancel debounce and run immediately."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        self._fn()

    def cancel(self) -> None:
        """Cancel any pending invocation."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None


def debounce(fn: Callable, delay: float) -> Debouncer:
    """Create a debounced version of `fn`."""
    return Debouncer(fn, delay)


# ---------------------------------------------------------------------------
# Throttle
# ---------------------------------------------------------------------------

class Throttler:
    """
    Throttle a callable — executes at most once per `interval` seconds.

    Python equivalent of useThrottle.
    """

    def __init__(self, fn: Callable, interval: float):
        self._fn = fn
        self._interval = interval
        self._last: float = 0.0
        self._lock = threading.Lock()

    def __call__(self, *args, **kwargs) -> bool:
        """Call fn if throttle interval has passed. Returns True if called."""
        with self._lock:
            now = time.monotonic()
            if now - self._last >= self._interval:
                self._last = now
                should_call = True
            else:
                should_call = False

        if should_call:
            self._fn(*args, **kwargs)
        return should_call

    def reset(self) -> None:
        with self._lock:
            self._last = 0.0


def throttle(fn: Callable, interval: float) -> Throttler:
    """Create a throttled version of `fn`."""
    return Throttler(fn, interval)


# ---------------------------------------------------------------------------
# Interval
# ---------------------------------------------------------------------------

class Interval:
    """
    Run a function on a repeating interval.

    Python equivalent of React useInterval.
    """

    def __init__(self, fn: Callable, interval_s: float, immediate: bool = False):
        self._fn = fn
        self._interval = interval_s
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        if immediate:
            try:
                fn()
            except Exception:
                pass

    def start(self) -> "Interval":
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def _run(self) -> None:
        while not self._stop_event.wait(self._interval):
            try:
                self._fn()
            except Exception:
                pass

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=self._interval + 1)
            self._thread = None

    def __enter__(self) -> "Interval":
        return self.start()

    def __exit__(self, *_) -> None:
        self.stop()


@contextmanager
def interval(fn: Callable, seconds: float, immediate: bool = False):
    """Context manager for repeating intervals."""
    iv = Interval(fn, seconds, immediate=immediate)
    iv.start()
    try:
        yield iv
    finally:
        iv.stop()


# ---------------------------------------------------------------------------
# Timeout (one-shot delayed call)
# ---------------------------------------------------------------------------

class Timeout:
    """
    One-shot delayed function call.

    Python equivalent of React useTimeout.
    """

    def __init__(self, fn: Callable, delay_s: float):
        self._fn = fn
        self._delay = delay_s
        self._timer: threading.Timer | None = None

    def start(self) -> "Timeout":
        self._timer = threading.Timer(self._delay, self._fn)
        self._timer.daemon = True
        self._timer.start()
        return self

    def cancel(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def reset(self) -> None:
        self.cancel()
        self.start()


# ---------------------------------------------------------------------------
# Previous value tracker
# ---------------------------------------------------------------------------

class PreviousTracker(object):
    """
    Track the previous value of a variable.

    Python equivalent of React usePrevious.
    """

    def __init__(self, initial: Any = None):
        self.previous: Any = initial
        self.current: Any = initial

    def update(self, value: Any) -> Any:
        """Update current, returns previous value."""
        self.previous = self.current
        self.current = value
        return self.previous


# ---------------------------------------------------------------------------
# Mount / unmount lifecycle
# ---------------------------------------------------------------------------

class LifecycleManager:
    """
    Manage mount/unmount callbacks for a component/service lifetime.

    Python equivalent of useMount + useUnmount + useEffect cleanup.
    """

    def __init__(self):
        self._cleanups: list[Callable] = []
        self._mounted = False

    def mount(self, *callbacks: Callable) -> None:
        """Run mount callbacks immediately."""
        for cb in callbacks:
            try:
                cleanup = cb()
                if callable(cleanup):
                    self._cleanups.append(cleanup)
            except Exception:
                pass
        self._mounted = True

    def add_cleanup(self, fn: Callable) -> None:
        """Register a cleanup to run on unmount."""
        self._cleanups.append(fn)

    def unmount(self) -> None:
        """Run all cleanups in reverse order."""
        self._mounted = False
        for cleanup in reversed(self._cleanups):
            try:
                cleanup()
            except Exception:
                pass
        self._cleanups.clear()

    @property
    def is_mounted(self) -> bool:
        return self._mounted

    def __enter__(self) -> "LifecycleManager":
        return self

    def __exit__(self, *_) -> None:
        self.unmount()


# ---------------------------------------------------------------------------
# After-first-render equivalent (run once, after initialization)
# ---------------------------------------------------------------------------

class AfterInit:
    """
    Run a callback once after the first call to `mark_ready()`.

    Python equivalent of useAfterFirstRender.
    """

    def __init__(self):
        self._ready = False
        self._callbacks: list[Callable] = []

    def after_ready(self, fn: Callable) -> None:
        """Register a callback to run after init."""
        if self._ready:
            fn()
        else:
            self._callbacks.append(fn)

    def mark_ready(self) -> None:
        """Mark initialization complete and run pending callbacks."""
        if not self._ready:
            self._ready = True
            for fn in self._callbacks:
                try:
                    fn()
                except Exception:
                    pass
            self._callbacks.clear()

    @property
    def is_ready(self) -> bool:
        return self._ready


__all__ = [
    "Debouncer", "debounce",
    "Throttler", "throttle",
    "Interval", "interval",
    "Timeout",
    "PreviousTracker",
    "LifecycleManager",
    "AfterInit",
]
