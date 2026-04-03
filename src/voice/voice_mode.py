"""
Voice mode detection and configuration.

Ports: voice/voiceModeEnabled.ts
Provides voice mode flag, TTS/STT backend detection.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum


class VoiceMode(str, Enum):
    DISABLED = "disabled"
    STT_ONLY = "stt_only"   # speech → text
    TTS_ONLY = "tts_only"   # text → speech
    FULL     = "full"       # bidirectional


@dataclass
class VoiceConfig:
    enabled: bool = False
    mode: VoiceMode = VoiceMode.DISABLED
    stt_backend: str = ""
    tts_backend: str = ""
    stt_model: str = ""
    tts_voice: str = ""
    stream: bool = True       # stream responses as they arrive


def is_voice_mode_enabled(env: dict | None = None) -> bool:
    """
    Check if voice mode is enabled via environment / config.

    Ports: voice/voiceModeEnabled.ts
    """
    env = env or os.environ
    return (
        env.get("CLAW_VOICE", "").lower() in ("1", "true", "full", "stt", "tts")
        or env.get("VOICE_MODE", "").lower() in ("1", "true", "full", "stt", "tts")
    )


def detect_tts_backend() -> str:
    """
    Detect available TTS backends on the system.
    Returns the name of the first available backend.
    """
    # Check for macOS say command
    if shutil.which("say"):
        return "macos_say"

    # Check for espeak
    if shutil.which("espeak"):
        return "espeak"

    # Check for festival
    if shutil.which("festival"):
        return "festival"

    # Check for coqui /piper
    if shutil.which("piper"):
        return "piper"

    return ""


def detect_stt_backend() -> str:
    """
    Detect available STT (speech-to-text) backends.
    """
    # Check for whisper CLI
    if shutil.which("whisper"):
        return "whisper_cli"

    # Check for macOS speech recognition
    if shutil.which("siri"):
        return "macos_siri"

    return ""


def get_voice_config(env: dict | None = None) -> VoiceConfig:
    """
    Build a VoiceConfig from environment and system detection.
    """
    env = env or os.environ
    enabled = is_voice_mode_enabled(env)

    if not enabled:
        return VoiceConfig(enabled=False)

    mode_str = (env.get("CLAW_VOICE") or env.get("VOICE_MODE") or "full").lower()

    if mode_str in ("stt", "stt_only"):
        mode = VoiceMode.STT_ONLY
    elif mode_str in ("tts", "tts_only"):
        mode = VoiceMode.TTS_ONLY
    elif mode_str == "full":
        mode = VoiceMode.FULL
    else:
        mode = VoiceMode.DISABLED

    return VoiceConfig(
        enabled=True,
        mode=mode,
        stt_backend=detect_stt_backend(),
        tts_backend=detect_tts_backend(),
        stt_model=env.get("STT_MODEL", "base"),
        tts_voice=env.get("TTS_VOICE", ""),
        stream=env.get("VOICE_STREAM", "1").lower() not in ("0", "false"),
    )


# ---------------------------------------------------------------------------
# TTS helper (uses whichever backend is available)
# ---------------------------------------------------------------------------

def speak(text: str, backend: str | None = None) -> bool:
    """
    Convert text to speech using an available backend.

    Returns True on success.
    """
    backend = backend or detect_tts_backend()
    if not backend:
        return False

    try:
        if backend == "macos_say":
            subprocess.run(["say", text], check=True, capture_output=True)
            return True
        elif backend == "espeak":
            subprocess.run(["espeak", text], check=True, capture_output=True)
            return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return False


# ---------------------------------------------------------------------------
# STT helper (records and transcribes)
# ---------------------------------------------------------------------------

def listen(backend: str | None = None, duration_s: float = 5.0) -> str:
    """
    Record audio and transcribe using an available STT backend.

    Returns the transcribed text, or empty string on failure.
    """
    backend = backend or detect_stt_backend()
    if not backend:
        return ""

    # Placeholder — actual implementation would use platform audio APIs
    # and call whisper CLI or platform STT
    return ""


__all__ = [
    "VoiceMode",
    "VoiceConfig",
    "is_voice_mode_enabled",
    "get_voice_config",
    "detect_tts_backend",
    "detect_stt_backend",
    "speak",
    "listen",
]
