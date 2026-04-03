"""
Prompt suggestion service.

Ports: services/PromptSuggestion/promptSuggestion.ts,
       services/PromptSuggestion/speculation.ts
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class PromptSuggestion:
    """A suggested follow-up prompt."""
    text: str
    score: float = 1.0
    source: str = "heuristic"


# ---------------------------------------------------------------------------
# Static heuristic suggestions (no LLM call needed for the fast path)
# ---------------------------------------------------------------------------

_CONTINUATIONS: list[str] = [
    "Can you elaborate on that?",
    "Show me an example.",
    "What are the edge cases?",
    "How would I test this?",
    "Can you write the tests?",
    "What are the alternatives?",
    "Explain why you chose this approach.",
    "How does this handle errors?",
    "What would you change about this design?",
    "Summarize the key points.",
]

_CODING_FOLLOW_UPS: list[str] = [
    "Run the tests.",
    "Check for any lint errors.",
    "Add type hints.",
    "Write a docstring for this.",
    "Refactor this for clarity.",
    "What's the time complexity?",
    "Does this need a migration?",
]

_FILE_FOLLOW_UPS: list[str] = [
    "Show the full file.",
    "What other files does this affect?",
    "Search for related code.",
    "Check git log for recent changes.",
]


def suggest_from_context(
    last_assistant_message: str = "",
    last_user_message: str = "",
    has_code: bool = False,
    has_file_ops: bool = False,
    limit: int = 4,
) -> list[PromptSuggestion]:
    """
    Generate contextual prompt suggestions based on the conversation so far.

    This is the fast heuristic path; for LLM-based suggestions use
    :func:`suggest_with_llm`.
    """
    candidates: list[PromptSuggestion] = []

    if has_code:
        for text in _CODING_FOLLOW_UPS[:3]:
            candidates.append(PromptSuggestion(text=text, score=0.9, source="code_context"))

    if has_file_ops:
        for text in _FILE_FOLLOW_UPS[:2]:
            candidates.append(PromptSuggestion(text=text, score=0.85, source="file_context"))

    for text in _CONTINUATIONS[:limit]:
        candidates.append(PromptSuggestion(text=text, score=0.7, source="general"))

    # Deduplicate and return top N
    seen: set[str] = set()
    result: list[PromptSuggestion] = []
    for s in sorted(candidates, key=lambda x: x.score, reverse=True):
        if s.text not in seen:
            seen.add(s.text)
            result.append(s)
        if len(result) >= limit:
            break

    return result


# ---------------------------------------------------------------------------
# Speculation (pre-generate likely next steps)
# ---------------------------------------------------------------------------

@dataclass
class SpeculationResult:
    """Result of speculating about the user's next likely action."""
    suggestions: list[PromptSuggestion] = field(default_factory=list)
    confidence: float = 0.0
    reasoning: str = ""


def speculate(
    conversation_tail: list[str],
    context_tags: list[str] | None = None,
) -> SpeculationResult:
    """
    Speculate on the user's likely next prompt based on conversation tail.

    Ports: services/PromptSuggestion/speculation.ts

    Args:
        conversation_tail: Last few messages as plain strings.
        context_tags: Optional context hints (e.g. ['coding', 'debugging']).
    """
    tags = set(context_tags or [])
    text_blob = " ".join(conversation_tail).lower()

    # Detect what kind of conversation we're in
    is_coding = bool(re.search(r"\b(def |class |function|import|const |let |var )\b", text_blob))
    is_debugging = bool(re.search(r"\b(error|exception|traceback|bug|fix|fail)\b", text_blob))
    is_explaining = bool(re.search(r"\b(explain|why|how|what is|tell me)\b", text_blob))

    if "coding" in tags or is_coding:
        tags.add("coding")
    if "debugging" in tags or is_debugging:
        tags.add("debugging")

    suggestions = suggest_from_context(
        has_code="coding" in tags,
        has_file_ops="file" in tags,
        limit=3,
    )

    if is_debugging:
        suggestions.insert(0, PromptSuggestion(
            text="Show me the full stack trace.",
            score=0.95,
            source="speculation",
        ))

    if is_explaining:
        suggestions.insert(0, PromptSuggestion(
            text="Give me a concrete example.",
            score=0.9,
            source="speculation",
        ))

    confidence = 0.8 if tags else 0.5
    return SpeculationResult(
        suggestions=suggestions[:4],
        confidence=confidence,
        reasoning=f"Detected context: {', '.join(sorted(tags)) or 'general'}",
    )


__all__ = [
    "PromptSuggestion",
    "suggest_from_context",
    "SpeculationResult",
    "speculate",
]
