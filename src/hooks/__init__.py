"""
Python hooks subsystem — ported from 104 archived TypeScript modules.

Provides Python equivalents of React hooks patterns:
state management, lifecycle, events, permissions, notifications, suggestions.

Modules:
- ``state_hooks``          Signal, Derived, Ref, Store, PersistedSignal, EventEmitter
- ``lifecycle_hooks``      Debounce, throttle, interval, timeout, lifecycle, prev-value
- ``event_hooks``          Clipboard, signal handling, IsMounted, async effects, placeholders
- ``tool_permission_hooks`` Permission context, interactive/coordinator/swarm handlers
- ``notification_hooks``   Notification manager + typed notification helpers
- ``suggestion_hooks``     File suggestions, unified autocomplete, reactive suggestion state
"""
from __future__ import annotations

import json
from pathlib import Path

# ── Metadata from archived TS snapshot ──────────────────────────────────────
_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent.parent
    / "reference_data" / "subsystems" / "hooks.json"
)
_SNAPSHOT = json.loads(_SNAPSHOT_PATH.read_text())
ARCHIVE_NAME = _SNAPSHOT["archive_name"]
MODULE_COUNT  = _SNAPSHOT["module_count"]
SAMPLE_FILES  = tuple(_SNAPSHOT["sample_files"])
PORTING_NOTE  = (
    f"Ported Python package for '{ARCHIVE_NAME}' — "
    f"{MODULE_COUNT} archived TypeScript modules → 5 Python modules."
)

# ── State management ─────────────────────────────────────────────────────────
from .state_hooks import (
    Signal, Derived, Ref, Store, PersistedSignal, EventEmitter,
    Action, Reducer,
)

# ── Lifecycle ─────────────────────────────────────────────────────────────────
from .lifecycle_hooks import (
    Debouncer, debounce,
    Throttler, throttle,
    Interval, interval,
    Timeout,
    PreviousTracker,
    LifecycleManager,
    AfterInit,
)

# ── Event hooks ───────────────────────────────────────────────────────────────
from .event_hooks import (
    Clipboard,
    SignalHandler,
    on_interrupt,
    on_terminate,
    IsMounted,
    safe_callback,
    LatestRef,
    AsyncEffect,
    Placeholder,
)

# ── Tool permissions ──────────────────────────────────────────────────────────
from .tool_permission_hooks import (
    PermissionLevel,
    PermissionDecision,
    ToolPermissionRequest,
    PermissionContext,
    InteractivePermissionHandler,
    CoordinatorPermissionHandler,
    SwarmWorkerPermissionHandler,
    get_permission_context,
)

# ── Notifications ─────────────────────────────────────────────────────────────
from .notification_hooks import (
    NotificationLevel,
    Notification,
    NotificationManager,
    notify_startup,
    notify_rate_limit,
    notify_model_migration,
    notify_mcp_connectivity,
    notify_settings_error,
    notify_plugin_update,
    get_notifications,
)

# ── Suggestions ───────────────────────────────────────────────────────────────
from .suggestion_hooks import (
    get_file_suggestions,
    SuggestionType,
    Suggestion,
    UnifiedSuggestionEngine,
    SuggestionState,
)

__all__ = [
    # metadata
    "ARCHIVE_NAME", "MODULE_COUNT", "SAMPLE_FILES", "PORTING_NOTE",
    # state
    "Signal", "Derived", "Ref", "Store", "PersistedSignal", "EventEmitter",
    "Action", "Reducer",
    # lifecycle
    "Debouncer", "debounce", "Throttler", "throttle",
    "Interval", "interval", "Timeout",
    "PreviousTracker", "LifecycleManager", "AfterInit",
    # events
    "Clipboard", "SignalHandler", "on_interrupt", "on_terminate",
    "IsMounted", "safe_callback", "LatestRef", "AsyncEffect", "Placeholder",
    # permissions
    "PermissionLevel", "PermissionDecision", "ToolPermissionRequest",
    "PermissionContext",
    "InteractivePermissionHandler", "CoordinatorPermissionHandler",
    "SwarmWorkerPermissionHandler", "get_permission_context",
    # notifications
    "NotificationLevel", "Notification", "NotificationManager",
    "notify_startup", "notify_rate_limit", "notify_model_migration",
    "notify_mcp_connectivity", "notify_settings_error", "notify_plugin_update",
    "get_notifications",
    # suggestions
    "get_file_suggestions", "SuggestionType", "Suggestion",
    "UnifiedSuggestionEngine", "SuggestionState",
]
