"""
Event hooks — Python equivalents of React event hooks.

Ports: hooks/useKeyPress.ts, hooks/useWindowSize.ts, hooks/useClipboard.ts,
       hooks/useAsyncEffect.ts, hooks/useLatest.ts, hooks/useSafeCallback.ts,
       hooks/useIsMounted.ts, hooks/renderPlaceholder.ts
"""
from __future__ import annotations

import asyncio
import signal
import subprocess
import sys
import threading
from contextlib import contextmanager
from typing import Any, Callable, Coroutine, TypeVar

from .state_hooks import Signal, EventEmitter

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Clipboard
# ---------------------------------------------------------------------------

class Clipboard:
    """
    Cross-platform clipboard access.

    Python equivalent of useClipboard.
    """

    @staticmethod
    def copy(text: str) -> bool:
        """Copy text to clipboard. Returns True on success."""
        try:
            if sys.platform == "darwin":
                proc = subprocess.run(["pbcopy"], input=text.encode(), check=True)
                return True
            elif sys.platform.startswith("linux"):
                for cmd in [["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]:
                    try:
                        subprocess.run(cmd, input=text.encode(), check=True, capture_output=True)
                        return True
                    except (FileNotFoundError, subprocess.CalledProcessError):
                        continue
            elif sys.platform == "win32":
                import subprocess
                proc = subprocess.run(["clip"], input=text.encode(), check=True)
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def paste() -> str | None:
        """Read text from clipboard. Returns None on failure."""
        try:
            if sys.platform == "darwin":
                result = subprocess.run(["pbpaste"], capture_output=True)
                return result.stdout.decode()
            elif sys.platform.startswith("linux"):
                for cmd in [["xclip", "-selection", "clipboard", "-o"], ["xsel", "--clipboard", "--output"]]:
                    try:
                        result = subprocess.run(cmd, capture_output=True, check=True)
                        return result.stdout.decode()
                    except (FileNotFoundError, subprocess.CalledProcessError):
                        continue
            elif sys.platform == "win32":
                result = subprocess.run(["powershell", "-command", "Get-Clipboard"], capture_output=True)
                return result.stdout.decode()
        except Exception:
            pass
        return None


# ---------------------------------------------------------------------------
# Signal / interrupt handling
# ---------------------------------------------------------------------------

class SignalHandler:
    """
    Manage OS signal handlers (SIGINT, SIGTERM, etc.).

    Python equivalent of useKeyPress for Ctrl+C, etc.
    """

    def __init__(self):
        self._handlers: dict[int, list[Callable]] = {}
        self._original: dict[int, Any] = {}
        self._emitter = EventEmitter()

    def on(self, sig: int, handler: Callable) -> Callable[[], None]:
        """Register a signal handler. Returns unregister function."""
        if sig not in self._handlers:
            self._handlers[sig] = []
            try:
                self._original[sig] = signal.getsignal(sig)
                signal.signal(sig, self._dispatch)
            except (OSError, ValueError):
                pass

        self._handlers[sig].append(handler)

        def off():
            try:
                self._handlers[sig].remove(handler)
            except ValueError:
                pass
            if not self._handlers[sig]:
                # Restore original handler
                orig = self._original.get(sig, signal.SIG_DFL)
                try:
                    signal.signal(sig, orig)
                except (OSError, ValueError):
                    pass

        return off

    def _dispatch(self, sig: int, frame: Any) -> None:
        for handler in list(self._handlers.get(sig, [])):
            try:
                handler(sig, frame)
            except Exception:
                pass


# Default global signal handler instance
_global_signal_handler = SignalHandler()


def on_interrupt(callback: Callable) -> Callable[[], None]:
    """Register a SIGINT handler. Returns unregister function."""
    return _global_signal_handler.on(signal.SIGINT, callback)


def on_terminate(callback: Callable) -> Callable[[], None]:
    """Register a SIGTERM handler. Returns unregister function."""
    return _global_signal_handler.on(signal.SIGTERM, callback)


# ---------------------------------------------------------------------------
# Is-mounted guard
# ---------------------------------------------------------------------------

class IsMounted:
    """
    Track whether a component/context is still mounted/active.

    Python equivalent of useIsMounted.
    """

    def __init__(self):
        self._mounted = True

    @property
    def value(self) -> bool:
        return self._mounted

    def unmount(self) -> None:
        self._mounted = False

    def guard(self, fn: Callable) -> Callable:
        """Wrap a callback to only call if still mounted."""
        def wrapper(*args, **kwargs):
            if self._mounted:
                return fn(*args, **kwargs)
        return wrapper

    def __bool__(self) -> bool:
        return self._mounted

    def __enter__(self) -> "IsMounted":
        return self

    def __exit__(self, *_) -> None:
        self.unmount()


# ---------------------------------------------------------------------------
# Safe callback (no-op after unmount)
# ---------------------------------------------------------------------------

def safe_callback(fn: Callable, is_mounted: IsMounted) -> Callable:
    """
    Wrap a callback so it's a no-op if is_mounted is False.

    Python equivalent of useSafeCallback.
    """
    def wrapper(*args, **kwargs):
        if is_mounted.value:
            return fn(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Latest ref — always holds the most recent value
# ---------------------------------------------------------------------------

class LatestRef:
    """
    Always holds the latest value of something.

    Python equivalent of useLatest (avoids stale closures).
    """

    def __init__(self, initial: Any = None):
        self._value = initial
        self._lock = threading.Lock()

    def set(self, value: Any) -> None:
        with self._lock:
            self._value = value

    def get(self) -> Any:
        with self._lock:
            return self._value

    @property
    def current(self) -> Any:
        return self.get()


# ---------------------------------------------------------------------------
# Async effect runner
# ---------------------------------------------------------------------------

class AsyncEffect:
    """
    Run an async coroutine as a background effect.

    Python equivalent of useAsyncEffect.
    """

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def run(
        self,
        coro_fn: Callable[[], Coroutine],
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        """Start the async effect."""
        self.cancel()

        async def _wrapper():
            try:
                await coro_fn()
            except asyncio.CancelledError:
                pass
            except Exception as e:
                if on_error:
                    on_error(e)

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                self._task = loop.create_task(_wrapper())
            else:
                loop.run_until_complete(_wrapper())
        except RuntimeError:
            # No event loop — run in thread
            def thread_run():
                asyncio.run(_wrapper())
            t = threading.Thread(target=thread_run, daemon=True)
            t.start()

    def cancel(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None


# ---------------------------------------------------------------------------
# Render placeholder (for async loading states)
# ---------------------------------------------------------------------------

class Placeholder:
    """
    Manage a loading/placeholder state.

    Python equivalent of renderPlaceholder.ts — tracks loading/ready/error states.
    """

    def __init__(self, placeholder: Any = None):
        self.state = Signal("loading")   # "loading" | "ready" | "error"
        self.data: Signal[Any] = Signal(None)
        self.error: Signal[Exception | None] = Signal(None)
        self.placeholder = placeholder

    def set_loading(self) -> None:
        self.state.set("loading")
        self.error.set(None)

    def set_ready(self, data: Any) -> None:
        self.data.set(data)
        self.state.set("ready")

    def set_error(self, error: Exception) -> None:
        self.error.set(error)
        self.state.set("error")

    @property
    def is_loading(self) -> bool:
        return self.state.get() == "loading"

    @property
    def is_ready(self) -> bool:
        return self.state.get() == "ready"

    @property
    def has_error(self) -> bool:
        return self.state.get() == "error"

    def render(
        self,
        on_loading: Callable | None = None,
        on_ready: Callable[[Any], Any] | None = None,
        on_error: Callable[[Exception], Any] | None = None,
    ) -> Any:
        """
        Render based on current state — pattern matching equivalent.
        """
        s = self.state.get()
        if s == "loading":
            return on_loading() if on_loading else self.placeholder
        elif s == "ready":
            return on_ready(self.data.get()) if on_ready else self.data.get()
        elif s == "error":
            return on_error(self.error.get()) if on_error else str(self.error.get())


__all__ = [
    "Clipboard",
    "SignalHandler",
    "on_interrupt",
    "on_terminate",
    "IsMounted",
    "safe_callback",
    "LatestRef",
    "AsyncEffect",
    "Placeholder",
]
