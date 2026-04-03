"""
Keybinding parsing and resolution.

Ports: keybindings/parser.ts, keybindings/schema.ts,
       keybindings/shortcutFormat.ts, keybindings/match.ts,
       keybindings/resolver.ts
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


# ---------------------------------------------------------------------------
# Modifier and key types
# ---------------------------------------------------------------------------

class Modifier(Enum):
    CTRL  = "ctrl"
    ALT   = "alt"
    SHIFT = "shift"
    META  = "meta"    # Cmd on macOS, Win on Windows

    @classmethod
    def parse(cls, s: str) -> "Modifier":
        return cls(s.lower().replace("cmd", "meta").replace("command", "meta"))


class Key(str, Enum):
    """Well-known key names."""
    A = "a"; B = "b"; C = "c"; D = "d"; E = "e"; F = "f"; G = "g"
    H = "h"; I = "i"; J = "j"; K = "k"; L = "l"; M = "m"; N = "n"
    O = "o"; P = "p"; Q = "q"; R = "r"; S = "s"; T = "t"; U = "u"
    V = "v"; W = "w"; X = "x"; Y = "y"; Z = "z"
    N0 = "0"; N1 = "1"; N2 = "2"; N3 = "3"; N4 = "4"
    N5 = "5"; N6 = "6"; N7 = "7"; N8 = "8"; N9 = "9"
    ENTER  = "enter"
    ESCAPE = "escape"
    TAB    = "tab"
    SPACE  = "space"
    BACKSPACE = "backspace"
    DELETE = "delete"
    UP     = "up"
    DOWN   = "down"
    LEFT   = "left"
    RIGHT  = "right"
    HOME   = "home"
    END    = "end"
    PAGEUP = "pageup"
    PAGEDOWN = "pagedown"
    F1 = "f1"; F2 = "f2"; F3 = "f3"; F4 = "f4"
    F5 = "f5"; F6 = "f6"; F7 = "f7"; F8 = "f8"
    F9 = "f9"; F10 = "f10"; F11 = "f11"; F12 = "f12"

    @classmethod
    def from_str(cls, s: str) -> "Key":
        lowered = s.lower()
        return cls(lowered)


# ---------------------------------------------------------------------------
# Parsed keybinding
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ParsedKeybinding:
    """A parsed keybinding: zero or more modifiers + one key."""
    modifiers: frozenset[Modifier] = field(default_factory=frozenset)
    key: Key = Key.ENTER

    def matches(self, other: "ParsedKeybinding") -> bool:
        return self == other

    def __str__(self) -> str:
        parts = [m.value for m in sorted(self.modifiers, key=lambda m: m.value)]
        parts.append(self.key.value)
        return "+".join(parts)


# ---------------------------------------------------------------------------
# Parser (keybindings/parser.ts)
# ---------------------------------------------------------------------------

_KEY_NAME_RE = re.compile(r"^[a-z0-9][-a-z0-9]*$", re.IGNORECASE)


def parse_keybinding(raw: str) -> ParsedKeybinding | None:
    """
    Parse a keybinding string like "ctrl+c", "cmd+shift+p", "escape".

    Supports both "+"-separated and dash-separated formats.

    Ports: keybindings/parser.ts
    """
    if not raw:
        return None

    raw = raw.strip().lower()
    tokens = re.split(r"[+\s]+", raw)
    if not tokens:
        return None

    modifiers: list[Modifier] = []
    key_token = tokens[-1]

    for token in tokens[:-1]:
        t = token.strip()
        if not t:
            continue
        try:
            modifiers.append(Modifier.parse(t))
        except ValueError:
            return None

    try:
        key = Key.from_str(key_token)
    except ValueError:
        return None

    return ParsedKeybinding(modifiers=frozenset(modifiers), key=key)


def format_keybinding(kb: ParsedKeybinding) -> str:
    """Render a ParsedKeybinding as a human-readable string."""
    return str(kb)


# ---------------------------------------------------------------------------
# Default bindings (keybindings/defaultBindings.ts)
# ---------------------------------------------------------------------------

DEFAULT_BINDINGS: dict[str, str] = {
    "ctrl+c":         "cancel",
    "ctrl+d":         "exit",
    "ctrl+z":         "undo",
    "ctrl+s":         "save",
    "ctrl+w":         "close",
    "ctrl+r":         "reload",
    "ctrl+shift+p":   "command_palette",
    "escape":         "dismiss",
    "enter":          "confirm",
    "tab":            "next",
    "shift+tab":      "prev",
    "up":             "cursor_up",
    "down":           "cursor_down",
    "ctrl+up":        "scroll_up",
    "ctrl+down":      "scroll_down",
}

# Reserved shortcuts that cannot be rebound (keybindings/reservedShortcuts.ts)
RESERVED: frozenset[str] = frozenset({
    "ctrl+c",
    "ctrl+d",
    "ctrl+z",
    "ctrl+\\",       # SIGQUIT
})


def is_reserved(raw: str) -> bool:
    return raw.lower() in RESERVED


# ---------------------------------------------------------------------------
# Keybinding schema (keybindings/schema.ts)
# ---------------------------------------------------------------------------

@dataclass
class KeybindingSchema:
    """Schema describing a named keybinding."""
    name: str
    display_name: str
    description: str = ""
    category: str = "general"
    default: str = ""
    when: str = ""         # context expression (e.g. "editorFocus")


# ---------------------------------------------------------------------------
# Resolver (keybindings/resolver.ts)
# ---------------------------------------------------------------------------

@dataclass
class ResolvedBinding:
    keybinding: ParsedKeybinding
    command: str
    context: str = ""


class KeybindingResolver:
    """
    Resolves raw key events to commands using a layered binding map.

    Ports: keybindings/resolver.ts
    """

    def __init__(self) -> None:
        self._bindings: list[tuple[ParsedKeybinding, str]] = []
        self._commands: dict[str, str] = {}

    def register(self, keybinding: ParsedKeybinding, command: str) -> None:
        self._bindings.append((keybinding, command))

    def register_default(self) -> None:
        """Load the default binding map."""
        for raw, cmd in DEFAULT_BINDINGS.items():
            kb = parse_keybinding(raw)
            if kb:
                self.register(kb, cmd)

    def resolve(self, kb: ParsedKeybinding) -> str | None:
        """Return the command for *kb*, or None if unbound."""
        for bound, cmd in self._bindings:
            if bound == kb:
                return cmd
        return None

    def bound_command(self, raw: str) -> str | None:
        """Convenience: parse and resolve in one call."""
        kb = parse_keybinding(raw)
        if kb is None:
            return None
        return self.resolve(kb)


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
]
