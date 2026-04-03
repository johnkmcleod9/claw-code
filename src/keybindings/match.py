"""
Keybinding match logic — does a key event match a binding?

Ports: keybindings/match.ts
"""
from __future__ import annotations

from dataclasses import dataclass
from .parser import ParsedKeybinding, Modifier


@dataclass
class KeyEvent:
    """A key event from the terminal."""
    key: str          # lowercase key name, e.g. "p", "escape", "enter"
    modifiers: frozenset[str]  # "ctrl", "alt", "shift", "meta"
    raw: str = ""     # raw escape sequence if available


def normalize_key(key: str) -> str:
    """Normalize a key name from terminal input."""
    key = key.lower().strip()

    # Map common terminal escape sequences
    mappings: dict[str, str] = {
        "\x1b":     "escape",
        "\r":       "enter",
        "\n":       "enter",
        "\t":       "tab",
        " ":        "space",
        "\x7f":     "backspace",
        "\x03":     "ctrl+c",   # actually Ctrl+C is handled specially
        "\x04":     "ctrl+d",
        "\x1a":     "ctrl+z",
    }

    if key in mappings:
        return mappings[key]

    # Handle Ctrl+letter
    if len(key) == 1 and key.isalpha():
        # Could be ctrl+key
        pass

    return key


def parse_terminal_sequence(seq: str) -> KeyEvent:
    """
    Parse a terminal escape sequence into a KeyEvent.

    Handles common ANSI / xterm escape sequences:

    - ``\x1b[A`` → Up
    - ``\x1b[1;5A`` → Ctrl+Up  (5 = Ctrl modifier)
    - ``\x1b[1;3A`` → Alt+Up   (3 = Alt modifier)
    - ``\x1b[1;2A`` → Shift+Up (2 = Shift modifier)
    - ``\x1bOP``   → F1
    - ``\x1b[15~`` → F5
    """
    import re

    # ANSI cursor sequences: CSI + modifiers + letter
    # Format: ESC [ 1 ; modifier key
    CSI_RE = re.compile(r"^\x1b\[([0-9;]+)([A-Za-z~])$")
    # SS3 sequence: ESC O + key (for F1-F4, arrow keys on some terminals)
    SS3_RE = re.compile(r"^\x1bO([A-Za-z])$")

    seq = seq.replace("\x1b", "\x1b")  # normalize ESC

    # Try CSI
    m = CSI_RE.match(seq)
    if m:
        params_str = m.group(1)   # e.g. "" or "1" or "1;5"
        final_char = m.group(2)   # e.g. "A" or "~"
        modifiers: set[str] = set()
        base_key = ""

        # Parse modifiers: CSI params are ;-delimited numbers
        # Common patterns:
        #   ""    → no params, key is in final_char (e.g. \x1b[A = Up)
        #   "1"   → no modifier, key in final_char
        #   "1;5" → modifier=5(Ctrl), no base key in params
        # xterm also uses modifier bitmasks: 1=Shift, 2=Alt, 4=Ctrl → 5=Shift+Ctrl
        if params_str:
            parts = [p for p in params_str.split(";") if p]
            # Extract modifier bitmask (last numeric part if more than one)
            if len(parts) > 1:
                try:
                    modifier_bits = int(parts[-1])
                    if modifier_bits & 1:
                        modifiers.add("shift")
                    if modifier_bits & 2:
                        modifiers.add("alt")
                    if modifier_bits & 4:
                        modifiers.add("ctrl")
                except ValueError:
                    pass
        else:
            parts = []

        # Map final char to key
        key_map: dict[str, str] = {
            "A": "up", "B": "down", "C": "right", "D": "left",
            "H": "home", "F": "end",
            "P": "f1", "Q": "f2", "R": "f3", "S": "f4",
        }
        if final_char in key_map:
            base_key = key_map[final_char]
        elif final_char == "~":
            # F5-F12: 15~=F5, 17~=F6, 18~=F7, 19~=F8, 20~=F9, 21~=F10, 23~=F11, 24~=F12
            fkey_map = {
                "15": "f5", "17": "f6", "18": "f7", "19": "f8",
                "20": "f9", "21": "f10", "23": "f11", "24": "f12",
            }
            num = str(parts[-1]) if parts else "15"
            base_key = fkey_map.get(num, final_char)
        else:
            base_key = final_char.lower()

        return KeyEvent(key=base_key, modifiers=frozenset(modifiers), raw=seq)

    # Try SS3 (F1-F4, arrows on some terminals)
    m = SS3_RE.match(seq)
    if m:
        char = m.group(1)
        ss3_map: dict[str, str] = {
            "P": "f1", "Q": "f2", "R": "f3", "S": "f4",
            "A": "up", "B": "down", "C": "right", "D": "left",
        }
        return KeyEvent(key=ss3_map.get(char, char.lower()), modifiers=frozenset(), raw=seq)

    # Plain key
    return KeyEvent(key=normalize_key(seq), modifiers=frozenset(), raw=seq)


def key_event_matches_binding(event: KeyEvent, binding: ParsedKeybinding) -> bool:
    """
    Check whether a terminal KeyEvent matches a ParsedKeybinding.

    Modifiers must match exactly unless the binding has no modifiers
    (in which case the event's modifiers are ignored, allowing e.g.
    plain "p" to match "p" even if shift is held — for non-letter keys).
    """
    # Check key match
    if event.key != binding.key.value:
        return False

    # For letter keys, case doesn't matter for the base key
    # But modifier state must match
    binding_mods = {m.value for m in binding.modifiers}
    event_mods = set(event.modifiers)

    if binding_mods == event_mods:
        return True

    # Special case: letters with shift are often just the letter itself
    # e.g. Shift+P is detected as just "P" (uppercase) in many terminals
    if len(event.key) == 1 and event.key.isalpha():
        # If binding wants shift+letter and event has no modifiers,
        # it's still valid on terminals that encode uppercase as plain letter
        if binding_mods == {"shift"} and event_mods == set():
            return True

    return False


def match_binding(
    event: KeyEvent,
    bindings: list[tuple[ParsedKeybinding, str]],
) -> str | None:
    """
    Find the first binding that matches this key event.

    Args:
        event: Parsed terminal key event.
        bindings: List of (keybinding, command_name) pairs to check.

    Returns:
        Command name if matched, else None.
    """
    for kb, cmd in bindings:
        if key_event_matches_binding(event, kb):
            return cmd
    return None


def readline_to_key_event(readline_key: str, readline_mods: frozenset[str]) -> KeyEvent:
    """
    Convert readline-style key info to a KeyEvent.

    readline provides key names like "vi-move" or "emacs-editing-map" as well
    as simple characters.
    """
    # readline already gives us nice names
    key = readline_key.lower()
    # Map readline's internal names
    readline_map: dict[str, str] = {
        "rubout": "backspace",
        "delete-char": "delete",
        "accept-line": "enter",
        "previous-history": "up",
        "next-history": "down",
        "backward-char": "left",
        "forward-char": "right",
    }
    return KeyEvent(
        key=readline_map.get(key, key),
        modifiers=frozenset(m.lower() for m in readline_mods),
    )
