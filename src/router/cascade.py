"""
Cascade Runner — try cheap model first, escalate if quality is insufficient.

This is the core of the self-improving loop:
1. Route task to cheapest capable model
2. Run the task
3. Quick-judge the output (using a judge model)
4. If quality < threshold, escalate to a better model
5. Record results to update capability map
"""
from __future__ import annotations

import asyncio
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.profiles.loader import find_profile
from src.providers.openrouter import OpenRouterProvider
from src.providers.base import ModelConfig
from src.tools_impl.registry import ToolRegistry
from src.agent.loop import AgentLoop
from src.eval.judge import judge_result, JudgeResult
from .capability_map import CapabilityMap
from .strategy import RoutingStrategy, route_task, RoutingDecision


@dataclass
class CascadeResult:
    """Result of a cascade execution."""
    task: str
    category: str
    attempts: list[CascadeAttempt] = field(default_factory=list)

    @property
    def final_attempt(self) -> "CascadeAttempt | None":
        return self.attempts[-1] if self.attempts else None

    @property
    def total_cost(self) -> float:
        return sum(a.cost_usd for a in self.attempts)

    @property
    def total_time(self) -> float:
        return sum(a.time_seconds for a in self.attempts)

    @property
    def escalated(self) -> bool:
        return len(self.attempts) > 1

    @property
    def final_quality(self) -> float:
        if self.final_attempt and self.final_attempt.judge_result:
            return self.final_attempt.judge_result.quality_score
        return 0.0


@dataclass
class CascadeAttempt:
    """A single attempt within a cascade."""
    model_name: str
    response: str
    quality_score: float
    cost_usd: float
    time_seconds: float
    tokens_in: int
    tokens_out: int
    tool_calls: int
    judge_result: JudgeResult | None = None
    escalation_reason: str | None = None


class CascadeRunner:
    """
    Runs tasks with automatic escalation.

    Usage:
        runner = CascadeRunner(cap_map, registry)
        result = await runner.run(
            task="Fix the bug in paginator.py",
            category="engineering",
            workdir=Path("/path/to/workspace"),
        )
    """

    def __init__(
        self,
        cap_map: CapabilityMap,
        registry: ToolRegistry,
        judge_model: str = "sonnet",
        quality_threshold: float = 0.75,
        max_escalations: int = 2,
        strategy: RoutingStrategy = RoutingStrategy.BALANCED,
    ):
        self.cap_map = cap_map
        self.registry = registry
        self.judge_model = judge_model
        self.quality_threshold = quality_threshold
        self.max_escalations = max_escalations
        self.strategy = strategy

    async def run(
        self,
        task: str,
        category: str,
        workdir: Path | None = None,
        min_quality: float | None = None,
        skip_judge: bool = False,
    ) -> CascadeResult:
        """
        Run a task with automatic escalation.

        1. Route to cheapest capable model
        2. Execute task
        3. Judge quality (unless skip_judge=True)
        4. If below threshold, escalate to next model
        """
        threshold = min_quality or self.quality_threshold
        result = CascadeResult(task=task, category=category)

        # Get ordered list of models to try
        models_to_try = self._get_model_cascade(category, threshold)

        if not models_to_try:
            print(f"⚠️  No models meet quality threshold {threshold} for {category}",
                  file=sys.stderr)
            return result

        for i, model_name in enumerate(models_to_try):
            if i >= self.max_escalations + 1:  # +1 for initial attempt
                break

            escalation_reason = None
            if i > 0:
                prev = result.attempts[-1]
                escalation_reason = (
                    f"Previous model ({prev.model_name}) scored "
                    f"{prev.quality_score:.2f} < {threshold:.2f} threshold"
                )
                print(
                    f"\n🔄 Escalating to {model_name}: {escalation_reason}",
                    file=sys.stderr,
                )

            attempt = await self._run_attempt(
                task=task,
                model_name=model_name,
                category=category,
                workdir=workdir,
                skip_judge=skip_judge,
                escalation_reason=escalation_reason,
            )
            result.attempts.append(attempt)

            # If quality meets threshold or we're skipping judge, stop
            if skip_judge or attempt.quality_score >= threshold:
                break

        return result

    def _get_model_cascade(
        self, category: str, min_quality: float
    ) -> list[str]:
        """
        Get ordered list of models to try.

        Order: cheapest first (balanced), then by increasing quality.
        This ensures we try the cheap model first and only escalate
        to expensive ones when needed.
        """
        capable = self.cap_map.models_for_category(category, min_quality=0.0)
        if not capable:
            return []

        # Sort by cost (cheapest first), then by quality (as tiebreaker)
        sorted_models = sorted(
            capable,
            key=lambda m: (m.cost_for(category), -m.quality_for(category)),
        )

        return [m.model_name for m in sorted_models]

    async def _run_attempt(
        self,
        task: str,
        model_name: str,
        category: str,
        workdir: Path | None,
        skip_judge: bool,
        escalation_reason: str | None,
    ) -> CascadeAttempt:
        """Run a single attempt with a specific model."""
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"🤖 Attempting with: {model_name}", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)

        start = time.time()

        # Load profile and create provider
        profile = find_profile(model_name)
        provider = OpenRouterProvider(model_id=profile.model_id)

        # Create agent loop
        loop = AgentLoop(
            provider=provider,
            profile=profile,
            registry=self.registry,
            workdir=workdir or Path.cwd(),
            max_turns=15,
            stream=True,
        )

        try:
            response = await asyncio.wait_for(
                loop.run(task),
                timeout=240.0,
            )
        except asyncio.TimeoutError:
            elapsed = time.time() - start
            return CascadeAttempt(
                model_name=model_name,
                response="",
                quality_score=0.0,
                cost_usd=loop.stats.total_cost_usd,
                time_seconds=elapsed,
                tokens_in=loop.stats.total_input_tokens,
                tokens_out=loop.stats.total_output_tokens,
                tool_calls=loop.stats.tool_calls_made,
                escalation_reason=escalation_reason or "timeout",
            )

        elapsed = time.time() - start

        # Quick judge if not skipping
        quality = 0.0
        judge = None
        if not skip_judge:
            try:
                judge = await self._quick_judge(task, response, category)
                quality = judge.quality_score
            except Exception as e:
                print(f"  ⚠️  Judge failed: {e}", file=sys.stderr)
                quality = 0.5  # Assume mediocre if judge fails

        print(
            f"  📊 Quality: {quality:.2f} | "
            f"Cost: ${loop.stats.total_cost_usd:.4f} | "
            f"Time: {elapsed:.1f}s",
            file=sys.stderr,
        )

        return CascadeAttempt(
            model_name=model_name,
            response=response,
            quality_score=quality,
            cost_usd=loop.stats.total_cost_usd,
            time_seconds=elapsed,
            tokens_in=loop.stats.total_input_tokens,
            tokens_out=loop.stats.total_output_tokens,
            tool_calls=loop.stats.tool_calls_made,
            judge_result=judge,
            escalation_reason=escalation_reason,
        )

    async def _quick_judge(
        self, task: str, response: str, category: str
    ) -> JudgeResult:
        """
        Quick quality assessment using the judge model.

        Uses a simplified prompt focused on output quality rather
        than full benchmark evaluation.
        """
        from src.eval.judge import quick_judge
        return await quick_judge(
            task_description=task,
            agent_response=response,
            judge_model=self.judge_model,
        )
