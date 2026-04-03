"""
Python CLI subsystem — ported from 19 archived TypeScript modules.

This package provides the CLI command layer:

- ``print``       Structured output, NDJSON serialisation, StructuredWriter
- ``handlers``    Command handler functions (auth, auto-mode, MCP, plugins, util, agents)
- ``transports``  Event transport layer (SSE, batch upload, hybrid fan-out)
- ``update``      Version checking and self-update
"""
from __future__ import annotations

from .handlers import (
    HandlerResult,
    MCPServerEntry,
    handle_agents_list,
    handle_auth_login,
    handle_auth_logout,
    handle_auth_status,
    handle_auto_mode,
    handle_doctor,
    handle_mcp_add,
    handle_mcp_list,
    handle_plugins_list,
    handle_version,
)
from .print import (
    OutputMode,
    StructuredWriter,
    configure_writer,
    get_writer,
    ndjson_stringify,
    print_error,
    print_result,
    print_text,
)
from .transports import (
    BaseTransport,
    HybridTransport,
    InMemoryTransport,
    SSETransport,
    SerialBatchUploader,
    TransportEvent,
    pick_transport,
)
from .update import (
    VersionInfo,
    check_for_update,
    get_current_version,
    perform_update,
)

import json as _json
from pathlib import Path as _Path

_SNAPSHOT_PATH = _Path(__file__).resolve().parent.parent / "reference_data" / "subsystems" / "cli.json"
_SNAPSHOT = _json.loads(_SNAPSHOT_PATH.read_text())

ARCHIVE_NAME = _SNAPSHOT["archive_name"]
MODULE_COUNT = _SNAPSHOT["module_count"]
SAMPLE_FILES = tuple(_SNAPSHOT["sample_files"])
PORTING_NOTE = (
    f"Ported Python package for '{ARCHIVE_NAME}' — "
    f"{MODULE_COUNT} archived TypeScript modules → 4 Python CLI modules."
)

__all__ = [
    # handlers
    "HandlerResult",
    "MCPServerEntry",
    "handle_agents_list",
    "handle_auth_login",
    "handle_auth_logout",
    "handle_auth_status",
    "handle_auto_mode",
    "handle_doctor",
    "handle_mcp_add",
    "handle_mcp_list",
    "handle_plugins_list",
    "handle_version",
    # print
    "OutputMode",
    "StructuredWriter",
    "configure_writer",
    "get_writer",
    "ndjson_stringify",
    "print_error",
    "print_result",
    "print_text",
    # transports
    "BaseTransport",
    "HybridTransport",
    "InMemoryTransport",
    "SSETransport",
    "SerialBatchUploader",
    "TransportEvent",
    "pick_transport",
    # update
    "VersionInfo",
    "check_for_update",
    "get_current_version",
    "perform_update",
    # archive metadata
    "ARCHIVE_NAME",
    "MODULE_COUNT",
    "PORTING_NOTE",
    "SAMPLE_FILES",
]
