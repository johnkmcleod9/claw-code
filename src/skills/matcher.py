"""
Skill matcher — find skills relevant to a given query or context.

Ports: skills/matchSkill.ts, skills/skillScorer.ts, skills/intentResolver.ts

Scores skills using:
1. Exact name match (highest priority)
2. Token overlap between query and skill name/description
3. Tag matching
4. Fuzzy prefix matching
"""
from __future__ import annotations

import re
from pathlib import Path

from .loader import Skill, list_skills
from .types import SkillMatch


# ---------------------------------------------------------------------------
# Tokenisation
# ---------------------------------------------------------------------------

_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "is", "in", "on", "at", "to", "of",
    "for", "with", "that", "this", "do", "can", "how", "what", "use",
    "i", "my", "me", "you", "your", "we", "our",
})


def _tokenise(text: str) -> list[str]:
    """Lowercase, strip punctuation, remove stop words."""
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return [t for t in tokens if t not in _STOP_WORDS]


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _score_skill(skill: Skill, query_tokens: list[str]) -> float:
    if not query_tokens:
        return 0.0

    name_tokens = _tokenise(skill.name)
    desc_tokens = _tokenise(skill.description)
    all_tokens = set(name_tokens) | set(desc_tokens) | set(skill.tags)

    total = len(query_tokens)
    matched = sum(1 for t in query_tokens if t in all_tokens)

    exact_bonus = 0.4 if skill.name.lower() in " ".join(query_tokens) else 0.0

    prefix_bonus = 0.0
    for qt in query_tokens:
        if any(st.startswith(qt) for st in all_tokens if len(qt) >= 3):
            prefix_bonus += 0.1
    prefix_bonus = min(prefix_bonus, 0.3)

    base_score = matched / total
    return min(1.0, base_score + exact_bonus + prefix_bonus)


def _build_reason(skill: Skill, query_tokens: list[str]) -> tuple[str, list[str]]:
    name_tokens = set(_tokenise(skill.name))
    desc_tokens = set(_tokenise(skill.description))
    tag_tokens  = set(skill.tags)

    matched: list[str] = []
    reasons: list[str] = []

    for qt in query_tokens:
        if qt in name_tokens:
            matched.append(qt)
            reasons.append(f"name:{qt}")
        elif qt in desc_tokens:
            matched.append(qt)
            reasons.append(f"desc:{qt}")
        elif qt in tag_tokens:
            matched.append(qt)
            reasons.append(f"tag:{qt}")

    reason = ", ".join(reasons[:4]) or "partial overlap"
    return reason, matched


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def match_skills(
    query: str,
    skills: list[Skill] | None = None,
    cwd: Path | None = None,
    top_k: int = 5,
    min_score: float = 0.1,
) -> list[SkillMatch]:
    """Find skills most relevant to *query*."""
    if skills is None:
        skills = list_skills(cwd)

    query_tokens = _tokenise(query)
    if not query_tokens:
        return []

    results: list[SkillMatch] = []
    for skill in skills:
        score = _score_skill(skill, query_tokens)
        if score >= min_score:
            reason, matched = _build_reason(skill, query_tokens)
            results.append(SkillMatch(
                skill_name=skill.name,
                score=score,
                reason=reason,
                matched_tokens=matched,
            ))

    results.sort(key=lambda m: -m.score)
    return results[:top_k]


def best_skill_match(
    query: str,
    skills: list[Skill] | None = None,
    cwd: Path | None = None,
    min_score: float = 0.3,
) -> SkillMatch | None:
    """Return the single best matching skill, or None if below threshold."""
    matches = match_skills(query, skills=skills, cwd=cwd, top_k=1, min_score=min_score)
    return matches[0] if matches else None


def rank_skills_for_intent(
    intent: str,
    available_skills: list[Skill],
) -> list[tuple[float, Skill]]:
    """Rank a list of skills by relevance to an expressed intent."""
    query_tokens = _tokenise(intent)
    scored = [
        (_score_skill(sk, query_tokens), sk)
        for sk in available_skills
    ]
    scored.sort(key=lambda x: -x[0])
    return scored


__all__ = [
    "match_skills",
    "best_skill_match",
    "rank_skills_for_intent",
    "SkillMatch",
]
