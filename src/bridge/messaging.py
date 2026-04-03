"""
Bridge message protocol.

Ports: bridge/bridgeMessaging.ts, bridge/inboundMessages.ts,
       bridge/inboundAttachments.ts, bridge/bridgePointer.ts,
       bridge/bridgeStatusUtil.ts
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Message types
# ---------------------------------------------------------------------------

class BridgeMsgType(str, Enum):
    # Inbound (IDE → CLI)
    USER_MESSAGE     = "user_message"
    TOOL_RESULT      = "tool_result"
    CANCEL           = "cancel"
    PING             = "ping"
    ATTACHMENT       = "attachment"
    # Outbound (CLI → IDE)
    ASSISTANT_MSG    = "assistant_message"
    TOOL_USE         = "tool_use"
    STATUS           = "status"
    ERROR            = "error"
    PONG             = "pong"
    SESSION_START    = "session_start"
    SESSION_END      = "session_end"
    COMPACTION       = "compaction"


class BridgeStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING   = "connecting"
    CONNECTED    = "connected"
    READY        = "ready"
    ERROR        = "error"


# ---------------------------------------------------------------------------
# Message model
# ---------------------------------------------------------------------------

@dataclass
class BridgeMessage:
    """
    A single message on the bridge wire protocol.

    Ports: bridge/bridgeMessaging.ts message envelope.
    """
    type: BridgeMsgType
    id: str = ""
    session_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps({
            "type": self.type.value,
            "id": self.id,
            "session_id": self.session_id,
            "payload": self.payload,
            "ts": self.timestamp,
        })

    @classmethod
    def from_json(cls, raw: str) -> "BridgeMessage":
        data = json.loads(raw)
        return cls(
            type=BridgeMsgType(data["type"]),
            id=data.get("id", ""),
            session_id=data.get("session_id", ""),
            payload=data.get("payload", {}),
            timestamp=data.get("ts", time.time()),
        )

    @classmethod
    def user_message(cls, text: str, session_id: str = "", msg_id: str = "") -> "BridgeMessage":
        return cls(
            type=BridgeMsgType.USER_MESSAGE,
            id=msg_id,
            session_id=session_id,
            payload={"text": text},
        )

    @classmethod
    def assistant_message(cls, text: str, session_id: str = "", msg_id: str = "") -> "BridgeMessage":
        return cls(
            type=BridgeMsgType.ASSISTANT_MSG,
            id=msg_id,
            session_id=session_id,
            payload={"text": text},
        )

    @classmethod
    def status_message(cls, status: BridgeStatus, detail: str = "") -> "BridgeMessage":
        return cls(
            type=BridgeMsgType.STATUS,
            payload={"status": status.value, "detail": detail},
        )

    @classmethod
    def error_message(cls, error: str, code: str = "") -> "BridgeMessage":
        return cls(
            type=BridgeMsgType.ERROR,
            payload={"error": error, "code": code},
        )


# ---------------------------------------------------------------------------
# Attachment model (bridge/inboundAttachments.ts)
# ---------------------------------------------------------------------------

@dataclass
class BridgeAttachment:
    """A file or image attachment sent from the IDE."""
    attachment_id: str
    name: str
    mime_type: str
    size: int
    data: bytes = field(default=b"", repr=False)
    url: str = ""

    @property
    def is_image(self) -> bool:
        return self.mime_type.startswith("image/")

    @property
    def is_text(self) -> bool:
        return self.mime_type.startswith("text/")

    def decode_text(self, encoding: str = "utf-8") -> str:
        return self.data.decode(encoding, errors="replace")


# ---------------------------------------------------------------------------
# Pointer / cursor context (bridge/bridgePointer.ts)
# ---------------------------------------------------------------------------

@dataclass
class EditorPointer:
    """The current cursor/selection context from the IDE."""
    file_path: str = ""
    line: int = 0
    column: int = 0
    selected_text: str = ""
    language_id: str = ""

    def to_context_string(self) -> str:
        parts = []
        if self.file_path:
            parts.append(f"File: {self.file_path}")
            if self.line:
                parts.append(f"Line: {self.line}")
        if self.selected_text:
            parts.append(f"Selected:\n```{self.language_id}\n{self.selected_text}\n```")
        return "\n".join(parts) if parts else ""


# ---------------------------------------------------------------------------
# Status utilities (bridge/bridgeStatusUtil.ts)
# ---------------------------------------------------------------------------

def format_status(status: BridgeStatus, detail: str = "") -> str:
    icons = {
        BridgeStatus.DISCONNECTED: "○",
        BridgeStatus.CONNECTING:   "◔",
        BridgeStatus.CONNECTED:    "●",
        BridgeStatus.READY:        "✓",
        BridgeStatus.ERROR:        "✗",
    }
    icon = icons.get(status, "?")
    label = f"{icon} Bridge {status.value}"
    return f"{label}: {detail}" if detail else label


__all__ = [
    "BridgeAttachment",
    "BridgeMessage",
    "BridgeMsgType",
    "BridgeStatus",
    "EditorPointer",
    "format_status",
]
