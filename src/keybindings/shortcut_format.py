"""
Shortcut display formatting for keybindings.

Ports: keybindings/shortcutFormat.ts, keybindings/useShortcutDisplay.ts
"""
from __future__ import annotations

from .parser import ParsedKeybinding, Key, Modifier, format_keybinding

# Platform-specific modifier display labels
_PLATFORM_LABELS: dict[str, str] = {
    "darwin": {"ctrl": "⌃", "alt": "⌥", "shift": "⇧", "meta": "⌘"},
    "win32":  {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "meta": "Win"},
    "linux":  {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "meta": "Super"},
}

# Fallback for unknown platforms
_DEFAULT_LABELS: dict[str, str] = {
    "ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "meta": "Meta",
}

# Key display symbols (macOS style, works across platforms)
_KEY_SYMBOLS: dict[str, str] = {
    "escape":     "Esc",
    "enter":      "↵",
    "backspace":  "⌫",
    "delete":     "⌦",
    "tab":        "⇥",
    "space":      "Space",
    "up":         "↑",
    "down":       "↓",
    "left":       "←",
    "right":      "→",
    "home":       "↖",
    "end":        "↘",
    "pageup":     "Page Up",
    "pagedown":   "Page Down",
    "f1":  "F1",   "f2":  "F2",  "f3":  "F3",  "f4":  "F4",
    "f5":  "F5",   "f6":  "F6",  "f7":  "F7",  "f8":  "F8",
    "f9":  "F9",   "f10": "F10", "f11": "F11", "f12": "F12",
    "n0": "0", "n1": "1", "n2": "2", "n3": "3", "n4": "4",
    "n5": "5", "n6": "6", "n7": "7", "n8": "8", "n9": "9",
}


def get_platform() -> str:
    """Detect the current platform."""
    import sys
    return sys.platform


def _mod_label(mod: Modifier, platform: str | None = None) -> str:
    plat = platform or get_platform()
    labels = _PLATFORM_LABELS.get(plat, _DEFAULT_LABELS)
    return labels.get(mod.value, mod.value)


def _key_label(key: Key) -> str:
    """Return a human-readable label for a key."""
    sym = _KEY_SYMBOLS.get(key.value)
    if sym:
        return sym
    # Single letters are upper-cased for display
    if len(key.value) == 1 and key.value.isalpha():
        return key.value.upper()
    return key.value


def format_shortcut(
    kb: ParsedKeybinding,
    platform: str | None = None,
    use_symbols: bool = True,
) -> str:
    """
    Format a keybinding as a display string.

    Args:
        kb: Parsed keybinding.
        platform: One of "darwin", "win32", "linux".  Defaults to current.
        use_symbols: If True (default), use symbols (⌘, ⌃, etc.)
                     If False, use plain text labels.

    Returns:
        Formatted display string, e.g. "⌘⇧P" or "Ctrl+Shift+P".
    """
    plat = platform or get_platform()
    parts = []

    for mod in sorted(kb.modifiers, key=lambda m: m.value):
        if use_symbols:
            label = _mod_label(mod, plat)
        else:
            label = _mod_label(mod, None)  # plain text
        parts.append(label)

    if use_symbols:
        parts.append(_key_label(kb.key))
    else:
        parts.append(kb.key.value.upper() if len(kb.key.value) == 1 else kb.key.value)

    if plat == "darwin" and use_symbols:
        # On macOS, use interfix spacing style: ⌘P
        return "".join(parts)
    else:
        return "+".join(parts)


def format_shortcut_row(
    command: str,
    display_name: str,
    kb: ParsedKeybinding,
    platform: str | None = None,
) -> str:
    """Format a single row for a keybinding table/list."""
    shortcut_str = format_shortcut(kb, platform=platform)
    return f"  {shortcut_str:<20}  {command:<30}  {display_name}"


def format_binding_table(
    bindings: dict[str, tuple[ParsedKeybinding, str]],
    platform: str | None = None,
) -> str:
    """
    Format a complete keybinding table.

    Args:
        bindings: Dict mapping command names to (keybinding, display_name).
        platform: Platform for label formatting.

    Returns:
        A formatted text table.
    """
    header = f"{'Shortcut':<20}  {'Command':<30}  Description"
    sep = "-" * len(header)
    lines = [header, sep]
    for cmd, (kb, name) in sorted(bindings.items()):
        lines.append(format_shortcut_row(cmd, name, kb, platform))
    return "\n".join(lines)


def parse_display_sequence(raw: str) -> list[str]:
    """
    Parse a display string back into a key sequence.

    E.g. "⌘P" → ["meta+p"], "Ctrl+Shift+P" → ["ctrl+shift+p"]

    Handles both symbol and plain-text formats.
    """
    import sys
    plat = sys.platform

    raw = raw.strip()

    # Try to expand symbols
    if plat == "darwin":
        replacements = [
            ("⌘", "meta"), ("⌃", "ctrl"), ("⌥", "alt"),
            ("⇧", "shift"), ("⌫", "backspace"), ("⌦", "delete"),
            ("↵", "enter"), ("⇥", "tab"),
        ]
        for sym, name in replacements:
            raw = raw.replace(sym, name + "+")
    else:
        replacements = [
            ("Ctrl+", "ctrl+"), ("Alt+", "alt+"),
            ("Shift+", "shift+"), ("Win+", "meta+"),
        ]
        for sym, name in replacements:
            raw = raw.replace(sym, name + "+")

    return [k.strip().lower() for k in raw.split("+") if k.strip()]
