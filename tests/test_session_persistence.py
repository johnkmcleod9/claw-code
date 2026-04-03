"""
Tests for WP 8615 — Session persistence (save/restore conversations).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from src.session_store import (
    StoredMessage,
    StoredSession,
    SessionIndexEntry,
    make_session_id,
    save_session,
    load_session,
    list_sessions,
    delete_session,
    session_from_repl,
    restore_messages_to_provider,
    format_session_list,
    auto_title_from_messages,
    _SESSION_VERSION,
)


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def session_dir(tmp_path):
    return tmp_path / "sessions"


@pytest.fixture
def sample_session(session_dir):
    sid = make_session_id("/tmp/proj", "claude")
    msgs = [
        StoredMessage(role="system", content="You are a helpful assistant."),
        StoredMessage(role="user", content="What is 2 + 2?"),
        StoredMessage(role="assistant", content="2 + 2 = 4."),
    ]
    return StoredSession(
        session_id=sid,
        title="Math question",
        model="claude",
        workdir="/tmp/proj",
        stored_messages=msgs,
        input_tokens=100,
        output_tokens=20,
    )


# ── StoredMessage ─────────────────────────────────────────────────────────

def test_stored_message_roundtrip():
    sm = StoredMessage(role="user", content="hello")
    d = sm.to_dict()
    sm2 = StoredMessage.from_dict(d)
    assert sm2.role == "user"
    assert sm2.content == "hello"


def test_stored_message_with_tool_calls():
    sm = StoredMessage(
        role="assistant",
        content="",
        tool_calls=[{"id": "tc1", "name": "bash", "arguments": {"command": "ls"}}],
    )
    d = sm.to_dict()
    assert "tool_calls" in d
    sm2 = StoredMessage.from_dict(d)
    assert sm2.tool_calls[0]["name"] == "bash"


def test_stored_message_no_optional_keys():
    sm = StoredMessage(role="user", content="hi")
    d = sm.to_dict()
    assert "tool_calls" not in d
    assert "tool_call_id" not in d


# ── StoredSession ─────────────────────────────────────────────────────────

def test_stored_session_roundtrip(sample_session):
    d = sample_session.to_dict()
    s2 = StoredSession.from_dict(d)
    assert s2.session_id == sample_session.session_id
    assert s2.title == "Math question"
    assert s2.message_count == 3
    assert s2.stored_messages[1].content == "What is 2 + 2?"


def test_stored_session_display_title(sample_session):
    assert sample_session.display_title == "Math question"


def test_stored_session_display_title_fallback():
    sid = make_session_id()
    s = StoredSession(
        session_id=sid,
        stored_messages=[
            StoredMessage(role="user", content="Fix my code"),
        ],
    )
    assert s.display_title == "Fix my code"


def test_stored_session_age_label(sample_session):
    sample_session.updated_at = time.time() - 90  # 1.5 mins ago
    label = sample_session.age_label()
    assert "ago" in label


def test_stored_session_version():
    sid = make_session_id()
    s = StoredSession(session_id=sid)
    assert s.version == _SESSION_VERSION


# ── Save / Load ───────────────────────────────────────────────────────────

def test_save_and_load(sample_session, session_dir):
    path = save_session(sample_session, session_dir)
    assert path.exists()
    loaded = load_session(sample_session.session_id, session_dir)
    assert loaded.session_id == sample_session.session_id
    assert loaded.title == "Math question"
    assert loaded.message_count == 3


def test_load_nonexistent_raises(session_dir):
    with pytest.raises(FileNotFoundError):
        load_session("deadbeef1234", session_dir)


def test_load_corrupt_raises(session_dir, tmp_path):
    d = session_dir
    d.mkdir(parents=True, exist_ok=True)
    bad = d / "badbad.json"
    bad.write_text("not json at all {{{{")
    with pytest.raises(ValueError):
        load_session("badbad", d)


def test_save_updates_index(sample_session, session_dir):
    save_session(sample_session, session_dir)
    entries = list_sessions(session_dir)
    assert any(e.session_id == sample_session.session_id for e in entries)


def test_list_sessions_sorted_by_recency(session_dir):
    # Save two sessions with different timestamps
    s1 = StoredSession(session_id=make_session_id(), title="Old", updated_at=time.time() - 3600)
    s2 = StoredSession(session_id=make_session_id(), title="New", updated_at=time.time())
    save_session(s1, session_dir)
    save_session(s2, session_dir)
    entries = list_sessions(session_dir)
    assert entries[0].title == "New"
    assert entries[1].title == "Old"


def test_delete_session(sample_session, session_dir):
    save_session(sample_session, session_dir)
    ok = delete_session(sample_session.session_id, session_dir)
    assert ok
    entries = list_sessions(session_dir)
    assert not any(e.session_id == sample_session.session_id for e in entries)


def test_delete_nonexistent_returns_false(session_dir):
    ok = delete_session("doesnotexist", session_dir)
    assert not ok


# ── Legacy v1 migration ───────────────────────────────────────────────────

def test_legacy_v1_loads(session_dir):
    sid = make_session_id()
    legacy = {
        "session_id": sid,
        "messages": ["Hello from v1"],
        "input_tokens": 10,
        "output_tokens": 5,
    }
    path = session_dir
    path.mkdir(parents=True, exist_ok=True)
    (path / f"{sid}.json").write_text(json.dumps(legacy))

    loaded = load_session(sid, path)
    assert loaded.session_id == sid
    assert loaded.message_count == 1
    assert loaded.stored_messages[0].content == "Hello from v1"


# ── session_from_repl ──────────────────────────────────────────────────────

class FakeMessage:
    def __init__(self, role, content, tool_calls=None, tool_call_id=None):
        self.role = role
        self.content = content
        self.tool_calls = tool_calls or []
        self.tool_call_id = tool_call_id
        self.name = None


def test_session_from_repl():
    msgs = [
        FakeMessage("system", "You are helpful."),
        FakeMessage("user", "Write a script"),
        FakeMessage("assistant", "Sure, here's a script..."),
    ]
    stored = session_from_repl(
        session_id="abc123",
        messages=msgs,
        model="claude",
        workdir="/tmp",
        input_tokens=150,
        output_tokens=300,
    )
    assert stored.session_id == "abc123"
    assert stored.model == "claude"
    assert len(stored.stored_messages) == 3
    assert stored.input_tokens == 150


def test_auto_title_from_messages():
    msgs = [
        FakeMessage("system", "You are helpful"),
        FakeMessage("user", "Explain recursion in Python"),
    ]
    title = auto_title_from_messages(msgs)
    assert "recursion" in title.lower()


# ── restore_messages_to_provider ──────────────────────────────────────────

def test_restore_messages():
    class SimpleMessage:
        def __init__(self, role, content):
            self.role = role
            self.content = content

    stored = StoredSession(
        session_id="x",
        stored_messages=[
            StoredMessage(role="user", content="hello"),
            StoredMessage(role="assistant", content="world"),
        ],
    )
    msgs = restore_messages_to_provider(stored, SimpleMessage)
    assert len(msgs) == 2
    assert msgs[0].role == "user"
    assert msgs[1].content == "world"


# ── Format helpers ────────────────────────────────────────────────────────

def test_format_session_list_empty():
    output = format_session_list([])
    assert "no saved" in output.lower()


def test_format_session_list_has_entries():
    entry = SessionIndexEntry(
        session_id="abc1234567890abc",
        title="Test session",
        model="claude",
        workdir="/tmp",
        created_at=time.time() - 100,
        updated_at=time.time() - 50,
        message_count=5,
        input_tokens=200,
        output_tokens=100,
    )
    output = format_session_list([entry], color=False)
    assert "Test session" in output
    assert "abc12345" in output
