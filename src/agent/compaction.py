"""
Conversation compaction — summarize older messages when context grows too large.
"""
from __future__ import annotations

from src.providers.base import Message


def estimate_tokens(messages: list[Message]) -> int:
    """Rough token estimate (~4 chars per token)."""
    total_chars = 0
    for msg in messages:
        if isinstance(msg.content, str):
            total_chars += len(msg.content)
        elif isinstance(msg.content, list):
            for block in msg.content:
                if isinstance(block, dict):
                    total_chars += len(str(block))
    return total_chars // 4


def compact_messages(
    messages: list[Message],
    max_tokens: int = 50_000,
    keep_recent: int = 6,
) -> list[Message]:
    """
    Compact conversation by summarizing older messages.
    Keeps the system prompt (first message) and recent messages.
    Replaces middle messages with a summary.
    """
    if len(messages) <= keep_recent + 1:
        return messages

    estimated = estimate_tokens(messages)
    if estimated <= max_tokens:
        return messages

    # Keep system prompt + recent messages
    system_msgs = [m for m in messages[:1] if m.role == "system"]
    recent = messages[-keep_recent:]
    middle = messages[len(system_msgs):-keep_recent]

    if not middle:
        return messages

    # Build summary of middle messages
    summary_parts: list[str] = []
    for msg in middle:
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        if msg.role == "user":
            summary_parts.append(f"User: {content[:200]}")
        elif msg.role == "assistant":
            if msg.tool_calls:
                tool_names = [tc.name for tc in msg.tool_calls]
                summary_parts.append(f"Assistant used tools: {', '.join(tool_names)}")
            elif content.strip():
                summary_parts.append(f"Assistant: {content[:200]}")
        elif msg.role == "tool":
            summary_parts.append(f"Tool result: {content[:100]}")

    summary_text = (
        "[Conversation compacted. Summary of earlier messages:]\n"
        + "\n".join(summary_parts[:30])
    )

    summary_msg = Message(role="user", content=summary_text)

    return system_msgs + [summary_msg] + recent
