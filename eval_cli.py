#!/usr/bin/env python3
"""
Adaptive Harness — Evaluation CLI.

Usage:
    python eval_cli.py run --suite benchmarks/engineering --model minimax-m2.7
    python eval_cli.py run --suite benchmarks/engineering --all-models
    python eval_cli.py run --suite benchmarks/engineering --model sonnet --judge-model sonnet
    python eval_cli.py report --results results/2026-03-31_1200/
    python eval_cli.py list --suite benchmarks/engineering
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).parent))


def cmd_run(args):
    """Run a benchmark suite against one or more models."""
    from src.eval.suite import BenchmarkSuite, run_suite
    from src.profiles.loader import load_all_profiles

    suite = BenchmarkSuite.from_directory(args.suite)

    # Filter tasks if specified
    if args.tasks:
        task_ids = {t.strip() for t in args.tasks.split(",")}
        suite.tasks = [t for t in suite.tasks if t.id in task_ids]
        if not suite.tasks:
            print(f"Error: no matching tasks for {args.tasks}", file=sys.stderr)
            sys.exit(1)

    # Override timeout if specified
    if args.timeout:
        for task in suite.tasks:
            task.timeout_seconds = args.timeout

    print(f"📦 Suite: {suite.name} ({len(suite)} tasks)", file=sys.stderr)

    # Determine which models to run
    if args.all_models:
        profiles = load_all_profiles()
        models = list(profiles.keys())
        print(f"🤖 Models: {', '.join(models)}", file=sys.stderr)
    elif args.model:
        models = [m.strip() for m in args.model.split(",")]
    else:
        print("Error: specify --model or --all-models", file=sys.stderr)
        sys.exit(1)

    # Custom profile override
    custom_profile_path = Path(args.profile) if args.profile else None

    # Create results directory
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    save_dir = Path(args.output) / timestamp if args.output else Path("results") / timestamp
    save_dir.mkdir(parents=True, exist_ok=True)
    print(f"💾 Results: {save_dir}", file=sys.stderr)

    # Run
    results = asyncio.run(
        run_suite(
            suite,
            models,
            judge_model=args.judge_model,
            save_dir=save_dir,
            stream=args.stream,
            custom_profile_path=custom_profile_path,
        )
    )

    # Generate and save report
    from src.eval.suite import generate_report

    report = generate_report(results)
    report_path = save_dir / "REPORT.md"
    report_path.write_text(report)
    print(f"\n📄 Report saved to: {report_path}", file=sys.stderr)
    print(report)


def cmd_report(args):
    """Generate a report from saved results."""
    from src.eval.suite import load_results, generate_report, generate_capability_matrix

    results_dir = Path(args.results)
    if not results_dir.exists():
        print(f"Error: results directory not found: {results_dir}", file=sys.stderr)
        sys.exit(1)

    results = load_results(results_dir)
    if not results:
        print(f"No results found in {results_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"📊 Loaded {len(results)} results", file=sys.stderr)

    if args.matrix:
        print(generate_capability_matrix(results))
    else:
        report = generate_report(results)
        print(report)

        # Save report
        report_path = results_dir / "REPORT.md"
        report_path.write_text(report)
        print(f"\n📄 Report saved to: {report_path}", file=sys.stderr)


def cmd_list(args):
    """List tasks in a suite."""
    from src.eval.suite import BenchmarkSuite

    suite = BenchmarkSuite.from_directory(args.suite)
    print(f"Suite: {suite.name} ({len(suite)} tasks)\n")
    for task in suite.tasks:
        print(f"  {task.id}")
        print(f"    {task.name}")
        print(f"    Category: {task.category} | Max turns: {task.max_turns} | Timeout: {task.timeout_seconds}s")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Adaptive Harness — Evaluation CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- run ---
    run_parser = subparsers.add_parser("run", help="Run benchmark suite")
    run_parser.add_argument("--suite", "-s", required=True, help="Path to suite directory")
    run_parser.add_argument("--model", "-m", help="Model name(s), comma-separated")
    run_parser.add_argument("--all-models", action="store_true", help="Run against all profiles")
    run_parser.add_argument("--judge-model", "-j", default="sonnet", help="Model for judging (default: sonnet)")
    run_parser.add_argument("--output", "-o", help="Output directory (default: results/)")
    run_parser.add_argument("--stream", action="store_true", help="Stream agent output")
    run_parser.add_argument("--tasks", "-t", help="Filter to specific task IDs, comma-separated")
    run_parser.add_argument("--profile", help="Path to a custom profile YAML (overrides --model profile lookup)")
    run_parser.add_argument("--timeout", type=int, help="Override timeout per task (seconds)")
    run_parser.set_defaults(func=cmd_run)

    # --- report ---
    report_parser = subparsers.add_parser("report", help="Generate report from results")
    report_parser.add_argument("--results", "-r", required=True, help="Results directory")
    report_parser.add_argument("--matrix", action="store_true", help="Show only capability matrix")
    report_parser.set_defaults(func=cmd_report)

    # --- list ---
    list_parser = subparsers.add_parser("list", help="List tasks in a suite")
    list_parser.add_argument("--suite", "-s", required=True, help="Path to suite directory")
    list_parser.set_defaults(func=cmd_list)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
