"""
Generate a starter keybindings.json for new users.

Ports: keybindings/template.ts
"""
from __future__ import annotations

from .parser import DEFAULT_BINDINGS, RESERVED


_USER_BINDINGS_TEMPLATE = """\
// Claw Code — User Keybindings
//
// This file overrides the default keybindings.
// Format: JSON array of { "key": "...", "command": "..." }
// Display-format keys (⌘P, ⌃C, etc.) are also accepted.
//
// Docs: https://github.com/johnkmcleod9/claw-code#keybindings

[
  // ── Navigation ────────────────────────────────────────────────────
  // { "key": "ctrl+p", "command": "command_palette" },

  // ── Session ──────────────────────────────────────────────────────
  // { "key": "ctrl+s", "command": "save" },
  // { "key": "escape", "command": "dismiss" },

  // ── Tool ─────────────────────────────────────────────────────────
  // { "key": "alt+t", "command": "toggle_tools" }
]
"""


def generate_user_bindings_template() -> str:
    """Return the starter keybindings.json template."""
    return _USER_BINDINGS_TEMPLATE.strip()


def get_default_bindings_list() -> list[dict[str, str]]:
    """Return the default bindings as a list of objects."""
    return [
        {"key": raw, "command": cmd}
        for raw, cmd in sorted(DEFAULT_BINDINGS.items())
    ]


def generate_full_bindings_file() -> str:
    """
    Generate a complete keybindings file showing all defaults with
    comments explaining which ones are reserved.
    """
    lines = [
        "// Claw Code — Default + Reserved Keybindings",
        "// Reserved shortcuts (cannot be overridden):",
        *[f"//   {r}" for r in sorted(RESERVED)],
        "",
        "[",
    ]
    for raw, cmd in sorted(DEFAULT_BINDINGS.items()):
        reserved_note = "  // RESERVED — cannot override" if raw in RESERVED else ""
        lines.append(f'  {{ "key": "{raw}", "command": "{cmd}" }},{reserved_note}')
    lines.append("]")
    return "\n".join(lines)
