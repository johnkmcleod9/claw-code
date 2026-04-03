"""
Skill matcher — intelligent skill selection for a given context.

Ports: skills/matchSkill.ts, skills/skillMatcher.ts
Provides relevance scoring and automatic skill triggering.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .loader import Skill, list_skills, resolve_skill


# ---------------------------------------------------------------------------
# Match scoring
# ---------------------------------------------------------------------------

@dataclass
class ScoredSkillMatch:
    """A skill matched against a query with relevance scoring."""
    skill: Skill
    score: float           # 0.0 – 1.0
    matched_on: list[str]   # which fields matched
    reason: str = ""


# ---------------------------------------------------------------------------
# Keyword signal banks
# ---------------------------------------------------------------------------

_KEYWORD_SIGNALS: dict[str, dict[str, float]] = {
    "code": {
        "write": 0.8, "function": 0.7, "class": 0.7, "import": 0.6,
        "refactor": 0.9, "bug": 0.8, "fix": 0.8, "error": 0.6,
        "test": 0.7, "debug": 0.8, "lint": 0.6, "type": 0.5,
        "api": 0.6, "endpoint": 0.6, "database": 0.7, "sql": 0.6,
    },
    "security": {
        "security": 1.0, "vulnerability": 1.0, "auth": 0.8,
        "password": 0.7, "token": 0.6, "secret": 0.8,
        "injection": 1.0, "xss": 0.9, "csrf": 0.9,
        "encrypt": 0.8, "tls": 0.7, "https": 0.6,
        "permission": 0.6, "access": 0.5,
    },
    "docs": {
        "document": 0.9, "readme": 0.9, "comment": 0.7,
        "spec": 0.8, "specification": 0.8, "api": 0.6,
        "changelog": 0.7, "guide": 0.7, "tutorial": 0.7,
    },
    "test": {
        "test": 1.0, "coverage": 0.8, "pytest": 0.8,
        "unittest": 0.7, "integration": 0.7, "mock": 0.6,
        "assert": 0.5, "fail": 0.5,
    },
    "refactor": {
        "refactor": 1.0, "improve": 0.8, "clean": 0.7,
        "simplify": 0.8, "extract": 0.6, "rename": 0.5,
    },
    "deploy": {
        "deploy": 1.0, "release": 0.8, "build": 0.7,
        "docker": 0.7, "ci": 0.6, "cd": 0.6, "pipeline": 0.6,
    },
    "review": {
        "review": 1.0, "pr": 0.8, "pull": 0.8, "merge": 0.7,
        "approve": 0.6, "comment": 0.5,
    },
    "architecture": {
        "architecture": 1.0, "design": 0.8, "pattern": 0.7,
        "microservice": 0.8, "monolith": 0.6, "api": 0.5,
        "schema": 0.6, "model": 0.5,
    },
    "data": {
        "data": 0.8, "csv": 0.7, "json": 0.6, "parse": 0.6,
        "transform": 0.7, "pipeline": 0.6, "etl": 0.8,
    },
    "learning": {
        "learn": 0.9, "teach": 0.9, "explain": 0.8,
        "understand": 0.7, "course": 0.8, "training": 0.8,
        "instructional": 0.9, "elearning": 0.9,
    },
}

# Default skill fallbacks
_DEFAULT_SKILL_TRIGGERS: dict[str, list[str]] = {
    "debug":   ["debug", "what's happening", "why is", "error", "broken"],
    "verify":  ["verify", "check if", "validate", "correct"],
    "security": ["security", "vulnerability", "injection", "auth"],
    "simplify": ["simplify", "make simpler", "clearer", "easier to read"],
    "stuck":   ["stuck", "can't", "not working", "blocked"],
    "remember": ["remember", "note this", "save this", "don't forget"],
}


# ---------------------------------------------------------------------------
# Matcher
# ---------------------------------------------------------------------------

class SkillMatcher:
    """
    Match user queries against available skills and score relevance.

    Ports: skills/skillMatcher.ts, skills/matchSkill.ts
    """

    def __init__(self, cwd: Path | None = None):
        self._cwd = cwd

    def match(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.1,
    ) -> list[ScoredSkillMatch]:
        """
        Find skills that match a user query.

        Scoring combines:
        - Exact name match (highest weight)
        - Keyword signal matching
        - Description substring matching
        - Fallback trigger phrase matching
        """
        query_lower = query.lower()
        query_words = set(re.findall(r"\w+", query_lower))
        skills = list_skills(cwd=self._cwd)
        matches: list[tuple[float, ScoredSkillMatch]] = []

        for skill in skills:
            score, reasons = self._score_skill(skill, query_lower, query_words)
            if score >= threshold:
                matches.append((score, ScoredSkillMatch(
                    skill=skill,
                    score=score,
                    matched_on=reasons,
                )))

        matches.sort(key=lambda x: -x[0])
        return [m for _, m in matches[:top_k]]

    def _score_skill(
        self,
        skill: Skill,
        query_lower: str,
        query_words: set[str],
    ) -> tuple[float, list[str]]:
        score = 0.0
        reasons: list[str] = []

        # 1. Exact name match — highest weight
        name_lower = skill.name.lower()
        if query_lower.strip() == name_lower:
            score += 1.0
            reasons.append("exact_name")
        elif name_lower in query_lower:
            score += 0.5
            reasons.append("name_contains")
        elif query_lower.strip() in name_lower:
            score += 0.4
            reasons.append("name_contains_rev")

        # 2. Keyword signal matching
        for domain, signals in _KEYWORD_SIGNALS.items():
            domain_score = 0.0
            for kw, weight in signals.items():
                if kw in query_lower:
                    domain_score = max(domain_score, weight)
            if domain_score > 0:
                score += domain_score * 0.6
                reasons.append(f"signal:{domain}")

        # 3. Description matching
        desc_lower = skill.description.lower()
        if desc_lower and desc_lower in query_lower:
            score += 0.5
            reasons.append("description")
        elif desc_lower:
            desc_words = set(re.findall(r"\w+", desc_lower))
            overlap = query_words & desc_words
            if overlap:
                score += min(0.4, len(overlap) * 0.1)
                reasons.append("description_words")

        # 4. Trigger phrase matching (for bundled skills)
        triggers = _DEFAULT_SKILL_TRIGGERS.get(skill.name.lower(), [])
        for trigger in triggers:
            if trigger in query_lower:
                score += 0.7
                reasons.append("trigger")
                break

        # Normalize to 0.0–1.0
        score = min(1.0, score / 2.0)
        return score, reasons


# ---------------------------------------------------------------------------
# Auto-skill suggestion
# ---------------------------------------------------------------------------

def suggest_skills(
    query: str,
    cwd: Path | None = None,
    top_k: int = 3,
) -> list[ScoredSkillMatch]:
    """
    Suggest the most relevant skills for a query.

    Returns top-k SkillMatch objects, or empty list if nothing relevant.
    """
    matcher = SkillMatcher(cwd=cwd)
    return matcher.match(query, top_k=top_k, threshold=0.15)


def auto_inject_skills(
    query: str,
    context: dict | None = None,
    cwd: Path | None = None,
    max_inject: int = 3,
) -> list[Skill]:
    """
    Automatically inject relevant skills into a session context.

    Returns skills that should be included in the system prompt.
    """
    matches = suggest_skills(query, cwd=cwd, top_k=max_inject)
    return [m.skill for m in matches if m.score >= 0.25]


# ---------------------------------------------------------------------------
# Global matcher instance
# ---------------------------------------------------------------------------

_global_matcher = SkillMatcher()


def match_skills(query: str, **kw) -> list[ScoredSkillMatch]:
    return _global_matcher.match(query, **kw)


__all__ = [
    "ScoredSkillMatch",
    "SkillMatcher",
    "suggest_skills",
    "auto_inject_skills",
    "match_skills",
]
