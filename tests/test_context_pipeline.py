"""
Tests for WP 8616 — Multi-stage context pipeline.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from src.providers.base import Message
from src.agent.context_pipeline import (
    PipelineConfig,
    PipelineReport,
    run_pipeline,
    run_pipeline_sync,
    load_memory_snippets,
    build_pipeline_config,
    _stage_estimate,
    _stage_compact,
    _stage_inject_memory,
    _stage_overflow_guard,
)


# ── Helpers ────────────────────────────────────────────────────────────────

def make_messages(n: int, include_system: bool = True) -> list[Message]:
    """Build a simple conversation of n messages."""
    msgs: list[Message] = []
    if include_system:
        msgs.append(Message(role="system", content="You are a helpful assistant."))
    for i in range(n):
        msgs.append(Message(role="user", content=f"Question number {i + 1}. " + "x" * 100))
        msgs.append(Message(role="assistant", content=f"Answer number {i + 1}. " + "y" * 100))
    return msgs


# ── Estimate stage ─────────────────────────────────────────────────────────

def test_estimate_basic():
    msgs = make_messages(3)
    report = PipelineReport()
    _, tokens = _stage_estimate(msgs, report)
    assert tokens > 0
    assert report.estimated_tokens_before == tokens
    assert "estimate" in report.stages


def test_estimate_empty():
    report = PipelineReport()
    _, tokens = _stage_estimate([], report)
    assert tokens == 0


# ── Compact stage ─────────────────────────────────────────────────────────

def test_compact_not_triggered_below_threshold():
    msgs = make_messages(2)
    config = PipelineConfig(model_context_tokens=1_000_000, compact_threshold_pct=0.60)
    report = PipelineReport()
    tokens = len(str(msgs)) // 4
    out, _ = _stage_compact(msgs, config, report, tokens)
    assert not report.compacted
    assert out == msgs


def test_compact_triggered_above_threshold():
    # Create a big conversation
    msgs = make_messages(30)
    from src.agent.compaction import estimate_tokens
    tokens = estimate_tokens(msgs)
    # Set threshold very low so compaction triggers
    config = PipelineConfig(model_context_tokens=tokens // 2, compact_threshold_pct=0.10)
    report = PipelineReport()
    out, new_tokens = _stage_compact(msgs, config, report, tokens)
    assert report.compacted
    assert len(out) < len(msgs)


# ── Memory injection stage ─────────────────────────────────────────────────

def test_memory_inject_no_snippets():
    msgs = make_messages(2)
    config = PipelineConfig(memory_snippets=[])
    report = PipelineReport()
    out = _stage_inject_memory(msgs, config, report)
    assert not report.memory_injected
    assert out == msgs


def test_memory_inject_with_snippets():
    msgs = make_messages(2)
    config = PipelineConfig(
        memory_snippets=["User prefers short answers", "User is a Python expert"],
    )
    report = PipelineReport()
    out = _stage_inject_memory(msgs, config, report)
    assert report.memory_injected
    assert report.memory_snippets_count == 2
    # Memory injected after system message
    assert out[0].role == "system"
    assert out[1].role == "user"
    assert "Python expert" in out[1].content


def test_memory_inject_no_system_message():
    msgs = [
        Message(role="user", content="hello"),
    ]
    config = PipelineConfig(memory_snippets=["Remember: X"])
    report = PipelineReport()
    out = _stage_inject_memory(msgs, config, report)
    assert report.memory_injected
    # Memory prepended since no system message
    assert out[0].role == "user"
    assert "Remember: X" in out[0].content


def test_memory_inject_skips_empty_snippets():
    msgs = make_messages(1)
    config = PipelineConfig(memory_snippets=["  ", "", "Valid snippet"])
    report = PipelineReport()
    out = _stage_inject_memory(msgs, config, report)
    assert report.memory_snippets_count == 1


# ── Overflow guard stage ────────────────────────────────────────────────────

def test_overflow_guard_not_triggered():
    msgs = make_messages(5)
    from src.agent.compaction import estimate_tokens
    tokens = estimate_tokens(msgs)
    config = PipelineConfig(model_context_tokens=tokens * 10, overflow_threshold_pct=0.90)
    report = PipelineReport()
    out, _ = _stage_overflow_guard(msgs, config, report, tokens)
    assert not report.overflow_trimmed
    assert out == msgs


def test_overflow_guard_drops_oldest():
    msgs = make_messages(20)
    from src.agent.compaction import estimate_tokens
    tokens = estimate_tokens(msgs)
    # Very low ceiling to force drops
    config = PipelineConfig(
        model_context_tokens=tokens // 5,
        overflow_threshold_pct=0.50,
        keep_recent_turns=2,
    )
    report = PipelineReport()
    out, _ = _stage_overflow_guard(msgs, config, report, tokens)
    assert report.overflow_trimmed
    assert report.overflow_dropped > 0
    assert len(out) < len(msgs)


def test_overflow_guard_preserves_tail():
    msgs = make_messages(10, include_system=True)
    from src.agent.compaction import estimate_tokens
    tokens = estimate_tokens(msgs)
    config = PipelineConfig(
        model_context_tokens=tokens // 5,
        overflow_threshold_pct=0.10,
        keep_recent_turns=3,
    )
    report = PipelineReport()
    out, _ = _stage_overflow_guard(msgs, config, report, tokens)
    # System message always preserved
    assert out[0].role == "system"
    # Last 6 messages should be the tail (3 turns × 2)
    assert out[-1] == msgs[-1]
    assert out[-2] == msgs[-2]


# ── Full pipeline ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pipeline_passthrough_small():
    msgs = make_messages(2)
    config = PipelineConfig(model_context_tokens=200_000, compact_threshold_pct=0.60)
    out, report = await run_pipeline(msgs, config)
    assert len(out) == len(msgs)
    assert not report.compacted
    assert not report.memory_injected
    assert not report.overflow_trimmed


@pytest.mark.asyncio
async def test_pipeline_disabled_passthrough():
    msgs = make_messages(5)
    config = PipelineConfig(enabled=False)
    out, report = await run_pipeline(msgs, config)
    assert out == msgs
    assert "disabled" in report.stages[0]


@pytest.mark.asyncio
async def test_pipeline_empty_messages():
    out, report = await run_pipeline([], PipelineConfig())
    assert out == []


@pytest.mark.asyncio
async def test_pipeline_with_memory_snippets():
    msgs = make_messages(3)
    config = PipelineConfig(
        model_context_tokens=200_000,
        memory_snippets=["User likes brevity"],
    )
    out, report = await run_pipeline(msgs, config)
    assert report.memory_injected
    assert report.memory_snippets_count == 1


@pytest.mark.asyncio
async def test_pipeline_report_summary():
    msgs = make_messages(3)
    config = PipelineConfig(memory_snippets=["A memory"])
    out, report = await run_pipeline(msgs, config)
    summary = report.summary()
    assert "memory" in summary.lower() or "passthrough" in summary.lower()
    assert "ms" in summary


@pytest.mark.asyncio
async def test_pipeline_elapsed_recorded():
    msgs = make_messages(5)
    _, report = await run_pipeline(msgs, PipelineConfig())
    assert report.elapsed_ms >= 0


# ── Sync wrapper ──────────────────────────────────────────────────────────

def test_run_pipeline_sync():
    msgs = make_messages(2)
    out, report = run_pipeline_sync(msgs, PipelineConfig())
    assert len(out) >= 1
    assert report.elapsed_ms >= 0


# ── load_memory_snippets ──────────────────────────────────────────────────

def test_load_memory_snippets_missing_file(tmp_path):
    snippets = load_memory_snippets(str(tmp_path / "nonexistent.txt"))
    assert snippets == []


def test_load_memory_snippets_from_file(tmp_path):
    f = tmp_path / "memory.txt"
    f.write_text("# comment\nSnippet one\nSnippet two\n\n  \n")
    snippets = load_memory_snippets(str(f))
    assert len(snippets) == 2
    assert snippets[0] == "Snippet one"
    assert snippets[1] == "Snippet two"


# ── build_pipeline_config ─────────────────────────────────────────────────

def test_build_pipeline_config_defaults():
    config = build_pipeline_config()
    assert config.model_context_tokens == 200_000
    assert config.compact_threshold_pct == 0.60
    assert isinstance(config.memory_snippets, list)


def test_build_pipeline_config_extra_snippets():
    config = build_pipeline_config(extra_snippets=["extra1", "extra2"])
    assert "extra1" in config.memory_snippets
    assert "extra2" in config.memory_snippets
