"""
Bridge debug utilities — structured logging, hexdump, and message tracing.

Ports: bridge/bridgeDebug.ts, bridge/debugUtils.ts
"""
from __future__ import annotations

import datetime
import logging
import os
import sys
from enum import Enum
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Log levels
# ---------------------------------------------------------------------------

class BridgeLogLevel(str, Enum):
    DEBUG = "debug"
    INFO  = "info"
    WARN  = "warn"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Bridge logger
# ---------------------------------------------------------------------------

class BridgeLogger:
    """
    Structured logger for bridge operations.

    Outputs to stderr by default; can be redirected to a file.
    """

    def __init__(
        self,
        name: str = "claw.bridge",
        level: BridgeLogLevel = BridgeLogLevel.INFO,
        output_path: Path | None = None,
    ) -> None:
        self.name = name
        self.level = level
        self._file = None
        if output_path:
            self._file = open(output_path, "a", encoding="utf-8")

    def _should_log(self, level: BridgeLogLevel) -> bool:
        order = [BridgeLogLevel.DEBUG, BridgeLogLevel.INFO,
                 BridgeLogLevel.WARN, BridgeLogLevel.ERROR]
        return order.index(level) >= order.index(self.level)

    def _format(
        self,
        level: BridgeLogLevel,
        msg: str,
        extra: dict[str, Any] | None = None,
    ) -> str:
        ts = datetime.datetime.now().isoformat(timespec="milliseconds")
        base = f"[{ts}] {level.value.upper():5s} [{self.name}] {msg}"
        if extra:
            import json
            base += " " + json.dumps(extra)
        return base

    def debug(self, msg: str, **kwargs: Any) -> None:
        if self._should_log(BridgeLogLevel.DEBUG):
            out = self._format(BridgeLogLevel.DEBUG, msg, kwargs or None)
            self._emit(out)

    def info(self, msg: str, **kwargs: Any) -> None:
        if self._should_log(BridgeLogLevel.INFO):
            out = self._format(BridgeLogLevel.INFO, msg, kwargs or None)
            self._emit(out)

    def warn(self, msg: str, **kwargs: Any) -> None:
        if self._should_log(BridgeLogLevel.WARN):
            out = self._format(BridgeLogLevel.WARN, msg, kwargs or None)
            self._emit(sys.stderr)

    def error(self, msg: str, **kwargs: Any) -> None:
        if self._should_log(BridgeLogLevel.ERROR):
            out = self._format(BridgeLogLevel.ERROR, msg, kwargs or None)
            self._emit(sys.stderr)

    def _emit(self, line: str, file: Any = None) -> None:
        dest = file or sys.stderr
        print(line, file=dest)
        if self._file:
            print(line, file=self._file)
            self._file.flush()

    def close(self) -> None:
        if self._file:
            self._file.close()
            self._file = None


# Global default logger (lazy)
_logger: BridgeLogger | None = None


def get_bridge_logger(
    level: BridgeLogLevel | None = None,
) -> BridgeLogger:
    """Get (or create) the global bridge logger."""
    global _logger
    if _logger is None:
        debug_env = os.environ.get("CLAW_BRIDGE_DEBUG", "").lower()
        if level is None:
            if debug_env in ("1", "true", "debug"):
                level = BridgeLogLevel.DEBUG
            else:
                level = BridgeLogLevel.INFO
        log_path_str = os.environ.get("CLAW_BRIDGE_LOG_PATH", "")
        log_path = Path(log_path_str) if log_path_str else None
        _logger = BridgeLogger(level=level, output_path=log_path)
    return _logger


def bridge_log(
    msg: str,
    level: BridgeLogLevel = BridgeLogLevel.INFO,
    **kwargs: Any,
) -> None:
    """Quick log helper: bridge_log('hello', level=WARN)."""
    get_bridge_logger().info(msg, **kwargs) if level == BridgeLogLevel.INFO else (
        get_bridge_logger().warn(msg, **kwargs) if level == BridgeLogLevel.WARN else (
            get_bridge_logger().error(msg, **kwargs)
        )
    )


def log_bridge_message(
    direction: str,   # "→" for outbound, "←" for inbound
    msg_type: str,
    payload_size: int | None = None,
    **extra: Any,
) -> None:
    """Log a bridge message in compact form."""
    logger = get_bridge_logger()
    info: dict[str, Any] = {"type": msg_type, **extra}
    if payload_size is not None:
        info["size"] = payload_size
    logger.debug(f"BRIDGE {direction} {msg_type}", **info)


def log_bridge_error(
    context: str,
    error: Exception | str,
    **extra: Any,
) -> None:
    """Log a bridge error with context."""
    err_str = str(error) if isinstance(error, Exception) else error
    get_bridge_logger().error(f"BRIDGE ERROR [{context}]: {err_str}", **extra)


# ---------------------------------------------------------------------------
# Hexdump
# ---------------------------------------------------------------------------

def hexdump(
    data: bytes | bytearray,
    offset: int = 0,
    length: int | None = None,
    width: int = 16,
) -> str:
    """
    Produce a classic hexdump-style output for binary data.

    Args:
        data:    Bytes to dump.
        offset:  Starting offset (shown in left column).
        length:  Max bytes to dump (None = all).
        width:   Bytes per line (default 16).

    Returns:
        Multiline hexdump string.
    """
    if isinstance(data, bytes):
        data = bytearray(data)
    if length:
        data = data[offset:offset + length]

    lines: list[str] = []
    for i in range(0, len(data), width):
        chunk = data[i:i + width]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        hex_part = hex_part.ljust(width * 3 - 1)

        ascii_part = "".join(
            chr(b) if 32 <= b < 127 else "."
            for b in chunk
        )
        addr = f"{offset + i:08x}"
        lines.append(f"{addr}  {hex_part}  |{ascii_part}|")

    return "\n".join(lines)
