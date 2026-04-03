"""
ID and session identifier utilities.

Ports: utils/agentId.ts, utils/agentContext.ts
"""
from __future__ import annotations

import hashlib
import os
import time
import uuid


def new_session_id() -> str:
    """Generate a new unique session ID (UUID4)."""
    return str(uuid.uuid4())


def new_short_id(prefix: str = "") -> str:
    """
    Generate a short random ID (8 hex chars), optionally prefixed.

    Example: ``new_short_id("tool")`` → ``"tool-a3f7c9b2"``
    """
    short = uuid.uuid4().hex[:8]
    return f"{prefix}-{short}" if prefix else short


def deterministic_id(*parts: str) -> str:
    """
    Generate a stable ID by hashing the concatenated *parts*.

    Useful for deduplication and caching.
    """
    payload = "|".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def timestamp_id() -> str:
    """
    Generate a time-ordered ID: ``{unix_ms}-{random_hex}``.

    Lexicographically sortable by creation time.
    """
    ts = int(time.time() * 1000)
    rand = uuid.uuid4().hex[:8]
    return f"{ts:016x}-{rand}"


def agent_id(name: str = "") -> str:
    """
    Generate an agent instance ID, optionally incorporating *name*.

    Format: ``{name}-{short_uuid}`` or just ``{short_uuid}``.
    """
    short = uuid.uuid4().hex[:12]
    slug = name.lower().replace(" ", "-") if name else ""
    return f"{slug}-{short}" if slug else short


def pid_token() -> str:
    """Return a token combining the current PID and a random component."""
    return f"{os.getpid()}-{uuid.uuid4().hex[:8]}"


__all__ = [
    "new_session_id",
    "new_short_id",
    "deterministic_id",
    "timestamp_id",
    "agent_id",
    "pid_token",
]
