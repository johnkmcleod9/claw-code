"""
Python constants subsystem — ported from 21 archived TypeScript modules.

This package provides application-wide constants:

- ``api_limits``      Context window sizes, token limits, retry config
- ``common``          Product info, file names, key names, UI figures, XML tags
- ``messages``        User-facing message strings, error IDs, system prompt sections
- ``output_styles``   ANSI colour helpers, terminal width, semantic formatters
"""
from __future__ import annotations

from .api_limits import (
    COMPACTION_KEEP_RECENT,
    COMPACTION_THRESHOLD_FRACTION,
    CONTEXT_WINDOW,
    MAX_OUTPUT_TOKENS,
    MAX_RETRIES,
    MAX_TOOL_CALLS_PER_TURN,
    MAX_TOOL_NAME_LENGTH,
    MAX_TOOL_OUTPUT_CHARS,
    MAX_TOOL_PARAM_KEYS,
    REQUEST_TIMEOUT_S,
    RETRY_BASE_DELAY_S,
    RETRY_MAX_DELAY_S,
    STREAM_CHUNK_SIZE,
    get_context_window,
    get_max_output_tokens,
)
from .common import (
    CONFIG_DIR_NAME,
    CONFIG_FILE_NAME,
    DOCS_URL,
    FIGURE_ARROW,
    FIGURE_BULLET,
    FIGURE_CROSS,
    FIGURE_ELLIPSIS,
    FIGURE_INFO,
    FIGURE_TICK,
    FIGURE_WARNING,
    GITIGNORE_FILE,
    GITHUB_URL,
    KEY_CTRL_C,
    KEY_CTRL_D,
    KEY_CTRL_Z,
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_TAB,
    KEY_UP,
    MEMORY_DIR_NAME,
    PLUGINS_DIR_NAME,
    PRODUCT_NAME,
    PRODUCT_SHORT,
    PRODUCT_VERSION,
    SESSION_FILE,
    SKILLS_DIR_NAME,
    SPINNER_VERBS,
    TRANSCRIPT_FILE,
    TURN_COMPLETION_VERBS,
    XML_DOCUMENT,
    XML_RESULT,
    XML_SEARCH_RESULTS,
    XML_THINKING,
    XML_TOOL_RESULT,
    XML_TOOL_USE,
)
from .messages import (
    CYBER_RISK_INSTRUCTION,
    MSG_AUTH_FAILED,
    MSG_CANCELLED,
    MSG_COMPACT_DONE,
    MSG_COMPACTING,
    MSG_CONTEXT_OVERFLOW,
    MSG_MAX_TURNS,
    MSG_RATE_LIMIT,
    MSG_TOOL_DENIED,
    MSG_UPDATE_AVAILABLE,
    SYSTEM_SECTION_IDENTITY,
    SYSTEM_SECTION_MEMORY,
    SYSTEM_SECTION_SAFETY,
    SYSTEM_SECTION_TOOLS,
    SYSTEM_SECTION_WORKDIR,
    ErrorId,
    format_message,
)
from .output_styles import (
    COLOUR_ENABLED,
    assistant_label,
    bold,
    code_text,
    dim,
    error,
    hr,
    info,
    muted,
    success,
    terminal_width,
    user_label,
    warning,
)

import json as _json
from pathlib import Path as _Path

_SNAPSHOT_PATH = _Path(__file__).resolve().parent.parent / "reference_data" / "subsystems" / "constants.json"
_SNAPSHOT = _json.loads(_SNAPSHOT_PATH.read_text())

ARCHIVE_NAME = _SNAPSHOT["archive_name"]
MODULE_COUNT = _SNAPSHOT["module_count"]
SAMPLE_FILES = tuple(_SNAPSHOT["sample_files"])
PORTING_NOTE = (
    f"Ported Python package for '{ARCHIVE_NAME}' — "
    f"{MODULE_COUNT} archived TypeScript modules → 4 Python constant modules."
)

__all__ = [
    # api_limits
    "COMPACTION_KEEP_RECENT",
    "COMPACTION_THRESHOLD_FRACTION",
    "CONTEXT_WINDOW",
    "MAX_OUTPUT_TOKENS",
    "MAX_RETRIES",
    "MAX_TOOL_CALLS_PER_TURN",
    "MAX_TOOL_NAME_LENGTH",
    "MAX_TOOL_OUTPUT_CHARS",
    "MAX_TOOL_PARAM_KEYS",
    "REQUEST_TIMEOUT_S",
    "RETRY_BASE_DELAY_S",
    "RETRY_MAX_DELAY_S",
    "STREAM_CHUNK_SIZE",
    "get_context_window",
    "get_max_output_tokens",
    # common
    "CONFIG_DIR_NAME",
    "CONFIG_FILE_NAME",
    "DOCS_URL",
    "FIGURE_ARROW",
    "FIGURE_BULLET",
    "FIGURE_CROSS",
    "FIGURE_ELLIPSIS",
    "FIGURE_INFO",
    "FIGURE_TICK",
    "FIGURE_WARNING",
    "GITIGNORE_FILE",
    "GITHUB_URL",
    "KEY_CTRL_C",
    "KEY_CTRL_D",
    "KEY_CTRL_Z",
    "KEY_DOWN",
    "KEY_ENTER",
    "KEY_ESCAPE",
    "KEY_TAB",
    "KEY_UP",
    "MEMORY_DIR_NAME",
    "PLUGINS_DIR_NAME",
    "PRODUCT_NAME",
    "PRODUCT_SHORT",
    "PRODUCT_VERSION",
    "SESSION_FILE",
    "SKILLS_DIR_NAME",
    "SPINNER_VERBS",
    "TRANSCRIPT_FILE",
    "TURN_COMPLETION_VERBS",
    "XML_DOCUMENT",
    "XML_RESULT",
    "XML_SEARCH_RESULTS",
    "XML_THINKING",
    "XML_TOOL_RESULT",
    "XML_TOOL_USE",
    # messages
    "CYBER_RISK_INSTRUCTION",
    "ErrorId",
    "MSG_AUTH_FAILED",
    "MSG_CANCELLED",
    "MSG_COMPACT_DONE",
    "MSG_COMPACTING",
    "MSG_CONTEXT_OVERFLOW",
    "MSG_MAX_TURNS",
    "MSG_RATE_LIMIT",
    "MSG_TOOL_DENIED",
    "MSG_UPDATE_AVAILABLE",
    "SYSTEM_SECTION_IDENTITY",
    "SYSTEM_SECTION_MEMORY",
    "SYSTEM_SECTION_SAFETY",
    "SYSTEM_SECTION_TOOLS",
    "SYSTEM_SECTION_WORKDIR",
    "format_message",
    # output_styles
    "COLOUR_ENABLED",
    "assistant_label",
    "bold",
    "code_text",
    "dim",
    "error",
    "hr",
    "info",
    "muted",
    "success",
    "terminal_width",
    "user_label",
    "warning",
    # archive metadata
    "ARCHIVE_NAME",
    "MODULE_COUNT",
    "PORTING_NOTE",
    "SAMPLE_FILES",
]
