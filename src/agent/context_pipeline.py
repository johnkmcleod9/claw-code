"""
Multi-stage context pipeline — WP 8616.

Stages (in order):
1. **Accumulate** — collect all messages from the session
2. **Estimate** — count tokens to decide whether action is needed
3. **Compact** — summarise old turns using the existing compaction module
4. **Memory inject** — prepend pinned memory snippets from the memory store
5. **Overflow guard** — hard-cap at model's context limit, dropping oldest
   non-system, non-pinned messages

The pipeline is a pure function: messages in → messages out.  No I/O side
effects; calling code decides whether to apply the result.

Usage::

    from src.agent.context_pipeline import run_pipeline, PipelineConfig

    config = PipelineConfig(
        model_context_tokens=200_000,  # Claude 3.5 Sonnet
        compact_threshold_pct=0.60,    # compact when 60% full
        memory_snippets=[...],         # optional pinned lines
    )
    messages, report = await run_pipeline(messages, config)

The returned ``report`` dict describes what each stage did so the caller can
log, display, or persist it.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from src.providers.base import Message
from .compaction import compact_messages, estimate_tokens

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class PipelineConfig:
    """
    Configuration for the context pipeline.

    Attributes:
        model_context_tokens: Hard context limit for the target model.
        compact_threshold_pct: Fraction of context that triggers compaction
            (0.0–1.0, default 0.60 = 60%).
        overflow_threshold_pct: Fraction at which overflow-guard kicks in
            after compaction (default 0.90 = 90%).
        keep_recent_turns: How many recent user/assistant pairs to protect
            from compaction.
        memory_snippets: Pinned text fragments to inject as a system-level
            memory block.  Each snippet should be a short string (≤ 200 chars).
        memory_header: Label printed before the injected memory block.
        compact_keep_recent: ``keep_recent`` passed to ``compact_messages``.
        enabled: Set False to bypass the pipeline (passthrough mode).
    """
    model_context_tokens: int = 200_000
    compact_threshold_pct: float = 0.60
    overflow_threshold_pct: float = 0.90
    keep_recent_turns: int = 6
    memory_snippets: list[str] = field(default_factory=list)
    memory_header: str = "## Injected Memory"
    compact_keep_recent: int = 6
    enabled: bool = True


# ---------------------------------------------------------------------------
# Pipeline report
# ---------------------------------------------------------------------------

@dataclass
class PipelineReport:
    """Summary of what the pipeline did."""
    elapsed_ms: float = 0.0
    input_messages: int = 0
    output_messages: int = 0
    estimated_tokens_before: int = 0
    estimated_tokens_after: int = 0
    compacted: bool = False
    memory_injected: bool = False
    memory_snippets_count: int = 0
    overflow_trimmed: bool = False
    overflow_dropped: int = 0
    stages: list[str] = field(default_factory=list)

    def summary(self) -> str:
        parts: list[str] = []
        if self.compacted:
            parts.append("compacted")
        if self.memory_injected:
            parts.append(f"memory({self.memory_snippets_count} snippets)")
        if self.overflow_trimmed:
            parts.append(f"overflow-trimmed({self.overflow_dropped} msgs dropped)")
        if not parts:
            parts.append("passthrough")
        tok_change = self.estimated_tokens_after - self.estimated_tokens_before
        sign = "+" if tok_change >= 0 else ""
        return (
            f"pipeline[{', '.join(parts)}] "
            f"tokens: {self.estimated_tokens_before:,} → {self.estimated_tokens_after:,} "
            f"({sign}{tok_change:,}) in {self.elapsed_ms:.0f}ms"
        )


# ---------------------------------------------------------------------------
# Stage implementations
# ---------------------------------------------------------------------------

def _stage_estimate(
    messages: list[Message],
    report: PipelineReport,
) -> tuple[list[Message], int]:
    """Stage 1: estimate token count."""
    tokens = estimate_tokens(messages)
    report.stages.append("estimate")
    report.estimated_tokens_before = tokens
    return messages, tokens


def _stage_compact(
    messages: list[Message],
    config: PipelineConfig,
    report: PipelineReport,
    current_tokens: int,
) -> tuple[list[Message], int]:
    """Stage 2: compact if above threshold."""
    threshold = int(config.model_context_tokens * config.compact_threshold_pct)
    if current_tokens < threshold:
        return messages, current_tokens

    compacted = compact_messages(
        messages,
        max_tokens=threshold,
        keep_recent=config.compact_keep_recent,
    )
    new_tokens = estimate_tokens(compacted)
    report.compacted = True
    report.stages.append(f"compact(before={current_tokens}, after={new_tokens})")
    return compacted, new_tokens


def _stage_inject_memory(
    messages: list[Message],
    config: PipelineConfig,
    report: PipelineReport,
) -> list[Message]:
    """
    Stage 3: inject pinned memory snippets.

    Memory is inserted as a synthetic user message right after the system
    prompt (index 0 if role==system, otherwise prepended).  This mirrors
    how Claude Code injects memory — it's visible to the model but marked
    clearly as injected context.
    """
    snippets = [s.strip() for s in config.memory_snippets if s.strip()]
    if not snippets:
        return messages

    memory_text = config.memory_header + "\n\n" + "\n".join(f"- {s}" for s in snippets)
    memory_msg = Message(role="user", content=memory_text)

    # Find insertion point: after system message if present
    if messages and messages[0].role == "system":
        result = [messages[0], memory_msg] + list(messages[1:])
    else:
        result = [memory_msg] + list(messages)

    report.memory_injected = True
    report.memory_snippets_count = len(snippets)
    report.stages.append(f"inject_memory({len(snippets)} snippets)")
    return result


def _stage_overflow_guard(
    messages: list[Message],
    config: PipelineConfig,
    report: PipelineReport,
    current_tokens: int,
) -> tuple[list[Message], int]:
    """
    Stage 4: overflow guard — hard-drop oldest non-system messages if still
    above the overflow threshold after compaction.

    We never drop:
    - The system message (index 0 if role==system)
    - The last ``keep_recent_turns * 2`` messages (user+assistant pairs)

    Messages are dropped from oldest first until we're under the ceiling.
    """
    ceiling = int(config.model_context_tokens * config.overflow_threshold_pct)
    if current_tokens <= ceiling:
        return messages, current_tokens

    # Identify protected zone
    protected_tail = config.keep_recent_turns * 2
    has_system = messages and messages[0].role == "system"
    system_slice = messages[:1] if has_system else []
    body = messages[1:] if has_system else messages[:]
    tail = body[-protected_tail:] if len(body) > protected_tail else body
    droppable = body[:-protected_tail] if len(body) > protected_tail else []

    dropped = 0
    while droppable and current_tokens > ceiling:
        droppable.pop(0)
        dropped += 1
        current_tokens = estimate_tokens(system_slice + droppable + tail)

    if dropped > 0:
        messages = system_slice + droppable + tail
        new_tokens = estimate_tokens(messages)
        report.overflow_trimmed = True
        report.overflow_dropped = dropped
        report.stages.append(f"overflow_guard(dropped={dropped})")
        return messages, new_tokens

    return messages, current_tokens


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def run_pipeline(
    messages: list[Message],
    config: PipelineConfig | None = None,
) -> tuple[list[Message], PipelineReport]:
    """
    Run the full context pipeline on a message list.

    This is an async function (future-proof for async compaction) but
    currently executes synchronously.

    Args:
        messages: Current conversation messages.
        config: Pipeline configuration.  Defaults to PipelineConfig().

    Returns:
        (processed_messages, report) tuple.
    """
    cfg = config or PipelineConfig()
    report = PipelineReport(input_messages=len(messages))
    t0 = time.monotonic()

    if not cfg.enabled or not messages:
        report.output_messages = len(messages)
        report.estimated_tokens_before = estimate_tokens(messages)
        report.estimated_tokens_after = report.estimated_tokens_before
        report.elapsed_ms = (time.monotonic() - t0) * 1000
        report.stages.append("disabled/passthrough")
        return messages, report

    # Stage 1: Estimate
    msgs, tokens = _stage_estimate(messages, report)

    # Stage 2: Compact if needed
    msgs, tokens = _stage_compact(msgs, cfg, report, tokens)

    # Stage 3: Inject memory
    msgs = _stage_inject_memory(msgs, cfg, report)
    tokens = estimate_tokens(msgs)  # re-estimate after injection

    # Stage 4: Overflow guard
    msgs, tokens = _stage_overflow_guard(msgs, cfg, report, tokens)

    report.output_messages = len(msgs)
    report.estimated_tokens_after = tokens
    report.elapsed_ms = (time.monotonic() - t0) * 1000

    return msgs, report


def run_pipeline_sync(
    messages: list[Message],
    config: PipelineConfig | None = None,
) -> tuple[list[Message], PipelineReport]:
    """
    Synchronous wrapper around run_pipeline for use outside async contexts.
    """
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Inside an existing event loop — create a future and run
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, run_pipeline(messages, config))
                return future.result()
        else:
            return loop.run_until_complete(run_pipeline(messages, config))
    except RuntimeError:
        return asyncio.run(run_pipeline(messages, config))


# ---------------------------------------------------------------------------
# Memory snippet helpers
# ---------------------------------------------------------------------------

def load_memory_snippets(memory_path: str | None = None) -> list[str]:
    """
    Load memory snippets from a flat text file (one snippet per line).

    This is a lightweight helper for the REPL — the full memory system
    uses session_store and session_memory service.  Each non-empty,
    non-comment line in the file becomes one snippet.

    Args:
        memory_path: Path to the memory file.  Defaults to
            ``~/.claw/memory.txt``.

    Returns:
        List of snippet strings (stripped, non-empty).
    """
    from pathlib import Path
    path = Path(memory_path) if memory_path else Path.home() / ".claw" / "memory.txt"
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return [
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith("#")
    ]


def build_pipeline_config(
    model_context_tokens: int = 200_000,
    compact_at: float = 0.60,
    memory_path: str | None = None,
    extra_snippets: list[str] | None = None,
) -> PipelineConfig:
    """
    Convenience factory: load memory from disk + extra snippets, return config.

    Args:
        model_context_tokens: Context window size of the target model.
        compact_at: Fraction of context that triggers compaction.
        memory_path: Override path to memory.txt.
        extra_snippets: Additional in-memory snippets to inject.

    Returns:
        PipelineConfig ready to pass to run_pipeline.
    """
    snippets = load_memory_snippets(memory_path)
    if extra_snippets:
        snippets.extend(extra_snippets)
    return PipelineConfig(
        model_context_tokens=model_context_tokens,
        compact_threshold_pct=compact_at,
        memory_snippets=snippets,
    )
