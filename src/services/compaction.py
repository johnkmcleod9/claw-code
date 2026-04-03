"""
Context compaction service.

Summarises a conversation when the context window grows too large,
replacing older messages with a compact summary so the session can continue.

Ports: services/compactConversation/ (conceptual), session/compaction logic
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass
class Message:
    """Minimal message representation used by the compaction service."""
    role: str          # "user" | "assistant" | "system"
    content: str
    token_count: int = 0
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompactionResult:
    """Outcome of a compaction operation."""
    summary: str
    messages_removed: int
    tokens_freed: int
    messages_kept: list[Message]
    compacted_at: float = field(default_factory=time.time)

    @property
    def total_messages_kept(self) -> int:
        return len(self.messages_kept)


# ---------------------------------------------------------------------------
# Compaction strategies
# ---------------------------------------------------------------------------

class CompactionStrategy:
    """Base class for compaction strategies."""

    def should_compact(self, messages: list[Message], token_limit: int) -> bool:
        raise NotImplementedError

    def compact(
        self,
        messages: list[Message],
        token_limit: int,
        summarise_fn: "SummariseFn | None" = None,
    ) -> CompactionResult:
        raise NotImplementedError


SummariseFn = "Callable[[list[Message]], str]"


class ThresholdCompactionStrategy(CompactionStrategy):
    """
    Compact when total token count exceeds a threshold.

    Keeps the system prompt + the most recent N messages; everything in between
    is replaced by a single summary message.

    Ports: conceptual equivalent of services/compactConversation
    """

    def __init__(
        self,
        threshold_fraction: float = 0.75,
        keep_recent: int = 20,
    ) -> None:
        self.threshold_fraction = threshold_fraction
        self.keep_recent = keep_recent

    def should_compact(self, messages: list[Message], token_limit: int) -> bool:
        total = sum(m.token_count for m in messages)
        return total >= token_limit * self.threshold_fraction

    def compact(
        self,
        messages: list[Message],
        token_limit: int,
        summarise_fn=None,
    ) -> CompactionResult:
        if not messages:
            return CompactionResult(
                summary="",
                messages_removed=0,
                tokens_freed=0,
                messages_kept=[],
            )

        # Separate system prompt (first message if role==system)
        system_msgs = [m for m in messages if m.role == "system"]
        non_system = [m for m in messages if m.role != "system"]

        # Keep the most recent messages
        if len(non_system) <= self.keep_recent:
            return CompactionResult(
                summary="",
                messages_removed=0,
                tokens_freed=0,
                messages_kept=messages,
            )

        to_summarise = non_system[: -self.keep_recent]
        to_keep = non_system[-self.keep_recent :]

        # Generate summary
        if summarise_fn is not None:
            summary_text = summarise_fn(to_summarise)
        else:
            summary_text = _default_summary(to_summarise)

        tokens_freed = sum(m.token_count for m in to_summarise)
        messages_removed = len(to_summarise)

        summary_msg = Message(
            role="assistant",
            content=f"[Previous conversation summary]\n{summary_text}",
            token_count=len(summary_text) // 4,  # rough estimate
        )

        kept = system_msgs + [summary_msg] + to_keep
        return CompactionResult(
            summary=summary_text,
            messages_removed=messages_removed,
            tokens_freed=tokens_freed,
            messages_kept=kept,
        )


def _default_summary(messages: list[Message]) -> str:
    """Produce a minimal summary without calling any external model."""
    user_count = sum(1 for m in messages if m.role == "user")
    assistant_count = sum(1 for m in messages if m.role == "assistant")
    topics: list[str] = []
    for m in messages:
        first_line = m.content.split("\n", 1)[0][:120]
        if first_line:
            topics.append(first_line)
    topic_list = "\n".join(f"- {t}" for t in topics[:5])
    return (
        f"Summary of {len(messages)} prior messages "
        f"({user_count} user, {assistant_count} assistant):\n{topic_list}"
    )


# ---------------------------------------------------------------------------
# Compaction service
# ---------------------------------------------------------------------------

class CompactionService:
    """
    High-level service that decides when and how to compact.

    Usage::

        svc = CompactionService(token_limit=100_000)
        if svc.should_compact(messages):
            result = svc.compact(messages)
            # result.messages_kept replaces the full history
    """

    def __init__(
        self,
        token_limit: int = 200_000,
        strategy: CompactionStrategy | None = None,
        summarise_fn=None,
    ) -> None:
        self.token_limit = token_limit
        self._strategy = strategy or ThresholdCompactionStrategy()
        self._summarise_fn = summarise_fn
        self._compact_count = 0

    def should_compact(self, messages: list[Message]) -> bool:
        return self._strategy.should_compact(messages, self.token_limit)

    def compact(self, messages: list[Message]) -> CompactionResult:
        result = self._strategy.compact(messages, self.token_limit, self._summarise_fn)
        if result.messages_removed > 0:
            self._compact_count += 1
        return result

    def compact_if_needed(self, messages: list[Message]) -> list[Message]:
        """
        Compact and return the new message list if needed; otherwise return original.
        """
        if self.should_compact(messages):
            return self.compact(messages).messages_kept
        return messages

    @property
    def compact_count(self) -> int:
        return self._compact_count

    def estimate_tokens(self, messages: list[Message]) -> int:
        """Sum of token_count fields; falls back to character-based estimate."""
        total = 0
        for m in messages:
            total += m.token_count or (len(m.content) // 4)
        return total


__all__ = [
    "CompactionResult",
    "CompactionService",
    "CompactionStrategy",
    "Message",
    "ThresholdCompactionStrategy",
]
