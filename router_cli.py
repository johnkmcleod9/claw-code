#!/usr/bin/env python3
"""
Router CLI — build capability map from eval results and demonstrate routing.

Usage:
    python3 router_cli.py build          # Build capability map from all results
    python3 router_cli.py route <category> [--strategy balanced] [--min-quality 0.7]
    python3 router_cli.py compare        # Show full comparison matrix
    python3 router_cli.py cascade <task> <category> [--workdir .] [--threshold 0.75]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from src.router.capability_map import CapabilityMap
from src.router.strategy import RoutingStrategy, route_task, route_multi


RESULTS_DIRS = [
    # Mercury results
    "results/mercury-run",
    "results/biz-mercury",
    "results/el-mercury",
    # MiniMax results
    "results/2026-03-31_fixed",
    "results/biz-minimax",
    "results/el-minimax",
]

CAP_MAP_PATH = Path("capability_map.json")


def cmd_build(args: argparse.Namespace) -> None:
    """Build capability map from all eval results."""
    cap_map = CapabilityMap()

    for results_base in RESULTS_DIRS:
        base = Path(results_base)
        if not base.exists():
            continue

        # Find the timestamped subdirectory
        for subdir in base.iterdir():
            if subdir.is_dir():
                sub_map = CapabilityMap.from_eval_results(subdir)
                # Merge into main map
                for name, model in sub_map.models.items():
                    existing = cap_map.get(name)
                    if existing:
                        # Merge categories
                        for cat_name, cat in model.categories.items():
                            existing.categories[cat_name] = cat
                    else:
                        cap_map.register(model)

    # Enrich with cost data from profiles
    _enrich_costs(cap_map)

    cap_map.save(CAP_MAP_PATH)
    print(f"✅ Built capability map: {CAP_MAP_PATH}")
    print(f"   Models: {len(cap_map.models)}")
    for name, model in cap_map.models.items():
        cats = ", ".join(model.categories.keys())
        print(f"   - {name}: {cats} (overall quality: {model.overall_quality:.2f})")


def cmd_route(args: argparse.Namespace) -> None:
    """Route a task to the best model."""
    if not CAP_MAP_PATH.exists():
        print("❌ No capability map. Run: python3 router_cli.py build")
        sys.exit(1)

    cap_map = CapabilityMap.load(CAP_MAP_PATH)
    strategy = RoutingStrategy(args.strategy)

    decision = route_task(
        cap_map,
        category=args.category,
        strategy=strategy,
        min_quality=args.min_quality,
    )

    if decision is None:
        print(f"❌ No model meets quality {args.min_quality} for '{args.category}'")
        sys.exit(1)

    print(f"\n🎯 Routing Decision")
    print(f"   Category:  {decision.category}")
    print(f"   Strategy:  {decision.strategy.value}")
    print(f"   Model:     {decision.model_name}")
    print(f"   Quality:   {decision.expected_quality:.2f}")
    print(f"   Speed:     {decision.expected_time:.1f}s avg")
    print(f"   Cost:      ${decision.expected_cost:.4f}/task")
    print(f"   Reason:    {decision.reason}")
    if decision.fallback:
        print(f"   Fallback:  {decision.fallback}")


def cmd_compare(args: argparse.Namespace) -> None:
    """Show full comparison matrix."""
    if not CAP_MAP_PATH.exists():
        print("❌ No capability map. Run: python3 router_cli.py build")
        sys.exit(1)

    cap_map = CapabilityMap.load(CAP_MAP_PATH)
    categories = set()
    for model in cap_map.models.values():
        categories.update(model.categories.keys())
    categories = sorted(categories)

    # Header
    model_names = sorted(cap_map.models.keys())
    header = f"{'Category':<15}"
    for name in model_names:
        header += f" | {name:<20}"
    print(header)
    print("-" * len(header))

    # Quality rows
    for cat in categories:
        row = f"{cat:<15}"
        for name in model_names:
            model = cap_map.models[name]
            if cat in model.categories:
                c = model.categories[cat]
                emoji = "🟢" if c.avg_quality >= 0.85 else "🟡" if c.avg_quality >= 0.7 else "🔴"
                row += f" | {emoji} Q={c.avg_quality:.2f} {c.avg_time_seconds:.0f}s  "
            else:
                row += f" | {'—':^20}"
        print(row)

    print()

    # Routing recommendations
    print("📋 Routing Recommendations:")
    for cat in categories:
        for strategy in [RoutingStrategy.CHEAPEST, RoutingStrategy.FASTEST, RoutingStrategy.QUALITY, RoutingStrategy.BALANCED]:
            decision = route_task(cap_map, cat, strategy, min_quality=0.7)
            if decision:
                print(f"   {cat:>12} [{strategy.value:>8}] → {decision.model_name} "
                      f"(Q={decision.expected_quality:.2f}, ${decision.expected_cost:.4f})")


def cmd_cascade(args: argparse.Namespace) -> None:
    """Run a task with cascade escalation."""
    if not CAP_MAP_PATH.exists():
        print("❌ No capability map. Run: python3 router_cli.py build")
        sys.exit(1)

    from src.tools_impl import create_default_registry
    from src.router.cascade import CascadeRunner

    cap_map = CapabilityMap.load(CAP_MAP_PATH)
    registry = create_default_registry()

    runner = CascadeRunner(
        cap_map=cap_map,
        registry=registry,
        quality_threshold=args.threshold,
    )

    result = asyncio.run(runner.run(
        task=args.task,
        category=args.category,
        workdir=Path(args.workdir),
    ))

    print(f"\n{'='*60}")
    print(f"📊 Cascade Result")
    print(f"{'='*60}")
    print(f"   Task:       {result.task[:80]}")
    print(f"   Category:   {result.category}")
    print(f"   Attempts:   {len(result.attempts)}")
    print(f"   Escalated:  {'Yes' if result.escalated else 'No'}")
    print(f"   Quality:    {result.final_quality:.2f}")
    print(f"   Total cost: ${result.total_cost:.4f}")
    print(f"   Total time: {result.total_time:.1f}s")

    for i, attempt in enumerate(result.attempts):
        status = "✅" if attempt.quality_score >= args.threshold else "⚠️"
        print(f"\n   Attempt {i+1}: {attempt.model_name}")
        print(f"     {status} Quality: {attempt.quality_score:.2f}")
        print(f"     Cost: ${attempt.cost_usd:.4f} | Time: {attempt.time_seconds:.1f}s")
        if attempt.escalation_reason:
            print(f"     Escalation: {attempt.escalation_reason}")


def _enrich_costs(cap_map: CapabilityMap) -> None:
    """Enrich model capabilities with cost data from profiles."""
    from src.profiles.loader import find_profile
    for name, model in cap_map.models.items():
        profile = find_profile(name)
        if profile:
            model.cost_per_million_input = profile.cost_per_million_input
            model.cost_per_million_output = profile.cost_per_million_output
            model.provider = profile.provider


def main() -> None:
    parser = argparse.ArgumentParser(description="Task Router CLI")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("build", help="Build capability map from eval results")

    route_p = sub.add_parser("route", help="Route a task category")
    route_p.add_argument("category", help="Task category (engineering, business, elearning)")
    route_p.add_argument("--strategy", default="balanced",
                        choices=["cheapest", "fastest", "quality", "balanced"])
    route_p.add_argument("--min-quality", type=float, default=0.7)

    sub.add_parser("compare", help="Show comparison matrix")

    cascade_p = sub.add_parser("cascade", help="Run task with escalation")
    cascade_p.add_argument("task", help="Task description")
    cascade_p.add_argument("category", help="Task category")
    cascade_p.add_argument("--workdir", default=".")
    cascade_p.add_argument("--threshold", type=float, default=0.75)

    analyze_p = sub.add_parser("analyze", help="Analyze failure patterns for a model")
    analyze_p.add_argument("model", help="Model name (mercury-2, minimax-m2.7)")

    improve_p = sub.add_parser("improve", help="Generate improvement plan using analyst model")
    improve_p.add_argument("model", help="Model name to improve")
    improve_p.add_argument("--analyst", default="sonnet", help="Analyst model to use")
    improve_p.add_argument("--profile", help="Path to current model profile YAML")
    improve_p.add_argument("--apply", action="store_true", help="Apply changes to profile")

    args = parser.parse_args()

    if args.command == "build":
        cmd_build(args)
    elif args.command == "route":
        cmd_route(args)
    elif args.command == "compare":
        cmd_compare(args)
    elif args.command == "cascade":
        cmd_cascade(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "improve":
        cmd_improve(args)
    else:
        parser.print_help()


def cmd_analyze(args: argparse.Namespace) -> None:
    """Analyze failure patterns for a model."""
    if not CAP_MAP_PATH.exists():
        print("❌ No capability map. Run: python3 router_cli.py build")
        sys.exit(1)

    from src.router.improver import analyze_failures

    cap_map = CapabilityMap.load(CAP_MAP_PATH)
    patterns = analyze_failures(cap_map, args.model)

    if not patterns:
        print(f"✅ No failure patterns found for {args.model}")
        return

    print(f"\n🔍 Failure Analysis: {args.model}")
    print(f"{'='*60}")

    for i, p in enumerate(patterns, 1):
        icon = {"critical": "🔴", "major": "🟡", "minor": "⚪"}[p.severity]
        print(f"\n  {icon} [{p.severity.upper()}] {p.pattern_type}")
        print(f"     Category: {p.category}")
        print(f"     Tasks: {', '.join(p.affected_tasks)}")
        print(f"     Frequency: {p.frequency:.0%}")
        print(f"     Details: {p.details}")


def cmd_improve(args: argparse.Namespace) -> None:
    """Generate improvement plan using analyst model."""
    if not CAP_MAP_PATH.exists():
        print("❌ No capability map. Run: python3 router_cli.py build")
        sys.exit(1)

    from src.router.improver import generate_improvement_plan, apply_improvement_plan

    cap_map = CapabilityMap.load(CAP_MAP_PATH)
    profile_path = Path(args.profile) if args.profile else None

    plan = asyncio.run(generate_improvement_plan(
        cap_map, args.model,
        current_profile_path=profile_path,
        analyst_model=args.analyst,
    ))

    print(f"\n📋 Improvement Plan: {plan.model_name}")
    print(f"{'='*60}")
    print(f"   Current quality: {plan.current_quality:.2f}")
    print(f"   Target quality:  {plan.target_quality:.2f}")
    print(f"   Failures found:  {len(plan.failures)}")
    print(f"   Prompt changes:  {len(plan.prompt_changes)}")

    for i, change in enumerate(sorted(plan.prompt_changes, key=lambda c: c.priority), 1):
        print(f"\n   Change {i} (P{change.priority}): [{change.action}] {change.section}")
        print(f"   Rationale: {change.rationale}")
        # Show first 200 chars of content
        preview = change.content[:200] + "..." if len(change.content) > 200 else change.content
        print(f"   Content: {preview}")

    if plan.config_changes:
        print(f"\n   Config changes: {plan.config_changes}")

    if args.apply and profile_path:
        output = apply_improvement_plan(plan, profile_path)
        print(f"\n   ✅ Applied to: {output}")


if __name__ == "__main__":
    main()
