"""
Self-Improving Loop — analyzes benchmark failures and generates
improved system prompts per model.

The cycle:
1. Analyze eval results → identify failure patterns
2. Generate improved system prompts targeting weak areas
3. Write updated profiles
4. Re-run failed benchmarks to measure improvement
5. Update capability map

This is the "learning" part of the adaptive harness.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.profiles.loader import find_profile, load_profile
from src.providers import get_provider
from src.providers.base import Message, ModelConfig

from .capability_map import CapabilityMap, TaskScore


@dataclass
class FailurePattern:
    """A recurring failure pattern across benchmarks."""
    pattern_type: str  # "timeout", "empty_response", "low_quality", "tool_misuse", "off_topic"
    affected_tasks: list[str]
    category: str
    frequency: float  # 0.0-1.0
    details: str
    severity: str  # "critical", "major", "minor"


@dataclass
class ImprovementPlan:
    """Plan for improving a model's performance."""
    model_name: str
    current_quality: float
    target_quality: float
    failures: list[FailurePattern]
    prompt_changes: list[PromptChange]
    config_changes: dict[str, Any] = field(default_factory=dict)


@dataclass
class PromptChange:
    """A suggested change to the system prompt."""
    section: str  # "tool_usage", "output_format", "reasoning", "constraints"
    action: str  # "add", "modify", "remove", "emphasize"
    content: str
    rationale: str
    priority: int  # 1=highest


def analyze_failures(
    cap_map: CapabilityMap,
    model_name: str,
    results_dir: Path | None = None,
) -> list[FailurePattern]:
    """
    Analyze a model's benchmark results for recurring failure patterns.
    """
    model = cap_map.get(model_name)
    if not model:
        return []

    patterns: list[FailurePattern] = []

    for cat_name, cat in model.categories.items():
        # Pattern 1: Timeouts
        timed_out = [
            tid for tid, ts in cat.task_scores.items()
            if ts.completion_rate == 0.0
        ]
        if timed_out:
            patterns.append(FailurePattern(
                pattern_type="timeout",
                affected_tasks=timed_out,
                category=cat_name,
                frequency=len(timed_out) / len(cat.task_scores),
                details=f"{len(timed_out)}/{len(cat.task_scores)} tasks timed out in {cat_name}",
                severity="critical" if len(timed_out) > len(cat.task_scores) * 0.3 else "major",
            ))

        # Pattern 2: Low quality (completed but poor)
        low_quality = [
            tid for tid, ts in cat.task_scores.items()
            if ts.completion_rate > 0 and ts.quality < 0.7
        ]
        if low_quality:
            avg_q = sum(
                cat.task_scores[tid].quality for tid in low_quality
            ) / len(low_quality)
            patterns.append(FailurePattern(
                pattern_type="low_quality",
                affected_tasks=low_quality,
                category=cat_name,
                frequency=len(low_quality) / len(cat.task_scores),
                details=f"{len(low_quality)} tasks below 0.70 quality (avg {avg_q:.2f})",
                severity="major" if avg_q < 0.5 else "minor",
            ))

        # Pattern 3: Tool misuse (low tool success rate)
        tool_issues = [
            tid for tid, ts in cat.task_scores.items()
            if ts.completion_rate > 0 and ts.tool_success_rate < 0.8
        ]
        if tool_issues:
            patterns.append(FailurePattern(
                pattern_type="tool_misuse",
                affected_tasks=tool_issues,
                category=cat_name,
                frequency=len(tool_issues) / len(cat.task_scores),
                details=f"{len(tool_issues)} tasks with <80% tool success",
                severity="major",
            ))

        # Pattern 4: Slow but completes (3x+ slower than fastest model)
        if cat.avg_time_seconds > 60:
            patterns.append(FailurePattern(
                pattern_type="slow_execution",
                affected_tasks=list(cat.task_scores.keys()),
                category=cat_name,
                frequency=1.0,
                details=f"Average {cat.avg_time_seconds:.0f}s per task in {cat_name}",
                severity="minor",
            ))

    return sorted(patterns, key=lambda p: {"critical": 0, "major": 1, "minor": 2}[p.severity])


async def generate_improvement_plan(
    cap_map: CapabilityMap,
    model_name: str,
    current_profile_path: Path | None = None,
    analyst_model: str = "sonnet",
) -> ImprovementPlan:
    """
    Use a strong model to analyze failures and generate an improvement plan.
    """
    model = cap_map.get(model_name)
    if not model:
        raise ValueError(f"Model {model_name} not found in capability map")

    failures = analyze_failures(cap_map, model_name)

    # Load current system prompt if available
    current_prompt = ""
    if current_profile_path and current_profile_path.exists():
        import yaml
        with open(current_profile_path) as f:
            profile_data = yaml.safe_load(f)
        current_prompt = profile_data.get("system_prompt", "")

    # Build analysis prompt
    analysis_prompt = _build_analysis_prompt(model_name, model, failures, current_prompt)

    # Call analyst model
    profile = find_profile(analyst_model)
    if not profile:
        raise ValueError(f"Analyst model not found: {analyst_model}")

    provider = get_provider(profile.provider, model_id=profile.model_id)

    messages = [
        Message(role="system", content=ANALYST_SYSTEM_PROMPT),
        Message(role="user", content=analysis_prompt),
    ]

    config = ModelConfig(temperature=0.3, max_tokens=4096)
    completion = await provider.complete(messages, tools=[], config=config)

    # Parse the response
    plan = _parse_improvement_plan(model_name, model, failures, completion.content)
    return plan


ANALYST_SYSTEM_PROMPT = """\
You are an expert AI systems engineer specializing in prompt optimization.

You analyze benchmark failure patterns for AI models and recommend specific,
actionable improvements to system prompts and configurations.

Your recommendations should be:
1. Targeted at specific failure patterns (not generic "be better" advice)
2. Concrete — include exact prompt text to add/modify
3. Prioritized — most impactful changes first
4. Testable — each change should be verifiable via re-running the affected benchmarks

Respond in JSON format:
{
  "prompt_changes": [
    {
      "section": "tool_usage|output_format|reasoning|constraints|identity",
      "action": "add|modify|remove|emphasize",
      "content": "exact text to add/modify",
      "rationale": "why this helps",
      "priority": 1
    }
  ],
  "config_changes": {
    "temperature": 0.7
  },
  "target_quality": 0.85,
  "analysis": "brief overall analysis"
}

IMPORTANT constraints on config_changes:
- max_output_tokens must NEVER be set below 8192. Models need sufficient output space.
- Do NOT change: name, provider, model_id, tool_call_format, or cost fields.
- temperature must stay between 0.0 and 1.5.
- When in doubt, leave config values unchanged and focus on prompt improvements.
"""


def _build_analysis_prompt(
    model_name: str,
    model: Any,
    failures: list[FailurePattern],
    current_prompt: str,
) -> str:
    """Build the prompt for the analyst model."""
    parts = [
        f"# Model Performance Analysis: {model_name}",
        "",
        "## Current Performance",
    ]

    for cat_name, cat in model.categories.items():
        completed = sum(1 for ts in cat.task_scores.values() if ts.completion_rate > 0)
        total = len(cat.task_scores)
        parts.append(
            f"- **{cat_name}**: Q={cat.avg_quality:.2f}, "
            f"Completion={completed}/{total}, "
            f"Avg time={cat.avg_time_seconds:.0f}s"
        )

    parts.append("\n## Failure Patterns")
    for f in failures:
        parts.append(
            f"- [{f.severity.upper()}] {f.pattern_type}: {f.details} "
            f"(tasks: {', '.join(f.affected_tasks)})"
        )

    if current_prompt:
        parts.append("\n## Current System Prompt")
        parts.append(f"```\n{current_prompt[:3000]}\n```")

    parts.append(
        "\n## Task: Generate specific prompt improvements to address these failures. "
        "Focus on the critical and major patterns first."
    )

    return "\n".join(parts)


def _parse_improvement_plan(
    model_name: str,
    model: Any,
    failures: list[FailurePattern],
    response: str,
) -> ImprovementPlan:
    """Parse the analyst's response into an ImprovementPlan."""
    try:
        # Extract JSON from response
        text = response.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

        data = json.loads(text)

        prompt_changes = [
            PromptChange(
                section=pc.get("section", "general"),
                action=pc.get("action", "add"),
                content=pc.get("content", ""),
                rationale=pc.get("rationale", ""),
                priority=pc.get("priority", 5),
            )
            for pc in data.get("prompt_changes", [])
        ]

        return ImprovementPlan(
            model_name=model_name,
            current_quality=model.overall_quality,
            target_quality=data.get("target_quality", 0.85),
            failures=failures,
            prompt_changes=prompt_changes,
            config_changes=data.get("config_changes", {}),
        )
    except (json.JSONDecodeError, KeyError) as e:
        # Fallback: return plan with just the failures
        return ImprovementPlan(
            model_name=model_name,
            current_quality=model.overall_quality,
            target_quality=0.85,
            failures=failures,
            prompt_changes=[],
            config_changes={},
        )


# ---------------------------------------------------------------------------
# Guardrails — parameters the improver must never regress below safe minimums.
# These prevent the analyst model from accidentally crippling a profile.
# ---------------------------------------------------------------------------

#: Hard floors for critical profile fields.  The improver may raise these
#: values but may never set them below the floor.
GUARDRAIL_FLOORS: dict[str, int | float] = {
    "max_output_tokens": 8_192,      # was regressed to 3072 → broke MiniMax
    "context_window": 32_000,        # models need reasonable context
    "optimal_temperature": 0.0,      # never negative (should be impossible, but defensive)
}

#: Hard ceilings — prevent runaway values that waste tokens/money.
GUARDRAIL_CEILINGS: dict[str, int | float] = {
    "optimal_temperature": 1.5,      # anything above this is random noise
    "max_output_tokens": 200_000,    # sanity cap
}

#: Fields the analyst model is NOT allowed to change at all.
GUARDRAIL_IMMUTABLE: set[str] = {
    "name",
    "provider",
    "model_id",
    "tool_call_format",
    "cost_per_million_input",
    "cost_per_million_output",
}


def _clamp_config(
    field_name: str,
    proposed: int | float,
    original: int | float,
) -> tuple[int | float, str | None]:
    """
    Apply guardrails to a proposed config value.

    Returns (final_value, warning_or_None).
    """
    final = proposed
    warning = None

    floor = GUARDRAIL_FLOORS.get(field_name)
    if floor is not None and proposed < floor:
        warning = (
            f"Guardrail: {field_name} proposed={proposed} below floor={floor} "
            f"(original={original}). Clamped to floor."
        )
        final = floor

    ceiling = GUARDRAIL_CEILINGS.get(field_name)
    if ceiling is not None and proposed > ceiling:
        warning = (
            f"Guardrail: {field_name} proposed={proposed} above ceiling={ceiling} "
            f"(original={original}). Clamped to ceiling."
        )
        final = ceiling

    # Preserve integer type when the original was int
    if isinstance(original, int) and isinstance(final, float) and final == int(final):
        final = int(final)

    return final, warning


def apply_improvement_plan(
    plan: ImprovementPlan,
    profile_path: Path,
    output_path: Path | None = None,
) -> Path:
    """
    Apply an improvement plan to a model profile.

    Creates a new profile file with the updated system prompt.
    Does NOT overwrite the original — writes to output_path or
    creates a versioned copy.

    Guardrails enforce safe bounds on critical parameters and prevent
    identity fields from being mutated.
    """
    import yaml

    with open(profile_path) as f:
        profile = yaml.safe_load(f)

    current_prompt = profile.get("system_prompt", "")
    guardrail_warnings: list[str] = []

    # Apply prompt changes in priority order
    sorted_changes = sorted(plan.prompt_changes, key=lambda c: c.priority)

    additions = []
    for change in sorted_changes:
        if change.action == "add":
            additions.append(f"\n## {change.section.replace('_', ' ').title()}\n{change.content}")
        elif change.action == "emphasize":
            # Wrap in emphasis markers
            additions.append(f"\n⚠️ IMPORTANT — {change.section}:\n{change.content}")

    if additions:
        improved_prompt = current_prompt + "\n" + "\n".join(additions)
        profile["system_prompt"] = improved_prompt

    # Apply config changes with guardrails
    config_field_map = {
        "temperature": "optimal_temperature",
        "max_tokens": "max_output_tokens",
        "max_output_tokens": "max_output_tokens",
        "context_window": "context_window",
        "top_p": "optimal_top_p",
    }

    for config_key, proposed_value in plan.config_changes.items():
        profile_field = config_field_map.get(config_key, config_key)

        # Block immutable fields
        if profile_field in GUARDRAIL_IMMUTABLE:
            w = f"Guardrail: blocked mutation of immutable field '{profile_field}'"
            guardrail_warnings.append(w)
            continue

        original = profile.get(profile_field, proposed_value)
        final, warning = _clamp_config(profile_field, proposed_value, original)

        if warning:
            guardrail_warnings.append(warning)

        profile[profile_field] = final

    # Log guardrail interventions so we can see them in benchmark output
    if guardrail_warnings:
        profile["_guardrail_warnings"] = guardrail_warnings
        for w in guardrail_warnings:
            print(f"  ⚠️  {w}")

    # Write to output path
    if output_path is None:
        stem = profile_path.stem
        output_path = profile_path.parent / f"{stem}_improved.yaml"

    with open(output_path, "w") as f:
        yaml.dump(profile, f, default_flow_style=False, sort_keys=False)

    return output_path
