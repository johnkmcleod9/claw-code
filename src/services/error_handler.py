"""
Error handling and classification service.

Ports: services/api/errors.ts, services/api/errorUtils.ts,
       services/errors/ (error classification, reporting)
"""
from __future__ import annotations

import traceback
from enum import Enum
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Error categories
# ---------------------------------------------------------------------------

class ErrorCategory(Enum):
    """High-level classification of errors."""
    NETWORK = "network"
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    CONTEXT_OVERFLOW = "context_overflow"
    INVALID_REQUEST = "invalid_request"
    SERVER = "server"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class ErrorSeverity(Enum):
    """Severity level for error reporting."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Structured error
# ---------------------------------------------------------------------------

class ClawError(Exception):
    """
    Structured error with category, code, and optional metadata.

    This is the base error class used across the application.
    """

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        code: str | None = None,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        retryable: bool = False,
        cause: Exception | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.code = code
        self.severity = severity
        self.retryable = retryable
        self.cause = cause
        self.metadata: dict[str, Any] = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": str(self),
            "category": self.category.value,
            "code": self.code,
            "severity": self.severity.value,
            "retryable": self.retryable,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"ClawError({str(self)!r}, category={self.category.value}, "
            f"code={self.code!r}, retryable={self.retryable})"
        )


# ---------------------------------------------------------------------------
# Specialised error subclasses
# ---------------------------------------------------------------------------

class NetworkError(ClawError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, category=ErrorCategory.NETWORK, retryable=True, **kwargs)


class AuthenticationError(ClawError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, category=ErrorCategory.AUTH, retryable=False, **kwargs)


class RateLimitError(ClawError):
    def __init__(self, message: str, retry_after: float | None = None, **kwargs: Any) -> None:
        meta = kwargs.pop("metadata", {})
        if retry_after is not None:
            meta["retry_after"] = retry_after
        super().__init__(
            message,
            category=ErrorCategory.RATE_LIMIT,
            retryable=True,
            metadata=meta,
            **kwargs,
        )
        self.retry_after = retry_after


class ContextOverflowError(ClawError):
    def __init__(self, message: str, token_count: int | None = None, **kwargs: Any) -> None:
        meta = kwargs.pop("metadata", {})
        if token_count is not None:
            meta["token_count"] = token_count
        super().__init__(
            message,
            category=ErrorCategory.CONTEXT_OVERFLOW,
            retryable=False,
            metadata=meta,
            **kwargs,
        )
        self.token_count = token_count


class TimeoutError(ClawError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, category=ErrorCategory.TIMEOUT, retryable=True, **kwargs)


class CancelledError(ClawError):
    def __init__(self, message: str = "Operation cancelled", **kwargs: Any) -> None:
        super().__init__(message, category=ErrorCategory.CANCELLED, retryable=False, **kwargs)


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

def classify_exception(exc: Exception) -> ClawError:
    """
    Convert an arbitrary exception into a ClawError with appropriate category.

    This is the central error classifier used by all service layers.
    """
    if isinstance(exc, ClawError):
        return exc

    msg = str(exc)
    exc_type = type(exc).__name__

    # Standard library errors
    if isinstance(exc, (ConnectionError, ConnectionRefusedError, ConnectionResetError)):
        return NetworkError(msg, cause=exc)
    if isinstance(exc, TimeoutError):
        return TimeoutError(msg, cause=exc)  # type: ignore[call-arg]

    # Pattern matching on message
    lower = msg.lower()
    if "rate limit" in lower or "429" in lower:
        return RateLimitError(msg, cause=exc)
    if "unauthorized" in lower or "forbidden" in lower or "401" in lower or "403" in lower:
        return AuthenticationError(msg, cause=exc)
    if "context" in lower and ("window" in lower or "length" in lower or "overflow" in lower):
        return ContextOverflowError(msg, cause=exc)
    if "timeout" in lower or "timed out" in lower:
        return TimeoutError(msg, cause=exc)  # type: ignore[call-arg]
    if "cancel" in lower:
        return CancelledError(msg, cause=exc)

    return ClawError(msg, cause=exc, code=exc_type)


def is_retryable(exc: Exception) -> bool:
    """Return True if the error is safe to retry."""
    if isinstance(exc, ClawError):
        return exc.retryable
    classified = classify_exception(exc)
    return classified.retryable


# ---------------------------------------------------------------------------
# Error reporter
# ---------------------------------------------------------------------------

ErrorHandler = Callable[[ClawError], None]


class ErrorReporter:
    """
    Collects and dispatches error events to registered handlers.

    Ports: services/errors/errorReporter.ts (conceptual)
    """

    def __init__(self) -> None:
        self._handlers: list[ErrorHandler] = []

    def add_handler(self, handler: ErrorHandler) -> Callable[[], None]:
        """Register a handler; returns an unsubscribe function."""
        self._handlers.append(handler)

        def remove() -> None:
            self._handlers.remove(handler)

        return remove

    def report(self, exc: Exception, context: str = "") -> ClawError:
        """
        Classify exc, optionally add context, and dispatch to all handlers.

        Returns the ClawError so callers can inspect it.
        """
        claw_err = classify_exception(exc)
        if context:
            claw_err.metadata.setdefault("context", context)
        for handler in self._handlers:
            try:
                handler(claw_err)
            except Exception:  # noqa: BLE001
                pass  # Never let a handler crash the caller
        return claw_err

    def format_traceback(self, exc: Exception) -> str:
        """Return a compact traceback string for logging."""
        return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


# Module-level singleton
_reporter: ErrorReporter | None = None


def get_reporter() -> ErrorReporter:
    global _reporter
    if _reporter is None:
        _reporter = ErrorReporter()
    return _reporter


def report_error(exc: Exception, context: str = "") -> ClawError:
    """Convenience wrapper around the global reporter."""
    return get_reporter().report(exc, context)


__all__ = [
    "AuthenticationError",
    "CancelledError",
    "ClawError",
    "ContextOverflowError",
    "ErrorCategory",
    "ErrorReporter",
    "ErrorSeverity",
    "NetworkError",
    "RateLimitError",
    "TimeoutError",
    "classify_exception",
    "get_reporter",
    "is_retryable",
    "report_error",
]
