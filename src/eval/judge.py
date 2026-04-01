"""
LLM-based quality evaluation — sends task + result to a strong model for scoring.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from src.profiles.loader import find_profile, load_profile
from src.providers import get_provider
from src.providers.base import Message, ModelConfig

from .models import TaskSpec, TaskResult


@dataclass
class JudgeResult:
    """Result from the LLM judge."""
    quality_score: float       # 0.0-1.0
    skill_adherence: float     # 0.0-1.0
    explanation: str


JUDGE_SYSTEM_PROMPT = """\
You are an expert code reviewer and evaluator. You will be given:

1. A TASK SPECIFICATION describing what the model was asked to do
2. A SCORING RUBRIC defining how to evaluate the result
3. The OUTPUT FILES produced by the model
4. The model's TOOL USAGE statistics

Your job is to score the result on two dimensions:

- **quality_score** (0.0-1.0): How well does the output satisfy the task? Use the rubric.
- **skill_adherence** (0.0-1.0): How well did the model use its tools? Did it read before editing? \
Did it verify its work? Was it efficient?

Respond with ONLY a JSON object (no markdown fences):
{
  "quality_score": <float 0.0-1.0>,
  "skill_adherence": <float 0.0-1.0>,
  "explanation": "<brief explanation of scores>"
}
"""


def _build_judge_prompt(task: TaskSpec, result: TaskResult) -> str:
    """Build the evaluation prompt for the judge model."""
    parts = [
        "## TASK SPECIFICATION",
        f"**ID:** {task.id}",
        f"**Name:** {task.name}",
        f"**Description:** {task.description}",
        "",
        "### Prompt Given to Model",
        task.prompt,
        "",
        "## SCORING RUBRIC",
        task.scoring_rubric,
        "",
        "## MODEL OUTPUT",
        f"**Completed:** {result.completed}",
        f"**Turns used:** {result.turns_used}",
        f"**Tool calls:** {result.tool_calls_made} ({result.tool_call_success_rate:.0%} success)",
        f"**Time:** {result.time_seconds:.1f}s",
        "",
    ]

    if result.failure_analysis:
        parts.append(f"**Failure:** {result.failure_analysis}")
        parts.append("")

    if result.output_files:
        parts.append("### Output Files")
        for filename, content in result.output_files.items():
            # Truncate very large files for the judge
            display = content if len(content) <= 8000 else content[:8000] + "\n... (truncated)"
            parts.append(f"\n**{filename}:**")
            parts.append(f"```\n{display}\n```")
    else:
        parts.append("### Output Files\n*No output files produced.*")

    if task.expected_outputs:
        parts.append("\n## EXPECTED OUTPUTS (for reference)")
        for filename, content in task.expected_outputs.items():
            display = content if len(content) <= 4000 else content[:4000] + "\n... (truncated)"
            parts.append(f"\n**{filename}:**")
            parts.append(f"```\n{display}\n```")

    return "\n".join(parts)


async def judge_result(
    task: TaskSpec,
    result: TaskResult,
    judge_model: str = "sonnet",
) -> JudgeResult:
    """
    Evaluate a task result using a strong LLM as judge.

    Args:
        task: The task specification with rubric
        result: The task result to evaluate
        judge_model: Name of the judge model profile (default: sonnet)

    Returns:
        JudgeResult with quality_score, skill_adherence, and explanation
    """
    # Load judge profile
    profile = find_profile(judge_model)
    if profile is None:
        # Try as a direct profile path
        from pathlib import Path
        profile_path = Path(__file__).parent.parent.parent / "profiles" / f"{judge_model}.yaml"
        if profile_path.exists():
            profile = load_profile(profile_path)
        else:
            raise ValueError(f"Judge model profile not found: {judge_model}")

    provider = get_provider(profile.provider, model_id=profile.model_id)

    messages = [
        Message(role="system", content=JUDGE_SYSTEM_PROMPT),
        Message(role="user", content=_build_judge_prompt(task, result)),
    ]

    config = ModelConfig(
        temperature=0.2,  # Low temperature for consistent evaluation
        max_tokens=2048,
    )

    completion = await provider.complete(messages, tools=[], config=config)

    # Parse JSON response
    try:
        # Try to extract JSON from the response
        text = completion.content.strip()
        # Handle possible markdown fences
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

        data = json.loads(text)
        return JudgeResult(
            quality_score=max(0.0, min(1.0, float(data.get("quality_score", 0.0)))),
            skill_adherence=max(0.0, min(1.0, float(data.get("skill_adherence", 0.0)))),
            explanation=data.get("explanation", "No explanation provided"),
        )
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        # Fallback: if we can't parse, return a zero score with the raw response
        return JudgeResult(
            quality_score=0.0,
            skill_adherence=0.0,
            explanation=f"Failed to parse judge response: {e}\nRaw: {completion.content[:500]}",
        )


QUICK_JUDGE_PROMPT = """\
You are evaluating an AI agent's work output. Score it quickly.

## TASK
{task}

## AGENT OUTPUT
{response}

Rate the output on two dimensions:
- **quality_score** (0.0-1.0): Did the agent accomplish the task? Is the output correct and useful?
- **skill_adherence** (0.0-1.0): Did the agent use tools effectively (read files, write changes, verify)?

Respond with ONLY a JSON object (no markdown fences):
{{"quality_score": <float>, "skill_adherence": <float>, "explanation": "<brief>"}}
"""


async def quick_judge(
    task_description: str,
    agent_response: str,
    judge_model: str = "sonnet",
) -> JudgeResult:
    """
    Quick quality check — lighter than full judge_result.
    Used by the cascade runner for escalation decisions.
    """
    profile = find_profile(judge_model)
    if profile is None:
        raise ValueError(f"Judge model profile not found: {judge_model}")

    provider = get_provider(profile.provider, model_id=profile.model_id)

    # Truncate response to avoid blowing up context
    truncated = agent_response[:6000] if len(agent_response) > 6000 else agent_response

    prompt = QUICK_JUDGE_PROMPT.format(task=task_description, response=truncated)

    messages = [
        Message(role="user", content=prompt),
    ]

    config = ModelConfig(temperature=0.2, max_tokens=1024)
    completion = await provider.complete(messages, tools=[], config=config)

    try:
        text = completion.content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        data = json.loads(text)
        return JudgeResult(
            quality_score=max(0.0, min(1.0, float(data.get("quality_score", 0.0)))),
            skill_adherence=max(0.0, min(1.0, float(data.get("skill_adherence", 0.0)))),
            explanation=data.get("explanation", ""),
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        return JudgeResult(quality_score=0.5, skill_adherence=0.5, explanation="Judge parse failed")
