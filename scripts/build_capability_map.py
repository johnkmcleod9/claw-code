#!/usr/bin/env python3
"""
Build consolidated capability_map.json from latest benchmark results.

Usage:
    python3 scripts/build_capability_map.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.router.capability_map import CapabilityMap, ModelCapability, CategoryScore, TaskScore

# Map model name → result directories (eng, biz, el)
# Using the latest validated runs for each model.
MODEL_RESULTS = {
    "mercury-2": {
        "provider": "openrouter",
        "model_id": "inception/mercury-coder-small-beta",
        "cost_input": 0.25,
        "cost_output": 1.0,
        "profile": "mercury-2_improved",
        "dirs": {
            "engineering": "results/2026-04-01_0555/mercury-2",
            "business": "results/2026-04-01_0558/mercury-2",
            "elearning": "results/2026-04-01_0600/mercury-2",
        },
    },
    "minimax-m2.7": {
        "provider": "openrouter",
        "model_id": "minimax/minimax-m2.7",
        "cost_input": 0.3,
        "cost_output": 1.1,
        "profile": "minimax-m2.7_improved",
        "dirs": {
            # 0718 has all 20 tasks from the full post-fix re-benchmark
            "engineering": "results/2026-04-01_0718/minimax-m2.7",
            "business": "results/2026-04-01_0718/minimax-m2.7",
            "elearning": "results/2026-04-01_0718/minimax-m2.7",
        },
    },
    "sonnet": {
        "provider": "openrouter",
        "model_id": "anthropic/claude-sonnet-4",
        "cost_input": 3.0,
        "cost_output": 15.0,
        "profile": "sonnet",
        "dirs": {
            "engineering": "results/2026-04-01_0922/sonnet",
            "business": "results/2026-04-01_0934/sonnet",
            "elearning": "results/2026-04-01_0934/sonnet",
        },
    },
}

ROOT = Path(__file__).parent.parent


def load_task_results(results_dir: Path, category: str) -> dict[str, TaskScore]:
    """Load individual task result JSONs from a directory."""
    scores = {}
    if not results_dir.exists():
        print(f"  ⚠️  Missing: {results_dir}", file=sys.stderr)
        return scores

    for f in sorted(results_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError) as e:
            print(f"  ⚠️  Bad JSON: {f}: {e}", file=sys.stderr)
            continue

        task_id = data.get("task_id", f.stem)

        # Skip tasks from wrong category (elearning dir may have both biz and el)
        prefix = task_id.split("-")[0].lower()
        cat_map = {"eng": "engineering", "biz": "business", "el": "elearning"}
        if cat_map.get(prefix) != category:
            continue

        completed = data.get("completed", False)
        quality = data.get("quality_score", 0.0) if completed else 0.0
        adherence = data.get("skill_adherence", 0.0) if completed else 0.0

        succeeded = data.get("tool_calls_succeeded")
        made = data.get("tool_calls_made", 0)
        if succeeded is not None and made > 0:
            tool_success = succeeded / made
        elif made > 0:
            tool_success = 1.0 if completed else 0.0
        else:
            tool_success = 1.0

        scores[task_id] = TaskScore(
            task_id=task_id,
            quality=quality,
            adherence=adherence,
            avg_time_seconds=data.get("time_seconds", 0.0),
            avg_cost_usd=data.get("cost_usd", 0.0),
            completion_rate=1.0 if completed else 0.0,
            tool_success_rate=tool_success,
        )

    return scores


def build_map() -> CapabilityMap:
    cap_map = CapabilityMap()

    for model_name, config in MODEL_RESULTS.items():
        print(f"\n🤖 {model_name}", file=sys.stderr)
        categories: dict[str, CategoryScore] = {}

        for cat_name, rel_dir in config["dirs"].items():
            results_dir = ROOT / rel_dir
            scores = load_task_results(results_dir, cat_name)

            if not scores:
                print(f"  ❌ No results for {cat_name}", file=sys.stderr)
                continue

            n = len(scores)
            score_list = list(scores.values())
            cat = CategoryScore(
                category=cat_name,
                avg_quality=sum(s.quality for s in score_list) / n,
                avg_adherence=sum(s.adherence for s in score_list) / n,
                avg_time_seconds=sum(s.avg_time_seconds for s in score_list) / n,
                avg_cost_usd=sum(s.avg_cost_usd for s in score_list) / n,
                completion_rate=sum(s.completion_rate for s in score_list) / n,
                task_scores=scores,
            )
            categories[cat_name] = cat

            completed = sum(1 for s in score_list if s.completion_rate > 0)
            print(
                f"  ✅ {cat_name}: Q={cat.avg_quality:.2f}, "
                f"{completed}/{n} completed, "
                f"${cat.avg_cost_usd:.4f}/task, "
                f"{cat.avg_time_seconds:.1f}s avg",
                file=sys.stderr,
            )

        cap = ModelCapability(
            model_name=model_name,
            provider=config["provider"],
            cost_per_million_input=config["cost_input"],
            cost_per_million_output=config["cost_output"],
            categories=categories,
        )
        cap_map.register(cap)

    return cap_map


if __name__ == "__main__":
    cap_map = build_map()
    output = ROOT / "capability_map.json"
    cap_map.save(output)
    print(f"\n💾 Saved to {output}", file=sys.stderr)

    # Print summary table
    print("\n# Capability Map Summary\n")
    print(f"| Model | Eng Q | Eng % | Biz Q | Biz % | EL Q | EL % | Overall Q | $/task |")
    print(f"|-------|-------|-------|-------|-------|------|------|-----------|--------|")
    for name, model in cap_map.models.items():
        eng = model.categories.get("engineering")
        biz = model.categories.get("business")
        el = model.categories.get("elearning")
        avg_cost = sum(c.avg_cost_usd for c in model.categories.values()) / max(len(model.categories), 1)
        print(
            f"| {name} | "
            f"{eng.avg_quality:.2f} | {eng.completion_rate*100:.0f}% | "
            f"{biz.avg_quality:.2f} | {biz.completion_rate*100:.0f}% | "
            f"{el.avg_quality:.2f} | {el.completion_rate*100:.0f}% | "
            f"{model.overall_quality:.2f} | ${avg_cost:.4f} |"
        )
