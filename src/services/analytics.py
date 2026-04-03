"""
Analytics / telemetry service — lightweight event logging.

Ports: services/analytics/index.ts, services/analytics/sink.ts,
       services/analytics/sinkKillswitch.ts, services/analytics/metadata.ts

This implementation is intentionally minimal and privacy-preserving:
- No external calls unless explicitly configured
- Events are queued in memory and optionally written to a local log
- The killswitch (CLAW_NO_ANALYTICS=1) fully disables event capture
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def analytics_enabled() -> bool:
    """Return True unless the killswitch env var is set."""
    return os.environ.get("CLAW_NO_ANALYTICS", "").strip() not in ("1", "true", "yes")


@dataclass
class AnalyticsEvent:
    """A single telemetry event."""
    event: str
    properties: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    session_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class NullSink:
    """Sink that discards everything (used when analytics is disabled)."""
    def record(self, event: AnalyticsEvent) -> None:
        pass

    def flush(self) -> None:
        pass


class FileSink:
    """Write events as newline-delimited JSON to a local file."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event: AnalyticsEvent) -> None:
        with self._path.open("a") as fh:
            fh.write(json.dumps(event.to_dict()) + "\n")

    def flush(self) -> None:
        pass  # File writes are immediate


class MemorySink:
    """In-memory event sink (useful for testing)."""

    def __init__(self) -> None:
        self.events: list[AnalyticsEvent] = []

    def record(self, event: AnalyticsEvent) -> None:
        self.events.append(event)

    def flush(self) -> None:
        pass

    def clear(self) -> None:
        self.events.clear()


class Analytics:
    """
    Central analytics controller.

    Usage::

        analytics = Analytics(session_id="abc123")
        analytics.track("tool_executed", {"tool": "bash", "success": True})
    """

    def __init__(
        self,
        session_id: str = "",
        sink=None,
        enabled: bool | None = None,
    ) -> None:
        self.session_id = session_id
        _enabled = enabled if enabled is not None else analytics_enabled()
        self._sink = sink if sink is not None else (NullSink() if not _enabled else MemorySink())
        self._enabled = _enabled

    def track(self, event: str, properties: dict[str, Any] | None = None) -> None:
        """Record a named event with optional properties."""
        if not self._enabled:
            return
        evt = AnalyticsEvent(
            event=event,
            properties=properties or {},
            session_id=self.session_id,
        )
        self._sink.record(evt)

    def flush(self) -> None:
        self._sink.flush()

    # ------------------------------------------------------------------
    # Convenience event helpers
    # ------------------------------------------------------------------

    def tool_executed(self, tool_name: str, success: bool, duration_ms: float = 0.0) -> None:
        self.track("tool_executed", {
            "tool": tool_name,
            "success": success,
            "duration_ms": round(duration_ms, 2),
        })

    def session_started(self, model: str = "", workdir: str = "") -> None:
        self.track("session_started", {"model": model, "workdir": workdir})

    def session_ended(self, turns: int = 0, cost_usd: float = 0.0) -> None:
        self.track("session_ended", {"turns": turns, "cost_usd": round(cost_usd, 6)})

    def error_occurred(self, error_type: str, message: str = "") -> None:
        self.track("error", {"error_type": error_type, "message": message[:200]})

    def model_switched(self, from_model: str, to_model: str) -> None:
        self.track("model_switched", {"from": from_model, "to": to_model})


# Default no-op instance (safe to use without configuration)
_default: Analytics | None = None


def get_analytics() -> Analytics:
    global _default
    if _default is None:
        _default = Analytics()
    return _default


def configure_analytics(session_id: str, sink=None) -> Analytics:
    global _default
    _default = Analytics(session_id=session_id, sink=sink)
    return _default


__all__ = [
    "AnalyticsEvent",
    "NullSink",
    "FileSink",
    "MemorySink",
    "Analytics",
    "get_analytics",
    "configure_analytics",
    "analytics_enabled",
]
