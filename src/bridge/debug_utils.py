"""
Bridge debugging utilities.

Ports: bridge/bridgeDebug.ts, bridge/debugUtils.ts
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import sys
from typing import Any


# ---------------------------------------------------------------------------
# Logger setup
# ---------------------------------------------------------------------------

_BRIDGE_LOGGER = "claw.bridge"


class BridgeDebugFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.datetime.now().isoformat(timespec="millis")
        return f"[{ts}] [{record.levelname}] bridge: {record.getMessage()}"


def get_bridge_logger() -> logging.Logger:
    logger = logging.getLogger(_BRIDGE_LOGGER)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(BridgeDebugFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG if _bridge_debug_enabled() else logging.WARNING)
    return logger


def _bridge_debug_enabled() -> bool:
    return os.environ.get("CLAW_BRIDGE_DEBUG", "").lower() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# Debug helpers
# ---------------------------------------------------------------------------

def bridge_log(level: str, msg: str, **kwargs: Any) -> None:
    logger = get_bridge_logger()
    getattr(logger, level.lower(), logger.info)(msg, extra=kwargs)


def log_bridge_message(direction: str, msg: Any) -> None:
    """
    Log a bridge message at DEBUG level.

    *direction* is "→" (inbound) or "←" (outbound).
    """
    if not _bridge_debug_enabled():
        return
    try:
        serialized = json.dumps(msg, default=str, indent=2)[:500]
    except Exception:
        serialized = repr(msg)
    bridge_log("debug", f"bridge {direction} {serialized}")


def log_bridge_error(msg: str, exc: Exception | None = None) -> None:
    extra = {}
    if exc:
        extra["exc"] = repr(exc)
    bridge_log("error", msg, **extra)


# ---------------------------------------------------------------------------
# Hex dump utility (bridge/debugUtils.ts hexdump)
# ---------------------------------------------------------------------------

def hexdump(data: bytes, offset: int = 0, limit: int = 256) -> str:
    """
    Produce an annotated hex dump of *data* (like ``xxd``).

    Useful for debugging binary protocol messages.
    """
    lines: list[str] = []
    for i in range(0, min(len(data), limit), 16):
        chunk = data[i : i + 16]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(
            chr(b) if 32 <= b < 127 else "."
            for b in chunk
        )
        lines.append(f"{offset + i:08x}  {hex_part:<48}  {ascii_part}")
    if len(data) > limit:
        lines.append(f"... ({len(data) - limit} bytes omitted)")
    return "\n".join(lines)


__all__ = [
    "bridge_log",
    "get_bridge_logger",
    "hexdump",
    "log_bridge_error",
    "log_bridge_message",
]
