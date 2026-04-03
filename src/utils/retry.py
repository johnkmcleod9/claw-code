"""
Retry and backoff utilities.

Ports: utils/abortController.ts, utils/api.ts (retry logic portions)
"""
from __future__ import annotations

import asyncio
import inspect
import logging
import random
import time
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryExhausted(Exception):
    """Raised when all retry attempts fail."""

    def __init__(self, attempts: int, last_error: Exception) -> None:
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"Exhausted {attempts} retry attempts. Last error: {last_error}")


def _jitter(value: float, factor: float = 0.25) -> float:
    """Apply random jitter ±factor to a value."""
    return value * (1 + random.uniform(-factor, factor))


def retry_sync(
    fn: Callable[..., T],
    *args,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff: float = 2.0,
    jitter: bool = True,
    retryable: tuple[type[Exception], ...] = (Exception,),
    **kwargs,
) -> T:
    """
    Synchronous retry with exponential backoff.

    Args:
        fn: Callable to retry.
        max_attempts: Maximum number of attempts.
        base_delay: Initial delay in seconds.
        max_delay: Maximum delay between retries.
        backoff: Multiplier applied to delay after each failure.
        jitter: Whether to add random jitter to avoid thundering herd.
        retryable: Exception types that trigger a retry.
    """
    last_error: Exception = RuntimeError("No attempts made")
    delay = base_delay

    for attempt in range(1, max_attempts + 1):
        try:
            return fn(*args, **kwargs)
        except retryable as exc:
            last_error = exc
            if attempt == max_attempts:
                break
            sleep_for = min(_jitter(delay) if jitter else delay, max_delay)
            logger.debug("Attempt %d/%d failed (%s). Retrying in %.2fs", attempt, max_attempts, exc, sleep_for)
            time.sleep(sleep_for)
            delay = min(delay * backoff, max_delay)

    raise RetryExhausted(max_attempts, last_error)


async def retry_async(
    fn: Callable[..., Awaitable[T]],
    *args,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff: float = 2.0,
    jitter: bool = True,
    retryable: tuple[type[Exception], ...] = (Exception,),
    **kwargs,
) -> T:
    """
    Async retry with exponential backoff.

    Args:
        fn: Async callable to retry.
        max_attempts: Maximum number of attempts.
        base_delay: Initial delay in seconds.
        max_delay: Maximum delay between retries.
        backoff: Multiplier applied to delay after each failure.
        jitter: Whether to add random jitter.
        retryable: Exception types that trigger a retry.
    """
    last_error: Exception = RuntimeError("No attempts made")
    delay = base_delay

    for attempt in range(1, max_attempts + 1):
        try:
            return await fn(*args, **kwargs)
        except retryable as exc:
            last_error = exc
            if attempt == max_attempts:
                break
            sleep_for = min(_jitter(delay) if jitter else delay, max_delay)
            logger.debug("Attempt %d/%d failed (%s). Retrying in %.2fs", attempt, max_attempts, exc, sleep_for)
            await asyncio.sleep(sleep_for)
            delay = min(delay * backoff, max_delay)

    raise RetryExhausted(max_attempts, last_error)


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff: float = 2.0,
    jitter: bool = True,
    retryable: tuple[type[Exception], ...] = (Exception,),
):
    """
    Decorator to add retry behaviour to a sync or async function.

    Example::

        @with_retry(max_attempts=5, retryable=(ConnectionError,))
        async def fetch(url: str) -> str:
            ...
    """
    def decorator(fn: Callable) -> Callable:
        if inspect.iscoroutinefunction(fn):
            @wraps(fn)
            async def async_wrapper(*args, **kwargs):
                return await retry_async(
                    fn, *args,
                    max_attempts=max_attempts,
                    base_delay=base_delay,
                    max_delay=max_delay,
                    backoff=backoff,
                    jitter=jitter,
                    retryable=retryable,
                    **kwargs,
                )
            return async_wrapper
        else:
            @wraps(fn)
            def sync_wrapper(*args, **kwargs):
                return retry_sync(
                    fn, *args,
                    max_attempts=max_attempts,
                    base_delay=base_delay,
                    max_delay=max_delay,
                    backoff=backoff,
                    jitter=jitter,
                    retryable=retryable,
                    **kwargs,
                )
            return sync_wrapper
    return decorator


class CircuitBreaker:
    """
    Simple circuit breaker to stop hammering a failing service.

    States: CLOSED (normal) → OPEN (failing) → HALF_OPEN (testing).
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max: int = 1,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max

        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._half_open_calls = 0

    @property
    def state(self) -> str:
        if self._state == self.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                self._state = self.HALF_OPEN
                self._half_open_calls = 0
        return self._state

    def call(self, fn: Callable[..., T], *args, **kwargs) -> T:
        state = self.state
        if state == self.OPEN:
            raise RuntimeError("Circuit breaker is OPEN — service unavailable")
        if state == self.HALF_OPEN and self._half_open_calls >= self.half_open_max:
            raise RuntimeError("Circuit breaker is HALF_OPEN — probe limit reached")

        if state == self.HALF_OPEN:
            self._half_open_calls += 1

        try:
            result = fn(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        self._state = self.CLOSED
        self._failure_count = 0

    def _on_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = self.OPEN


__all__ = [
    "RetryExhausted",
    "retry_sync",
    "retry_async",
    "with_retry",
    "CircuitBreaker",
]
