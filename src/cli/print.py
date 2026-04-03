"""
CLI print / output helpers.

Ports: cli/print.ts, cli/structuredIO.ts, cli/ndjsonSafeStringify.ts
"""
from __future__ import annotations

import json
import sys
from enum import Enum
from typing import Any, TextIO


# ---------------------------------------------------------------------------
# Output modes
# ---------------------------------------------------------------------------

class OutputMode(Enum):
    """How the CLI renders output."""
    INTERACTIVE = "interactive"   # Human-readable, coloured
    PRINT = "print"               # Plain text, no colour
    JSON = "json"                 # Newline-delimited JSON (NDJSON)


# ---------------------------------------------------------------------------
# NDJSON helpers (cli/ndjsonSafeStringify.ts)
# ---------------------------------------------------------------------------

def _make_safe(obj: Any, depth: int = 0) -> Any:
    """Remove circular references and non-serialisable values."""
    if depth > 10:
        return "[max depth]"
    if isinstance(obj, dict):
        return {k: _make_safe(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_safe(v, depth + 1) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def ndjson_stringify(obj: Any) -> str:
    """
    Serialise *obj* to a single-line JSON string safe for NDJSON streams.

    Ports: cli/ndjsonSafeStringify.ts
    """
    return json.dumps(_make_safe(obj), ensure_ascii=False, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Structured I/O (cli/structuredIO.ts)
# ---------------------------------------------------------------------------

class StructuredWriter:
    """
    Writes output in either human-readable or NDJSON format.

    Ports: cli/structuredIO.ts
    """

    def __init__(
        self,
        mode: OutputMode = OutputMode.INTERACTIVE,
        stream: TextIO | None = None,
    ) -> None:
        self.mode = mode
        self._out = stream or sys.stdout

    # ---- core writes -------------------------------------------------

    def write(self, text: str) -> None:
        """Write raw text (always)."""
        self._out.write(text)
        self._out.flush()

    def writeln(self, text: str = "") -> None:
        self.write(text + "\n")

    def emit(self, event_type: str, data: Any = None) -> None:
        """
        Emit a structured event.

        In NDJSON mode: writes a JSON line ``{"type": ..., "data": ...}``.
        In other modes: writes a human-readable representation.
        """
        if self.mode == OutputMode.JSON:
            payload = {"type": event_type, "data": data}
            self.writeln(ndjson_stringify(payload))
        else:
            if data is not None:
                self.writeln(f"[{event_type}] {data}")

    # ---- typed events ------------------------------------------------

    def text(self, message: str) -> None:
        self.emit("text", message)

    def error(self, message: str, code: str | None = None) -> None:
        payload: dict[str, Any] = {"message": message}
        if code:
            payload["code"] = code
        self.emit("error", payload)
        if self.mode != OutputMode.JSON:
            # Also write to stderr for human modes
            sys.stderr.write(f"Error: {message}\n")
            sys.stderr.flush()

    def result(self, data: Any) -> None:
        self.emit("result", data)

    def info(self, message: str) -> None:
        if self.mode == OutputMode.INTERACTIVE:
            self.writeln(message)
        else:
            self.emit("info", message)

    def success(self, message: str) -> None:
        if self.mode == OutputMode.INTERACTIVE:
            self.writeln(f"✓ {message}")
        else:
            self.emit("success", {"message": message})


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------

_default_writer: StructuredWriter | None = None


def get_writer() -> StructuredWriter:
    global _default_writer
    if _default_writer is None:
        _default_writer = StructuredWriter()
    return _default_writer


def configure_writer(mode: OutputMode, stream: TextIO | None = None) -> StructuredWriter:
    global _default_writer
    _default_writer = StructuredWriter(mode=mode, stream=stream)
    return _default_writer


def print_text(message: str) -> None:
    get_writer().text(message)


def print_error(message: str, code: str | None = None) -> None:
    get_writer().error(message, code)


def print_result(data: Any) -> None:
    get_writer().result(data)


__all__ = [
    "OutputMode",
    "StructuredWriter",
    "configure_writer",
    "get_writer",
    "ndjson_stringify",
    "print_error",
    "print_result",
    "print_text",
]
