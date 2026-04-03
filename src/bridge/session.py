"""
Bridge session management.

Ports: bridge/createSession.ts, bridge/codeSessionApi.ts,
       bridge/replBridge.ts, bridge/replBridgeHandle.ts,
       bridge/bridgeApi.ts
"""
from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Session model
# ---------------------------------------------------------------------------

@dataclass
class BridgeSession:
    """
    Represents a single bridge connection session.

    Ports: bridge/createSession.ts, bridge/codeSessionApi.ts
    """
    session_id: str
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    endpoint: str = ""
    client_info: dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.last_activity = time.time()

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at

    @property
    def idle_seconds(self) -> float:
        return time.time() - self.last_activity

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "endpoint": self.endpoint,
            "client_info": self.client_info,
            "is_active": self.is_active,
            "metadata": self.metadata,
        }


def create_session(endpoint: str = "", client_info: dict[str, Any] | None = None) -> BridgeSession:
    """Factory: create a new bridge session with a random ID."""
    return BridgeSession(
        session_id=secrets.token_urlsafe(12),
        endpoint=endpoint,
        client_info=client_info or {},
    )


# ---------------------------------------------------------------------------
# Session store
# ---------------------------------------------------------------------------

class BridgeSessionStore:
    """
    In-memory registry of active bridge sessions.

    Ports: bridge/replBridgeHandle.ts (session handle registry)
    """

    def __init__(self) -> None:
        self._sessions: dict[str, BridgeSession] = {}

    def add(self, session: BridgeSession) -> None:
        self._sessions[session.session_id] = session

    def get(self, session_id: str) -> BridgeSession | None:
        session = self._sessions.get(session_id)
        if session:
            session.touch()
        return session

    def remove(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

    def list_active(self) -> list[BridgeSession]:
        self._prune()
        return [s for s in self._sessions.values() if s.is_active]

    def _prune(self, idle_timeout: float = 300.0) -> None:
        """Remove sessions idle longer than *idle_timeout*."""
        now = time.time()
        stale = [
            sid for sid, s in self._sessions.items()
            if now - s.last_activity > idle_timeout
        ]
        for sid in stale:
            self._sessions.pop(sid, None)

    def clear(self) -> None:
        self._sessions.clear()


# ---------------------------------------------------------------------------
# API surface (bridge/bridgeApi.ts)
# ---------------------------------------------------------------------------

MessageHandler = Callable[["BridgeSession", Any], None]


class BridgeAPI:
    """
    High-level bridge API for the CLI to send/receive messages.

    Ports: bridge/bridgeApi.ts
    """

    def __init__(self, config, transport) -> None:
        self._config = config
        self._transport = transport
        self._sessions = BridgeSessionStore()
        self._handlers: dict[str, list[MessageHandler]] = {}

    def create_session(self) -> BridgeSession:
        session = create_session(endpoint=self._config.base_url)
        self._sessions.add(session)
        return session

    def send(self, session: BridgeSession, msg: Any) -> None:
        """Send a message over the transport."""
        self._transport.send(msg)

    def register_handler(self, msg_type: str, handler: MessageHandler) -> None:
        self._handlers.setdefault(msg_type, []).append(handler)

    def handle_inbound(self, session: BridgeSession, msg: Any) -> None:
        msg_type = getattr(msg, "type", str(type(msg).__name__))
        for handler in self._handlers.get(msg_type, []):
            try:
                handler(session, msg)
            except Exception:
                pass


__all__ = [
    "BridgeAPI",
    "BridgeSession",
    "BridgeSessionStore",
    "create_session",
]
