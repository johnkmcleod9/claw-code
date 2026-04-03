"""
Agent summary service — generate compact summaries of agent sessions.

Ports: services/AgentSummary/agentSummary.ts
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentTurnSummary:
    """Summary of a single agent turn."""
    turn_number: int
    user_request: str
    tools_used: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    outcome: str = ""
    cost_usd: float = 0.0


@dataclass
class AgentSessionSummary:
    """High-level summary of a complete agent session."""
    session_id: str
    total_turns: int
    total_cost_usd: float
    tools_used: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    key_accomplishments: list[str] = field(default_factory=list)
    turn_summaries: list[AgentTurnSummary] = field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [
            f"# Session Summary — `{self.session_id}`",
            "",
            f"**Turns:** {self.total_turns}  |  **Cost:** ${self.total_cost_usd:.4f}",
            "",
        ]

        if self.key_accomplishments:
            lines.append("## Accomplishments")
            lines.extend(f"- {a}" for a in self.key_accomplishments)
            lines.append("")

        if self.tools_used:
            lines.append(f"**Tools used:** {', '.join(self.tools_used)}")

        if self.files_modified:
            lines.append("## Files Modified")
            lines.extend(f"- `{f}`" for f in self.files_modified)

        return "\n".join(lines)

    def to_compact(self, max_chars: int = 400) -> str:
        """One-paragraph compact summary for context injection."""
        accomplishments = "; ".join(self.key_accomplishments[:3])
        files = ", ".join(f"`{f}`" for f in self.files_modified[:5])
        extra_files = f" (+{len(self.files_modified) - 5} more)" if len(self.files_modified) > 5 else ""
        return (
            f"Session {self.session_id}: {self.total_turns} turns, "
            f"${self.total_cost_usd:.4f}. {accomplishments}. "
            f"Files: {files}{extra_files}."
        )[:max_chars]


def summarize_session(
    session_id: str,
    messages: list[dict[str, Any]],
    stats: dict[str, Any] | None = None,
) -> AgentSessionSummary:
    """
    Build an AgentSessionSummary from raw message history.

    This is the heuristic path (no LLM call). For richer summaries,
    pass the output to an LLM with the context.

    Args:
        session_id: Unique session identifier.
        messages: List of message dicts with 'role' and 'content' keys.
        stats: Optional stats dict with 'total_cost_usd', 'turns', etc.
    """
    tools_used: set[str] = set()
    files_modified: set[str] = set()
    user_requests: list[str] = []
    turn_summaries: list[AgentTurnSummary] = []
    turn_num = 0

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        content_str = content if isinstance(content, str) else str(content)

        if role == "user" and content_str.strip():
            user_requests.append(content_str[:200])
            turn_num += 1

        # Extract tool names from tool call results
        if role == "tool" or (isinstance(content, list)):
            blocks = content if isinstance(content, list) else []
            for block in blocks:
                if isinstance(block, dict):
                    tool_name = block.get("name") or block.get("type", "")
                    if tool_name:
                        tools_used.add(tool_name)

        # Heuristic: extract file paths from content
        if isinstance(content_str, str):
            for match in re.finditer(r"[`'\"]([^\s`'\"]+\.[a-zA-Z]{1,10})[`'\"]", content_str):
                candidate = match.group(1)
                if "/" in candidate or candidate.startswith("."):
                    files_modified.add(candidate)

        # Extract tool calls from assistant messages
        tool_calls = msg.get("tool_calls", [])
        for tc in tool_calls:
            name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
            if name:
                tools_used.add(name)

    s = stats or {}
    total_cost = s.get("total_cost_usd", 0.0)
    total_turns = s.get("turns", turn_num)

    # Derive key accomplishments from user requests
    accomplishments = [r[:120] for r in user_requests[:5]]

    return AgentSessionSummary(
        session_id=session_id,
        total_turns=total_turns,
        total_cost_usd=total_cost,
        tools_used=sorted(tools_used),
        files_modified=sorted(files_modified),
        key_accomplishments=accomplishments,
        turn_summaries=turn_summaries,
    )


__all__ = [
    "AgentTurnSummary",
    "AgentSessionSummary",
    "summarize_session",
]
