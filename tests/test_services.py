"""Tests for the src/services subsystem."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# session_memory
# ---------------------------------------------------------------------------
from src.services.session_memory import MemoryEntry, SessionMemory, make_memory


def test_session_memory_set_get():
    mem = make_memory()
    mem.set("project", "claw-code")
    assert mem.get("project") == "claw-code"
    assert mem.get("missing") is None
    assert mem.get("missing", "default") == "default"


def test_session_memory_update():
    mem = make_memory()
    mem.set("key", "v1")
    mem.set("key", "v2")
    assert mem.get("key") == "v2"


def test_session_memory_search():
    mem = make_memory()
    mem.set("name", "Claw Code", tags=["project"])
    mem.set("author", "John", tags=["personal"])
    mem.set("name_of_project", "other")
    results = mem.search("name")
    assert len(results) == 2
    results_tagged = mem.search("name", tag="project")
    assert len(results_tagged) == 1
    assert results_tagged[0].tags == ["project"]


def test_session_memory_delete():
    mem = make_memory()
    mem.set("key", "value")
    assert "key" in mem
    assert mem.delete("key")
    assert "key" not in mem
    assert not mem.delete("nonexistent")


def test_session_memory_persist(tmp_path):
    path = tmp_path / "memory.json"
    mem = SessionMemory.load(path)
    mem.set("name", "Claw")
    mem.save()

    mem2 = SessionMemory.load(path)
    assert mem2.get("name") == "Claw"


def test_session_memory_to_context_block():
    mem = make_memory()
    mem.set("project", "claw-code", tags=["work"])
    block = mem.to_context_block()
    assert "<session_memory>" in block
    assert "claw-code" in block
    assert "[work]" in block


def test_memory_entry_to_from_dict():
    entry = MemoryEntry(key="k", value="v", tags=["t1"])
    d = entry.to_dict()
    restored = MemoryEntry.from_dict(d)
    assert restored.key == "k"
    assert restored.value == "v"
    assert restored.tags == ["t1"]


# ---------------------------------------------------------------------------
# api_client
# ---------------------------------------------------------------------------
from src.services.api_client import (
    ApiError,
    AuthError,
    RateLimitError,
    ServerError,
    UsageStats,
    raise_for_status,
)
from src.utils.http import HttpResponse


def test_usage_stats_add():
    a = UsageStats(input_tokens=100, output_tokens=50, cost_usd=0.01)
    b = UsageStats(input_tokens=200, output_tokens=100, cost_usd=0.02)
    c = a + b
    assert c.input_tokens == 300
    assert c.output_tokens == 150
    assert c.total_tokens == 450
    assert c.cost_usd == 0.03


def test_usage_stats_from_response():
    data = {
        "usage": {
            "input_tokens": 10,
            "output_tokens": 20,
            "cache_read_input_tokens": 5,
        }
    }
    s = UsageStats.from_response(data)
    assert s.input_tokens == 10
    assert s.output_tokens == 20
    assert s.cached_tokens == 5


def test_raise_for_status_success():
    resp = HttpResponse(status=200, headers={}, body=b"{}")
    result = raise_for_status(resp)
    assert result is resp


def test_raise_for_status_429():
    resp = HttpResponse(status=429, headers={}, body=b"rate limited")
    with pytest.raises(RateLimitError) as exc:
        raise_for_status(resp)
    assert exc.value.status == 429


def test_raise_for_status_401():
    resp = HttpResponse(status=401, headers={}, body=b"unauthorized")
    with pytest.raises(AuthError):
        raise_for_status(resp)


def test_raise_for_status_500():
    resp = HttpResponse(status=500, headers={}, body=b"error")
    with pytest.raises(ServerError):
        raise_for_status(resp)


# ---------------------------------------------------------------------------
# prompt_suggestion
# ---------------------------------------------------------------------------
from src.services.prompt_suggestion import (
    PromptSuggestion,
    SpeculationResult,
    speculate,
    suggest_from_context,
)


def test_suggest_from_context():
    suggestions = suggest_from_context(has_code=True, has_file_ops=False, limit=3)
    assert len(suggestions) <= 3
    assert all(isinstance(s, PromptSuggestion) for s in suggestions)
    # Higher scores first
    scores = [s.score for s in suggestions]
    assert scores == sorted(scores, reverse=True)


def test_suggest_from_context_empty():
    suggestions = suggest_from_context(limit=4)
    assert len(suggestions) <= 4


def test_speculate_debugging():
    result = speculate(["The code throws an exception on line 42"], context_tags=["debugging"])
    assert isinstance(result, SpeculationResult)
    assert result.confidence > 0
    assert len(result.suggestions) >= 1
    # debugging should trigger stack trace suggestion
    texts = [s.text for s in result.suggestions]
    assert any("stack trace" in t.lower() for t in texts)


def test_speculate_coding():
    result = speculate(["def foo(): return 42"], context_tags=["coding"])
    assert result.confidence > 0.5


# ---------------------------------------------------------------------------
# agent_summary
# ---------------------------------------------------------------------------
from src.services.agent_summary import (
    AgentSessionSummary,
    AgentTurnSummary,
    summarize_session,
)


def test_summarize_session_empty():
    summary = summarize_session("test-123", [])
    assert summary.session_id == "test-123"
    assert summary.total_turns == 0


def test_summarize_session_messages():
    messages = [
        {"role": "user", "content": "Write a function"},
        {"role": "assistant", "content": "Here's the function", "tool_calls": [{"name": "bash"}]},
    ]
    summary = summarize_session("test-456", messages)
    assert "bash" in summary.tools_used


def test_session_summary_markdown():
    s = AgentSessionSummary(
        session_id="test",
        total_turns=3,
        total_cost_usd=0.005,
        tools_used=["bash", "file_read"],
        files_modified=["foo.py"],
        key_accomplishments=["wrote foo.py"],
    )
    md = s.to_markdown()
    assert "test" in md
    assert "wrote foo.py" in md
    assert "foo.py" in md


def test_session_summary_to_compact():
    s = AgentSessionSummary(
        session_id="abc",
        total_turns=2,
        total_cost_usd=0.01,
        tools_used=["read"],
        files_modified=["a.py", "b.py"],
        key_accomplishments=["worked on files"],
    )
    compact = s.to_compact(max_chars=100)
    assert len(compact) <= 100


# ---------------------------------------------------------------------------
# analytics
# ---------------------------------------------------------------------------
from src.services.analytics import (
    Analytics,
    AnalyticsEvent,
    FileSink,
    MemorySink,
    NullSink,
    analytics_enabled,
)


def test_null_sink():
    sink = NullSink()
    sink.record(AnalyticsEvent(event="test"))
    sink.flush()  # should be no-op


def test_memory_sink():
    sink = MemorySink()
    analytics = Analytics(sink=sink)
    analytics.track("test_event", {"key": "value"})
    assert len(sink.events) == 1
    assert sink.events[0].event == "test_event"
    sink.clear()
    assert len(sink.events) == 0


def test_file_sink(tmp_path):
    path = tmp_path / "events.jsonl"
    sink = FileSink(path)
    sink.record(AnalyticsEvent(event="my_event", properties={"k": 1}))
    sink.flush()
    assert path.exists()
    lines = path.read_text().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["event"] == "my_event"


def test_analytics_tool_executed(tmp_path):
    sink = MemorySink()
    analytics = Analytics(session_id="s1", sink=sink)
    analytics.tool_executed("bash", success=True, duration_ms=123.4)
    assert len(sink.events) == 1
    assert sink.events[0].event == "tool_executed"
    assert sink.events[0].properties["tool"] == "bash"
    assert sink.events[0].properties["success"] is True


def test_analytics_disabled_via_env(monkeypatch):
    monkeypatch.setenv("CLAW_NO_ANALYTICS", "1")
    from importlib import reload
    import src.services.analytics as ana_module
    reload(ana_module)
    assert not ana_module.analytics_enabled()
    monkeypatch.delenv("CLAW_NO_ANALYTICS", raising=False)
    reload(ana_module)
    assert ana_module.analytics_enabled()  # reset


def test_analytics_session_lifecycle(tmp_path):
    sink = MemorySink()
    analytics = Analytics(session_id="s2", sink=sink)
    analytics.session_started(model="sonnet", workdir="/tmp")
    analytics.session_ended(turns=5, cost_usd=0.042)
    analytics.error_occurred("ValueError", "division by zero")
    analytics.model_switched("sonnet", "deepseek")
    assert len(sink.events) == 4


# ---------------------------------------------------------------------------
# __init__ re-exports
# ---------------------------------------------------------------------------
from src.services import (
    ARCHIVE_NAME,
    MODULE_COUNT,
    PORTING_NOTE,
    ApiError as _AE,
    SessionMemory as _SM,
    PromptSuggestion as _PS,
    Analytics as _An,
    AgentSessionSummary as _ASS,
)


def test_init_re_exports():
    assert ARCHIVE_NAME == "services"
    assert MODULE_COUNT == 130
    assert "Ported" in PORTING_NOTE or "ported" in PORTING_NOTE
    assert issubclass(_AE, Exception)
    assert issubclass(_SM, SessionMemory)
    assert isinstance(_PS("hello", 0.9), PromptSuggestion)
    assert isinstance(_ASS("sid", 0, 0.0), AgentSessionSummary)
