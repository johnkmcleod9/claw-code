"""
Python voice subsystem — ported from 1 archived TypeScript module.

Provides voice mode enablement detection and configuration.

Module:
- ``voice_mode``  Voice mode flag, TTS/STT availability detection
"""
from __future__ import annotations

import json
from pathlib import Path

# ── Metadata from archived TS snapshot ──────────────────────────────────────
_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent.parent
    / "reference_data" / "subsystems" / "voice.json"
)
_SNAPSHOT = json.loads(_SNAPSHOT_PATH.read_text())
ARCHIVE_NAME = _SNAPSHOT["archive_name"]
MODULE_COUNT  = _SNAPSHOT["module_count"]
SAMPLE_FILES  = tuple(_SNAPSHOT["sample_files"])
PORTING_NOTE  = (
    f"Ported Python package for '{ARCHIVE_NAME}' — "
    f"{MODULE_COUNT} archived TypeScript module → 1 Python module."
)

from .voice_mode import (
    is_voice_mode_enabled,
    VoiceConfig,
    get_voice_config,
    VoiceMode,
    detect_tts_backend,
    detect_stt_backend,
    speak,
    listen,
)

__all__ = [
    "ARCHIVE_NAME", "MODULE_COUNT", "SAMPLE_FILES", "PORTING_NOTE",
    "is_voice_mode_enabled",
    "VoiceConfig",
    "get_voice_config",
    "VoiceMode",
    "detect_tts_backend",
    "detect_stt_backend",
    "speak",
    "listen",
]
