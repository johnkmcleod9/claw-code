"""
Skills execution pipeline — end-to-end orchestration.

Ports: skills/skillPipeline.ts, skills/skillMiddleware.ts

Chains: discover → match → load (with cache) → execute → emit events.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .cache import SkillCache, get_default_cache
from .discovery import SkillIndex, build_skill_index
from .executor import SkillExecutionContext, execute_skill, inject_skill_into_system_prompt
from .loader import Skill, resolve_skill
from .matcher import match_skills
from .types import SkillEvent, SkillMatch, SkillResult


# ---------------------------------------------------------------------------
# Middleware protocol
# ---------------------------------------------------------------------------

MiddlewareFn = Callable[["PipelineRequest", "PipelineResponse | None"], "PipelineResponse | None"]


@dataclass
class PipelineRequest:
    """Input to a skill pipeline run."""
    query: str
    top_k: int = 3
    min_score: float = 0.2
    inputs: dict[str, Any] = field(default_factory=dict)
    cwd: Path | None = None
    inject_into_system: bool = True
    existing_system: str = ""


@dataclass
class PipelineResponse:
    """Output of a skill pipeline run."""
    matched: list[SkillMatch] = field(default_factory=list)
    executed: list[SkillResult] = field(default_factory=list)
    injected_system: str = ""
    events: list[SkillEvent] = field(default_factory=list)
    error: str = ""

    @property
    def success(self) -> bool:
        return not self.error and any(r.success for r in self.executed)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class SkillPipeline:
    """
    Composable skill execution pipeline.

    Usage::

        pipeline = SkillPipeline(cwd=Path.cwd())
        response = await pipeline.run(PipelineRequest(query="help me debug"))
        if response.injected_system:
            full_system = response.injected_system + my_system_prompt
    """

    def __init__(
        self,
        cwd: Path | None = None,
        cache: SkillCache | None = None,
        middleware: list[MiddlewareFn] | None = None,
        auto_build_index: bool = True,
    ) -> None:
        self.cwd = cwd or Path.cwd()
        self.cache = cache or get_default_cache()
        self.middleware: list[MiddlewareFn] = middleware or []
        self._index: SkillIndex | None = None

        if auto_build_index:
            self._index = build_skill_index(cwd=self.cwd)

    # ── Index ──────────────────────────────────────────────────────────────

    def rebuild_index(self) -> None:
        """Force a fresh scan of skill directories."""
        self._index = build_skill_index(cwd=self.cwd)

    # ── Middleware ────────────────────────────────────────────────────────

    def use(self, fn: MiddlewareFn) -> "SkillPipeline":
        """Register a middleware function. Returns self for chaining."""
        self.middleware.append(fn)
        return self

    # ── Core run ──────────────────────────────────────────────────────────

    async def run(self, request: PipelineRequest) -> PipelineResponse:
        """
        Execute the full pipeline for a query.

        Steps:
        1. Match skills from the index.
        2. Load matched skills (with cache).
        3. Execute each skill.
        4. Optionally compose system prompt injection.
        """
        response = PipelineResponse()

        # 1. Match
        all_skills = self._get_all_skills()
        response.matched = match_skills(
            request.query,
            skills=all_skills,
            top_k=request.top_k,
            min_score=request.min_score,
        )

        if not response.matched:
            return response

        response.events.append(SkillEvent(
            "matched",
            skill_name=",".join(m.skill_name for m in response.matched),
            data={"count": len(response.matched)},
        ))

        # 2. Load + execute
        system_blocks: list[str] = []
        for match in response.matched:
            skill = self._load_skill(match.skill_name)
            if skill is None:
                response.events.append(SkillEvent("error", match.skill_name, {"error": "not_found"}))
                continue

            ctx = SkillExecutionContext(
                skill=skill,
                inputs=request.inputs,
                user_query=request.query,
                inject_into_system=request.inject_into_system,
            )

            result = await execute_skill(ctx)
            response.executed.append(result)
            response.events.append(SkillEvent(
                "executed" if result.success else "error",
                skill.name,
                {"success": result.success, "duration_ms": result.duration_ms},
            ))

            if result.success and request.inject_into_system and isinstance(result.output, str):
                system_blocks.append(inject_skill_into_system_prompt(skill))

        # 3. Compose injected system
        if system_blocks:
            combined = "\n\n".join(system_blocks)
            if request.existing_system:
                response.injected_system = combined + "\n\n" + request.existing_system
            else:
                response.injected_system = combined

        # 4. Middleware (post-processing)
        for mw in self.middleware:
            try:
                result_override = mw(request, response)
                if result_override is not None:
                    response = result_override
            except Exception:
                pass

        return response

    # ── Helpers ───────────────────────────────────────────────────────────

    def _get_all_skills(self) -> list[Skill]:
        """Return all skills from index, using cache where possible."""
        if self._index is None:
            return []
        skills: list[Skill] = []
        for name in self._index.names():
            skill = self._load_skill(name)
            if skill:
                skills.append(skill)
        return skills

    def _load_skill(self, name: str) -> Skill | None:
        """Load a skill, using cache first."""
        cached = self.cache.get(name)
        if cached:
            return cached
        skill = resolve_skill(name, cwd=self.cwd)
        if skill:
            self.cache.put(skill)
        return skill


# ---------------------------------------------------------------------------
# Convenience helper
# ---------------------------------------------------------------------------

async def run_skill_pipeline(
    query: str,
    cwd: Path | None = None,
    top_k: int = 3,
    min_score: float = 0.2,
    existing_system: str = "",
) -> PipelineResponse:
    """
    One-shot helper: build a pipeline and run it.

    Returns:
        PipelineResponse with matched skills and injected system prompt.
    """
    pipeline = SkillPipeline(cwd=cwd)
    return await pipeline.run(PipelineRequest(
        query=query,
        top_k=top_k,
        min_score=min_score,
        existing_system=existing_system,
    ))


__all__ = [
    "PipelineRequest",
    "PipelineResponse",
    "SkillPipeline",
    "run_skill_pipeline",
    "MiddlewareFn",
]
