"""
Python state subsystem — ported from 6 archived TypeScript modules.

This package provides application state management:

- ``observable``  Observable values, generic Store, selectors, teammate view helpers
- ``app_state``   AppState container, AppStateStore singleton, AppMode/ApprovalMode enums
"""
from __future__ import annotations

from .app_state import AppMode, AppState, AppStateStore, ApprovalMode
from .observable import (
    Observable,
    Store,
    filter_private_keys,
    make_teammate_view,
    merge_state,
    select,
    select_many,
    select_where,
)

# Backward-compat shim
from pathlib import Path as _Path
import json as _json

_SNAPSHOT_PATH = _Path(__file__).resolve().parent.parent / "reference_data" / "subsystems" / "state.json"
_SNAPSHOT = _json.loads(_SNAPSHOT_PATH.read_text())

ARCHIVE_NAME = _SNAPSHOT["archive_name"]
MODULE_COUNT = _SNAPSHOT["module_count"]
SAMPLE_FILES = tuple(_SNAPSHOT["sample_files"])
PORTING_NOTE = (
    f"Ported Python package for '{ARCHIVE_NAME}' — "
    f"{MODULE_COUNT} archived TypeScript modules → 2 Python modules."
)

__all__ = [
    # observable
    "Observable",
    "Store",
    "filter_private_keys",
    "make_teammate_view",
    "merge_state",
    "select",
    "select_many",
    "select_where",
    # app_state
    "AppMode",
    "AppState",
    "AppStateStore",
    "ApprovalMode",
    # legacy archive metadata
    "ARCHIVE_NAME",
    "MODULE_COUNT",
    "PORTING_NOTE",
    "SAMPLE_FILES",
]
