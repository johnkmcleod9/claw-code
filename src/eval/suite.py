"""
Benchmark suite management — load tasks from YAML, run suites, generate reports.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean, stdev

import yaml

from src.profiles.loader import load_all_profiles, find_profile
from src.tools_impl.registry import create_default_registry

from .models import TaskSpec, TaskResult
from .runner import run_task
from .judge import judge_result, JudgeResult


class BenchmarkSuite:
    """A collection of benchmark tasks loaded from YAML files."""

    def __init__(self, name: str, tasks: list[TaskSpec]):
        self.name = name
        self.tasks = tasks

    @classmethod
    def from_directory(cls, directory: str | Path) -> BenchmarkSuite:
        """Load all TaskSpec YAML files from a directory."""
        directory = Path(directory)
        if not directory.exists():
            raise FileNotFoundError(f"Suite directory not found: {directory}")

        tasks: list[TaskSpec] = []
        for yaml_file in sorted(directory.glob("*.yaml")):
            try:
                with open(yaml_file) as f:
                    data = yaml.safe_load(f)
                tasks.append(TaskSpec.from_dict(data))
            except Exception as e:
                print(f"Warning: Failed to load task {yaml_file.name}: {e}", file=sys.stderr)

        if not tasks:
            raise ValueError(f"No valid task specs found in {directory}")

        return cls(name=directory.name, tasks=tasks)

    def filter_by_category(self, category: str) -> list[TaskSpec]:
        return [t for t in self.tasks if t.category == category]

    def __len__(self) -> int:
        return len(self.tasks)

    def __repr__(self) -> str:
        return f"BenchmarkSuite(name={self.name!r}, tasks={len(self.tasks)})"


async def run_suite(
    suite: BenchmarkSuite,
    models: list[str],
    *,
    judge_model: str = "sonnet",
    save_dir: str | Path | None = None,
    stream: bool = False,
    custom_profile_path: Path | None = None,
) -> list[TaskResult]:
    """
    Run all tasks in a suite against all specified models.

    Args:
        suite: The benchmark suite to run
        models: List of model profile names
        judge_model: Model to use for quality evaluation
        save_dir: Directory to save individual results (optional)
        stream: Whether to stream agent output

    Returns:
        List of all TaskResults
    """
    all_profiles = load_all_profiles()
    registry = create_default_registry()
    results: list[TaskResult] = []

    for model_name in models:
        if custom_profile_path:
            from src.profiles.loader import load_profile
            profile = load_profile(custom_profile_path)
        else:
            profile = all_profiles.get(model_name)
            if profile is None:
                profile = find_profile(model_name)
        if profile is None:
            print(f"⚠️  Skipping unknown model: {model_name}", file=sys.stderr)
            continue

        print(f"\n{'═' * 60}", file=sys.stderr)
        print(f"🤖 Model: {profile.name} ({profile.provider}/{profile.model_id})", file=sys.stderr)
        print(f"{'═' * 60}", file=sys.stderr)

        for i, task in enumerate(suite.tasks, 1):
            print(f"\n  [{i}/{len(suite)}] {task.id}: {task.name}", file=sys.stderr)

            # Per-task profile selection: try category-specific variant first
            from src.profiles.loader import find_profile_for_category
            from pathlib import Path
            task_profile = profile  # default
            if not custom_profile_path:
                profiles_dir = Path(__file__).parent.parent.parent / "profiles"
                cat_profile_path = profiles_dir / f"{model_name}_{task.category}.yaml"
                if cat_profile_path.exists():
                    alt = find_profile_for_category(model_name, task.category)
                    if alt is not None:
                        # Compare system prompt content to detect a genuinely different profile
                        if alt.system_prompt != profile.system_prompt:
                            task_profile = alt
                            print(f"  📎 {task.category}-specific profile active", file=sys.stderr)
                        else:
                            print(f"  📎 {task.category}-specific profile exists (same content)", file=sys.stderr)

            # Run the task
            try:
                result = await run_task(task, task_profile, registry, stream=stream)
            except Exception as e:
                print(f"  ❌ Task crashed: {e}", file=sys.stderr)
                result = TaskResult(
                    task_id=task.id,
                    model=profile.name,
                    completed=False,
                    tool_calls_made=0,
                    tool_call_success_rate=0.0,
                    turns_used=0,
                    tokens_input=0,
                    tokens_output=0,
                    cost_usd=0.0,
                    time_seconds=0.0,
                    failure_analysis=f"Runner exception: {e}",
                )

            # Judge the result
            if result.completed:
                try:
                    judge = await judge_result(task, result, judge_model=judge_model)
                    result.quality_score = judge.quality_score
                    result.skill_adherence = judge.skill_adherence
                    result.judge_explanation = judge.explanation
                    print(f"  📊 Quality: {judge.quality_score:.2f} | Adherence: {judge.skill_adherence:.2f}", file=sys.stderr)
                except Exception as e:
                    print(f"  ⚠️  Judge failed: {e}", file=sys.stderr)
                    result.judge_explanation = f"Judge error: {e}"
            else:
                print(f"  ❌ Did not complete: {result.failure_analysis}", file=sys.stderr)

            results.append(result)

            # Save individual result
            if save_dir:
                _save_result(result, save_dir)

            # Status line
            status = "✓" if result.completed else "✗"
            cost_str = f"${result.cost_usd:.4f}"
            print(f"  {status} {result.time_seconds:.1f}s | {cost_str} | {result.turns_used} turns", file=sys.stderr)

    return results


def _save_result(result: TaskResult, save_dir: str | Path) -> Path:
    """Save a single result to disk."""
    save_dir = Path(save_dir)
    model_dir = save_dir / result.model
    model_dir.mkdir(parents=True, exist_ok=True)

    filepath = model_dir / f"{result.task_id}.json"
    filepath.write_text(result.to_json())
    return filepath


def load_results(results_dir: str | Path) -> list[TaskResult]:
    """Load all TaskResults from a results directory."""
    results_dir = Path(results_dir)
    results: list[TaskResult] = []
    for json_file in sorted(results_dir.rglob("*.json")):
        try:
            results.append(TaskResult.from_json(json_file.read_text()))
        except Exception as e:
            print(f"Warning: Failed to load {json_file}: {e}", file=sys.stderr)
    return results


def generate_capability_matrix(results: list[TaskResult]) -> str:
    """
    Generate a markdown table showing per-task scores for each model.

    Columns: Task ID | Model1 | Model2 | ...
    Cells: quality_score (colored by range)
    """
    if not results:
        return "No results to display."

    # Organize by task and model
    models = sorted(set(r.model for r in results))
    task_ids = sorted(set(r.task_id for r in results))

    scores: dict[tuple[str, str], TaskResult] = {}
    for r in results:
        scores[(r.task_id, r.model)] = r

    # Build table
    lines = []
    header = "| Task |" + " | ".join(f" {m} " for m in models) + " |"
    separator = "|------|" + " | ".join("------" for _ in models) + " |"
    lines.append(header)
    lines.append(separator)

    for tid in task_ids:
        row = f"| {tid} |"
        for model in models:
            r = scores.get((tid, model))
            if r is None:
                row += " — |"
            elif not r.completed:
                row += " ❌ |"
            else:
                score = r.quality_score
                emoji = "🟢" if score >= 0.8 else "🟡" if score >= 0.5 else "🔴"
                row += f" {emoji} {score:.2f} |"
        lines.append(row)

    # Averages row
    avg_row = "| **Average** |"
    for model in models:
        model_results = [r for r in results if r.model == model and r.completed]
        if model_results:
            avg = mean(r.quality_score for r in model_results)
            avg_row += f" **{avg:.2f}** |"
        else:
            avg_row += " — |"
    lines.append(avg_row)

    return "\n".join(lines)


def generate_report(results: list[TaskResult]) -> str:
    """Generate a full evaluation report with statistics."""
    if not results:
        return "No results to report."

    models = sorted(set(r.model for r in results))
    lines = [
        "# Adaptive Harness — Evaluation Report",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Tasks:** {len(set(r.task_id for r in results))}",
        f"**Models:** {', '.join(models)}",
        "",
        "## Capability Matrix",
        "",
        generate_capability_matrix(results),
        "",
    ]

    # Per-model summary
    lines.append("## Model Summaries")
    for model in models:
        mr = [r for r in results if r.model == model]
        completed = [r for r in mr if r.completed]
        lines.append(f"\n### {model}")
        lines.append(f"- **Tasks run:** {len(mr)}")
        lines.append(f"- **Completed:** {len(completed)}/{len(mr)} ({len(completed)/len(mr)*100:.0f}%)")

        if completed:
            q_scores = [r.quality_score for r in completed]
            s_scores = [r.skill_adherence for r in completed]
            costs = [r.cost_usd for r in completed]
            times = [r.time_seconds for r in completed]

            lines.append(f"- **Quality:** avg {mean(q_scores):.2f}" + (f" (σ={stdev(q_scores):.2f})" if len(q_scores) > 1 else ""))
            lines.append(f"- **Skill adherence:** avg {mean(s_scores):.2f}")
            lines.append(f"- **Total cost:** ${sum(costs):.4f} (avg ${mean(costs):.4f}/task)")
            lines.append(f"- **Total time:** {sum(times):.1f}s (avg {mean(times):.1f}s/task)")
            lines.append(f"- **Total tokens:** {sum(r.tokens_input for r in completed):,} in / {sum(r.tokens_output for r in completed):,} out")

            # Tool usage
            total_tc = sum(r.tool_calls_made for r in completed)
            if total_tc > 0:
                avg_rate = mean(r.tool_call_success_rate for r in completed)
                lines.append(f"- **Tool calls:** {total_tc} total ({avg_rate:.0%} avg success)")

        # Failures
        failed = [r for r in mr if not r.completed]
        if failed:
            lines.append(f"\n**Failures ({len(failed)}):**")
            for r in failed:
                lines.append(f"- `{r.task_id}`: {r.failure_analysis or 'Unknown'}")

    # Cost comparison
    if len(models) > 1:
        lines.append("\n## Cost Comparison")
        for model in models:
            mr = [r for r in results if r.model == model and r.completed]
            if mr:
                total = sum(r.cost_usd for r in mr)
                avg_q = mean(r.quality_score for r in mr)
                # Cost-effectiveness: quality per dollar
                if total > 0:
                    efficiency = avg_q / total
                    lines.append(f"- **{model}:** ${total:.4f} total | {avg_q:.2f} avg quality | {efficiency:.1f} quality/$ efficiency")
                else:
                    lines.append(f"- **{model}:** $0.0000 total | {avg_q:.2f} avg quality")

    return "\n".join(lines)
