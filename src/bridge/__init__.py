"""
Python bridge subsystem — ported from 31 archived TypeScript modules.

This package provides the IDE bridge layer:

- ``config``       BridgeConfig, poll defaults, env var loader, enabled flag
- ``messaging``    BridgeMessage, BridgeMsgType, BridgeStatus, EditorPointer
- ``session``      BridgeSession, BridgeSessionStore, BridgeAPI
- ``jwt_utils``    JWT payload decode/encode (HS256), JWTPayload
- ``debug_utils``  BridgeLogger, hexdump, message tracing
"""
from __future__ import annotations

from .config import (
    DEFAULT_MAX_RECONNECT_ATTEMPTS,
    DEFAULT_POLL_INTERVAL_MS,
    DEFAULT_POLL_TIMEOUT_MS,
    DEFAULT_RECONNECT_DELAY_MS,
    BridgeConfig,
    is_bridge_enabled,
    load_bridge_config_from_env,
)
from .debug_utils import (
    bridge_log,
    get_bridge_logger,
    hexdump,
    log_bridge_error,
    log_bridge_message,
)
from .jwt_utils import (
    JWTPayload,
    decode_jwt_payload,
    encode_jwt_payload,
)
from .messaging import (
    BridgeAttachment,
    BridgeMessage,
    BridgeMsgType,
    BridgeStatus,
    EditorPointer,
    format_status,
)
from .session import (
    BridgeAPI,
    BridgeSession,
    BridgeSessionStore,
    create_session,
)

import json as _json
from pathlib import Path as _Path

_SNAPSHOT_PATH = _Path(__file__).resolve().parent.parent / "reference_data" / "subsystems" / "bridge.json"
_SNAPSHOT = _json.loads(_SNAPSHOT_PATH.read_text())

ARCHIVE_NAME = _SNAPSHOT["archive_name"]
MODULE_COUNT = _SNAPSHOT["module_count"]
SAMPLE_FILES = tuple(_SNAPSHOT["sample_files"])
PORTING_NOTE = (
    f"Ported Python package for '{ARCHIVE_NAME}' — "
    f"{MODULE_COUNT} archived TypeScript modules → 5 Python bridge modules."
)

__all__ = [
    # config
    "BridgeConfig",
    "DEFAULT_MAX_RECONNECT_ATTEMPTS",
    "DEFAULT_POLL_INTERVAL_MS",
    "DEFAULT_POLL_TIMEOUT_MS",
    "DEFAULT_RECONNECT_DELAY_MS",
    "is_bridge_enabled",
    "load_bridge_config_from_env",
    # debug
    "bridge_log",
    "get_bridge_logger",
    "hexdump",
    "log_bridge_error",
    "log_bridge_message",
    # jwt
    "JWTPayload",
    "decode_jwt_payload",
    "encode_jwt_payload",
    # messaging
    "BridgeAttachment",
    "BridgeMessage",
    "BridgeMsgType",
    "BridgeStatus",
    "EditorPointer",
    "format_status",
    # session
    "BridgeAPI",
    "BridgeSession",
    "BridgeSessionStore",
    "create_session",
    # archive metadata
    "ARCHIVE_NAME",
    "MODULE_COUNT",
    "PORTING_NOTE",
    "SAMPLE_FILES",
]
