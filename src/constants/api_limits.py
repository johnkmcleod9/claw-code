"""
API limits and token budget constants.

Ports: constants/apiLimits.ts, constants/toolLimits.ts
"""
from __future__ import annotations

# Context window sizes by model family (approximate, in tokens)
CONTEXT_WINDOW: dict[str, int] = {
    "claude-3-5-sonnet": 200_000,
    "claude-3-5-haiku": 200_000,
    "claude-3-opus": 200_000,
    "claude-opus-4": 200_000,
    "claude-sonnet-4": 200_000,
    "gpt-4o": 128_000,
    "gpt-4-turbo": 128_000,
    "gpt-4": 8_192,
    "gpt-3.5-turbo": 16_385,
    "gemini-1.5-pro": 2_000_000,
    "gemini-1.5-flash": 1_000_000,
    "gemini-2.0-flash": 1_000_000,
    "default": 200_000,
}

# Maximum output tokens by model family
MAX_OUTPUT_TOKENS: dict[str, int] = {
    "claude-3-5-sonnet": 8_192,
    "claude-3-5-haiku": 8_192,
    "claude-3-opus": 4_096,
    "claude-opus-4": 32_000,
    "claude-sonnet-4": 16_000,
    "gpt-4o": 4_096,
    "gpt-4-turbo": 4_096,
    "default": 4_096,
}

# Compaction thresholds
COMPACTION_THRESHOLD_FRACTION = 0.75   # Compact when 75% of context is used
COMPACTION_KEEP_RECENT = 20            # Keep this many recent messages after compaction

# Tool call limits
MAX_TOOL_CALLS_PER_TURN = 100
MAX_TOOL_OUTPUT_CHARS = 100_000        # Truncate tool outputs beyond this
MAX_TOOL_NAME_LENGTH = 64
MAX_TOOL_PARAM_KEYS = 50

# Request limits
MAX_RETRIES = 3
RETRY_BASE_DELAY_S = 1.0
RETRY_MAX_DELAY_S = 60.0
REQUEST_TIMEOUT_S = 300.0

# Batch / streaming
STREAM_CHUNK_SIZE = 1024               # bytes


def get_context_window(model: str) -> int:
    """Return the context window size for *model*, with fallback."""
    for prefix, size in CONTEXT_WINDOW.items():
        if model.startswith(prefix):
            return size
    return CONTEXT_WINDOW["default"]


def get_max_output_tokens(model: str) -> int:
    for prefix, limit in MAX_OUTPUT_TOKENS.items():
        if model.startswith(prefix):
            return limit
    return MAX_OUTPUT_TOKENS["default"]


__all__ = [
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
]
