"""
Python screens subsystem — ported from 3 archived TypeScript modules.

Provides screen state representations:

- ``screen``  Screen, DoctorScreen, REPLScreen, ResumeScreen, ScreenType enum
"""
from __future__ import annotations

from .screen import (
    DoctorScreen,
    REPLScreen,
    ResumeScreen,
    Screen,
    ScreenType,
    make_screen,
)

import json as _json
from pathlib import Path as _Path

_SNAPSHOT_PATH = _Path(__file__).resolve().parent.parent / "reference_data" / "subsystems" / "screens.json"
_SNAPSHOT = _json.loads(_SNAPSHOT_PATH.read_text())

ARCHIVE_NAME = _SNAPSHOT["archive_name"]
MODULE_COUNT = _SNAPSHOT["module_count"]
SAMPLE_FILES = tuple(_SNAPSHOT["sample_files"])
PORTING_NOTE = (
    f"Ported Python package for '{ARCHIVE_NAME}' — "
    f"{MODULE_COUNT} archived TypeScript modules → 1 Python screen module."
)

__all__ = [
    "DoctorScreen",
    "REPLScreen",
    "ResumeScreen",
    "Screen",
    "ScreenType",
    "make_screen",
    "ARCHIVE_NAME",
    "MODULE_COUNT",
    "PORTING_NOTE",
    "SAMPLE_FILES",
]
