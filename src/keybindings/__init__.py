"""
Python keybindings subsystem — 14 modules for keyboard shortcut handling.

Provides keybinding parsing, resolution, matching, and display formatting
for the Claw Code CLI REPL.

Modules:
- ``parser``          ParsedKeybinding, Modifier, Key enums, parse_keybinding(), resolver
- ``shortcut_format`` Formatted display strings (symbols, platform labels, tables)
- ``load_user``       Load and merge user keybinding overrides from JSON config
- ``match``           Terminal escape sequence parsing and key event matching
- ``template``        Starter keybindings.json template generator

Ports: 14 archived TypeScript modules → 5 Python modules.
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
from .shortcut_format import (
    format_shortcut,
    format_shortcut_row,
    format_binding_table,
    parse_display_sequence,
)
from .load_user import (
    load_user_bindings,
    merge_bindings,
    ensure_keybindings_dir,
)
from .match import (
    KeyEvent,
    match_binding,
    parse_terminal_sequence,
    key_event_matches_binding,
)
from .template import (
    generate_user_bindings_template,
    get_default_bindings_list,
    generate_full_bindings_file,
)

__all__ = [
    # parser
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
    # shortcut_format
    "format_shortcut",
    "format_shortcut_row",
    "format_binding_table",
    "parse_display_sequence",
    # load_user
    "load_user_bindings",
    "merge_bindings",
    "ensure_keybindings_dir",
    # match
    "KeyEvent",
    "match_binding",
    "parse_terminal_sequence",
    "key_event_matches_binding",
    # template
    "generate_user_bindings_template",
    "get_default_bindings_list",
    "generate_full_bindings_file",
]
