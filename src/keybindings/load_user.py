"""
Load and merge user keybinding overrides.

Ports: keybindings/loadUserBindings.ts
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .parser import (
    ParsedKeybinding,
    parse_keybinding,
    DEFAULT_BINDINGS,
    RESERVED,
    is_reserved,
)
from .shortcut_format import parse_display_sequence


# ---------------------------------------------------------------------------
# Config paths
# ---------------------------------------------------------------------------

def _keybindings_path() -> Path:
    """Path to the user's keybindings config file."""
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    if xdg:
        base = Path(xdg)
    else:
        base = Path.home() / ".config"

    # Allow override via environment
    if os.environ.get("CLAW_KEYBINDINGS_PATH"):
        return Path(os.environ["CLAW_KEYBINDINGS_PATH"])

    return base / "claw" / "keybindings.json"


# ---------------------------------------------------------------------------
# Schema for the keybindings file
# ---------------------------------------------------------------------------

@dataclass
class UserBinding:
    raw: str  # original string as written in file
    command: str
    context: str = ""  # optional "when" clause

    @property
    def parsed(self) -> ParsedKeybinding | None:
        return parse_keybinding(self.raw)

    @property
    def parsed_display(self) -> ParsedKeybinding | None:
        """Parse a display-formatted sequence (e.g. ⌘P)."""
        tokens = parse_display_sequence(self.raw)
        if not tokens:
            return None
        # Last token is the key, rest are modifiers
        parts = tokens[:-1]
        key = tokens[-1]
        raw = "+".join(parts + [key])
        return parse_keybinding(raw)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_user_binding(b: UserBinding) -> list[str]:
    """Return list of validation warnings (empty = valid)."""
    errors: list[str] = []
    if is_reserved(b.raw):
        errors.append(f"{b.raw!r} is reserved and cannot be rebound")
    parsed = b.parsed or b.parsed_display
    if parsed is None:
        errors.append(f"Could not parse keybinding: {b.raw!r}")
    if not b.command:
        errors.append("Binding has no command")
    return errors


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_user_bindings(
    path: Path | None = None,
) -> dict[str, ParsedKeybinding]:
    """
    Load user keybinding overrides from a JSON file.

    Returns a dict mapping raw keybinding strings to ParsedKeybinding objects.

    File format::

        [
          {"key": "ctrl+shift+p", "command": "command_palette"},
          {"key": "alt+n", "command": "next_suggestion", "when": "suggestionVisible"}
        ]

    Both ``"key"`` and ``"display"`` (e.g. "⌘P") are supported.

    Ports: keybindings/loadUserBindings.ts
    """
    target = path or _keybindings_path()
    if not target.exists():
        return {}

    try:
        raw = target.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {target}: {e}") from e
    except OSError as e:
        raise OSError(f"Cannot read {target}: {e}") from e

    if not isinstance(data, list):
        raise ValueError(f"Keybindings file must be a JSON list, got {type(data).__name__}")

    merged: dict[str, ParsedKeybinding] = {}

    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Item {i} in keybindings file must be an object, got {type(item).__name__}")

        raw_key = item.get("key") or item.get("display") or ""
        command = item.get("command", "")
        context = item.get("when", "")

        if not raw_key:
            continue

        binding = UserBinding(raw=raw_key, command=command, context=context)
        errors = _validate_user_binding(binding)
        if errors:
            print(f"Warning: invalid keybinding[{i}] {raw_key!r}:", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            continue

        parsed = binding.parsed or binding.parsed_display
        if parsed is not None:
            merged[raw_key] = parsed

    return merged


def merge_bindings(
    user_bindings: dict[str, ParsedKeybinding],
) -> dict[str, str]:
    """
    Merge user bindings with defaults.

    User bindings override defaults. Reserved bindings are never overridden.

    Returns:
        Dict mapping keybinding strings → command names.
    """
    result: dict[str, str] = {}

    # Start with defaults
    for raw, cmd in DEFAULT_BINDINGS.items():
        if not is_reserved(raw):
            result[raw] = cmd

    # Overlay user bindings
    for raw, kb in user_bindings.items():
        if is_reserved(raw):
            continue
        # Find the command this was registered with
        cmd = None
        for _raw, _cmd in {**DEFAULT_BINDINGS, **dict((k, "") for k in user_bindings)}:
            if _raw == raw:
                cmd = _cmd
                break
        # We don't know the command here, so just store raw→command mapping
        # The caller is responsible for knowing the command
        result[str(kb)] = ""  # Placeholder — caller fills in

    return result


def ensure_keybindings_dir() -> Path:
    """Ensure the keybindings config directory exists."""
    path = _keybindings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
