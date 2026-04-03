"""
User-facing message strings.

Ports: constants/messages.ts, constants/errorIds.ts,
       constants/cyberRiskInstruction.ts, constants/prompts.ts,
       constants/systemPromptSections.ts
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Error IDs (constants/errorIds.ts)
# ---------------------------------------------------------------------------

class ErrorId:
    CONTEXT_OVERFLOW = "context_overflow"
    RATE_LIMIT = "rate_limit"
    AUTH_FAILED = "auth_failed"
    NETWORK_ERROR = "network_error"
    TOOL_EXEC_FAILED = "tool_exec_failed"
    MAX_TURNS_REACHED = "max_turns_reached"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Common user-facing messages (constants/messages.ts)
# ---------------------------------------------------------------------------

MSG_CONTEXT_OVERFLOW = (
    "The conversation has exceeded the model's context window. "
    "Starting compaction to summarise earlier messages..."
)
MSG_RATE_LIMIT = (
    "Rate limit reached. Waiting {retry_after:.0f}s before retrying..."
)
MSG_AUTH_FAILED = (
    "Authentication failed. Check your API key and try again."
)
MSG_MAX_TURNS = (
    "Reached the maximum number of turns ({max_turns}). "
    "The session will end."
)
MSG_CANCELLED = "Operation cancelled."
MSG_TOOL_DENIED = "Tool use denied by approval policy."
MSG_COMPACTING = "Compacting conversation history..."
MSG_COMPACT_DONE = "Compaction complete. Freed {tokens_freed:,} tokens."
MSG_UPDATE_AVAILABLE = (
    "A new version ({latest}) is available. "
    "Run `pip install --upgrade claw-code` to update."
)

# ---------------------------------------------------------------------------
# System prompt sections (constants/systemPromptSections.ts)
# ---------------------------------------------------------------------------

SYSTEM_SECTION_IDENTITY = "You are {product_name}, an AI assistant."

SYSTEM_SECTION_TOOLS = (
    "You have access to tools that let you interact with the user's computer. "
    "Use them carefully and only when necessary."
)

SYSTEM_SECTION_SAFETY = (
    "Always ask for confirmation before taking destructive actions "
    "(deleting files, sending emails, making purchases, etc.)."
)

SYSTEM_SECTION_WORKDIR = (
    "You are operating in the directory: {workdir}"
)

SYSTEM_SECTION_MEMORY = (
    "You have access to a persistent memory store. "
    "Use it to remember information the user asks you to retain."
)

# ---------------------------------------------------------------------------
# Cyber-risk instruction (constants/cyberRiskInstruction.ts)
# ---------------------------------------------------------------------------

CYBER_RISK_INSTRUCTION = (
    "Do not assist with creating malware, exploits, or tools designed to "
    "attack systems without authorisation. "
    "Do not help bypass security controls or exfiltrate private data."
)

# ---------------------------------------------------------------------------
# Prompt helpers (constants/prompts.ts)
# ---------------------------------------------------------------------------

def format_message(template: str, **kwargs) -> str:
    """Format a message template with keyword arguments."""
    try:
        return template.format(**kwargs)
    except KeyError:
        return template


__all__ = [
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
]
