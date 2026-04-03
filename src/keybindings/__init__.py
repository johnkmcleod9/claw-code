"""
Python keybindings subsystem — ported from 14 archived TypeScript modules.

Provides keybinding parsing, resolution, and matching:

- ``parser``  ParsedKeybinding, Modifier, Key enums, parse_keybinding(), resolver
"""
from __future__ import annotations

from .parser import (
    DEFAULT_BINDINGS,
    Key,
    KeybindingResolver,
    KeybindingSchema,
    Modifier,
    ParsedKeybinding,
    RESERVED,
    ResolvedBinding,
    format_keybinding,
    is_reserved,
    parse_keybinding,
)

import json as _json
from pathlib import Path as _Path

_SNAPSHOT_PATH = _Path(__file__).resolve().parent.parent / "reference_data" / "subsystems" / "keybindings.json"
_SNAPSHOT = _json.loads(_SNAPSHOT_PATH.read_text())

ARCHIVE_NAME = _SNAPSHOT["archive_name"]
MODULE_COUNT = _SNAPSHOT["module_count"]
SAMPLE_FILES = tuple(_SNAPSHOT["sample_files"])
PORTING_NOTE = (
    f"Ported Python package for '{ARCHIVE_NAME}' — "
    f"{MODULE_COUNT} archived TypeScript modules → 1 Python module (core logic)."
)

__all__ = [
    "DEFAULT_BINDINGS",
    "Key",
    "KeybindingResolver",
    "KeybindingSchema",
    "Modifier",
    "ParsedKeybinding",
    "RESERVED",
    "ResolvedBinding",
    "format_keybinding",
    "is_reserved",
    "parse_keybinding",
    "ARCHIVE_NAME",
    "MODULE_COUNT",
    "PORTING_NOTE",
    "SAMPLE_FILES",
]
