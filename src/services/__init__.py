"""
Python services subsystem — ported from 130 archived TypeScript modules.

This package provides core application services:

- ``session_memory``    Persistent key-value memory across sessions
- ``api_client``        HTTP API client with retry, auth, and usage tracking
- ``prompt_suggestion`` Contextual follow-up prompt suggestions
- ``agent_summary``     Compact session and turn summaries
- ``analytics``         Event telemetry (privacy-preserving, opt-out)
- ``error_handler``     Structured error classification and reporting
- ``compaction``        Context window compaction service
- ``magic_docs``        Document ingestion, chunking, and Q&A helpers
- ``oauth``             OAuth 2.0 / PKCE token management
"""
from __future__ import annotations

from .agent_summary import AgentSessionSummary, AgentTurnSummary, summarize_session
from .analytics import (
    Analytics,
    AnalyticsEvent,
    FileSink,
    MemorySink,
    NullSink,
    analytics_enabled,
    configure_analytics,
    get_analytics,
)
from .api_client import (
    ApiClient,
    ApiError,
    AuthError,
    ClientConfig,
    RateLimitError,
    ServerError,
    UsageStats,
    raise_for_status,
)
from .compaction import (
    CompactionResult,
    CompactionService,
    CompactionStrategy,
    Message as CompactionMessage,
    ThresholdCompactionStrategy,
)
from .error_handler import (
    AuthenticationError,
    CancelledError,
    ClawError,
    ContextOverflowError,
    ErrorCategory,
    ErrorReporter,
    ErrorSeverity,
    NetworkError,
    classify_exception,
    get_reporter,
    is_retryable,
    report_error,
)
from .magic_docs import (
    DocChunk,
    MagicDoc,
    MagicDocStore,
    build_qa_prompt,
    build_summarise_prompt,
    chunk_text,
    ingest_file,
    ingest_text,
)
from .oauth import (
    OAuthProvider,
    OAuthToken,
    TokenStore,
    build_auth_url,
    generate_code_challenge,
    generate_code_verifier,
    parse_redirect,
)
from .prompt_suggestion import (
    PromptSuggestion,
    SpeculationResult,
    speculate,
    suggest_from_context,
)
from .session_memory import MemoryEntry, SessionMemory, make_memory

# Backward-compat shim
from pathlib import Path as _Path
import json as _json

_SNAPSHOT_PATH = _Path(__file__).resolve().parent.parent / "reference_data" / "subsystems" / "services.json"
_SNAPSHOT = _json.loads(_SNAPSHOT_PATH.read_text())

ARCHIVE_NAME = _SNAPSHOT["archive_name"]
MODULE_COUNT = _SNAPSHOT["module_count"]
SAMPLE_FILES = tuple(_SNAPSHOT["sample_files"])
PORTING_NOTE = (
    f"Ported Python package for '{ARCHIVE_NAME}' — "
    f"{MODULE_COUNT} archived TypeScript modules → 9 Python service modules."
)

__all__ = [
    # session_memory
    "MemoryEntry",
    "SessionMemory",
    "make_memory",
    # api_client
    "ApiClient",
    "ApiError",
    "AuthError",
    "ClientConfig",
    "RateLimitError",
    "ServerError",
    "UsageStats",
    "raise_for_status",
    # prompt_suggestion
    "PromptSuggestion",
    "SpeculationResult",
    "speculate",
    "suggest_from_context",
    # agent_summary
    "AgentSessionSummary",
    "AgentTurnSummary",
    "summarize_session",
    # analytics
    "Analytics",
    "AnalyticsEvent",
    "FileSink",
    "MemorySink",
    "NullSink",
    "analytics_enabled",
    "configure_analytics",
    "get_analytics",
    # error_handler
    "AuthenticationError",
    "CancelledError",
    "ClawError",
    "ContextOverflowError",
    "ErrorCategory",
    "ErrorReporter",
    "ErrorSeverity",
    "NetworkError",
    "classify_exception",
    "get_reporter",
    "is_retryable",
    "report_error",
    # compaction
    "CompactionMessage",
    "CompactionResult",
    "CompactionService",
    "CompactionStrategy",
    "ThresholdCompactionStrategy",
    # magic_docs
    "DocChunk",
    "MagicDoc",
    "MagicDocStore",
    "build_qa_prompt",
    "build_summarise_prompt",
    "chunk_text",
    "ingest_file",
    "ingest_text",
    # oauth
    "OAuthProvider",
    "OAuthToken",
    "TokenStore",
    "build_auth_url",
    "generate_code_challenge",
    "generate_code_verifier",
    "parse_redirect",
    # legacy archive metadata
    "ARCHIVE_NAME",
    "MODULE_COUNT",
    "PORTING_NOTE",
    "SAMPLE_FILES",
]
