"""
Tests for WP 8609 — Keybindings subsystem.
"""
from __future__ import annotations

import pytest

from src.keybindings.parser import (
    parse_keybinding,
    format_keybinding,
    DEFAULT_BINDINGS,
    RESERVED,
    is_reserved,
    ParsedKeybinding,
    Key,
    Modifier,
    KeybindingResolver,
)
from src.keybindings.shortcut_format import (
    format_shortcut,
    parse_display_sequence,
)
from src.keybindings.match import (
    KeyEvent,
    parse_terminal_sequence,
    key_event_matches_binding,
    match_binding,
)
from src.keybindings.template import (
    generate_user_bindings_template,
    get_default_bindings_list,
)
from src.keybindings.load_user import load_user_bindings


# ── parser ─────────────────────────────────────────────────────────────────

def test_parse_simple_key():
    kb = parse_keybinding("escape")
    assert kb is not None
    assert kb.key == Key.ESCAPE
    assert not kb.modifiers


def test_parse_ctrl_c():
    kb = parse_keybinding("ctrl+c")
    assert kb is not None
    assert kb.key == Key.C
    assert Modifier.CTRL in kb.modifiers


def test_parse_ctrl_shift_p():
    kb = parse_keybinding("ctrl+shift+p")
    assert kb is not None
    assert kb.key == Key.P
    assert Modifier.CTRL in kb.modifiers
    assert Modifier.SHIFT in kb.modifiers


def test_parse_cmd_equals_meta():
    kb = parse_keybinding("cmd+p")
    assert kb is not None
    assert Modifier.META in kb.modifiers


def test_parse_invalid():
    assert parse_keybinding("") is None
    assert parse_keybinding("not a key") is None


def test_format_keybinding():
    kb = parse_keybinding("ctrl+shift+p")
    assert format_keybinding(kb) == "ctrl+shift+p"


def test_reserved():
    assert is_reserved("ctrl+c")
    assert is_reserved("ctrl+d")
    assert not is_reserved("ctrl+p")


def test_resolver_register_and_resolve():
    resolver = KeybindingResolver()
    resolver.register_default()
    kb = parse_keybinding("escape")
    assert resolver.resolve(kb) == "dismiss"


# ── shortcut format ─────────────────────────────────────────────────────────

def test_format_shortcut_plain():
    kb = parse_keybinding("escape")
    assert format_shortcut(kb, use_symbols=False) == "Escape"


def test_format_shortcut_ctrl_c():
    kb = parse_keybinding("ctrl+c")
    assert "ctrl" in format_shortcut(kb, use_symbols=False).lower()
    assert "c" in format_shortcut(kb, use_symbols=False).lower()


def test_parse_display_sequence():
    tokens = parse_display_sequence("ctrl+p")
    assert tokens == ["ctrl", "p"]


# ── match ─────────────────────────────────────────────────────────────────

def test_parse_terminal_up():
    event = parse_terminal_sequence("\x1b[A")
    assert event.key == "up"


def test_parse_terminal_ctrl_up():
    # CSI 1;5A = Ctrl+Up
    event = parse_terminal_sequence("\x1b[1;5A")
    assert event.key == "up"
    assert "ctrl" in event.modifiers


def test_key_event_matches_exact():
    event = KeyEvent(key="escape", modifiers=frozenset())
    kb = parse_keybinding("escape")
    assert key_event_matches_binding(event, kb)


def test_key_event_matches_with_modifier():
    event = KeyEvent(key="c", modifiers=frozenset(["ctrl"]))
    kb = parse_keybinding("ctrl+c")
    assert key_event_matches_binding(event, kb)


def test_match_binding():
    bindings = [
        (parse_keybinding("escape"), "dismiss"),
        (parse_keybinding("enter"), "confirm"),
    ]
    event = KeyEvent(key="escape", modifiers=frozenset())
    assert match_binding(event, bindings) == "dismiss"


def test_match_binding_no_match():
    bindings = [(parse_keybinding("escape"), "dismiss")]
    event = KeyEvent(key="p", modifiers=frozenset())
    assert match_binding(event, bindings) is None


# ── template ───────────────────────────────────────────────────────────────

def test_generate_template():
    tpl = generate_user_bindings_template()
    assert "keybindings" in tpl.lower()
    assert "ctrl" in tpl


def test_get_default_bindings_list():
    bindings = get_default_bindings_list()
    assert len(bindings) > 0
    assert all("key" in b and "command" in b for b in bindings)


# ── load_user_bindings ─────────────────────────────────────────────────────

def test_load_nonexistent_file(tmp_path):
    bindings = load_user_bindings(tmp_path / "nonexistent.json")
    assert bindings == {}


def test_load_valid_bindings(tmp_path):
    import json
    f = tmp_path / "keybindings.json"
    f.write_text(json.dumps([
        {"key": "ctrl+shift+p", "command": "command_palette"},
        {"key": "alt+n", "command": "next"},
    ]))
    bindings = load_user_bindings(f)
    assert len(bindings) == 2


def test_load_invalid_binding_warns(tmp_path):
    import json
    import sys
    f = tmp_path / "keybindings.json"
    f.write_text(json.dumps([
        {"key": "ctrl+c", "command": "cannot_override_reserved"},
    ]))
    # Should not raise, just warn
    bindings = load_user_bindings(f)
    # ctrl+c is reserved and should be skipped
    assert bindings == {}
