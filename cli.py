#!/usr/bin/env python3
"""
Pathwise Adaptive Harness — CLI entry point.

Usage:
    python cli.py "Write hello world to hello.py" --model minimax-m2.7
    python cli.py "Fix the bug in main.py" --profile profiles/sonnet.yaml
    python cli.py "List all Python files" --model qwen-3.5-local --workdir ./src
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent))


def main():
    parser = argparse.ArgumentParser(
        description="Pathwise Adaptive Harness — multi-model coding agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("task", help="Task description for the agent")
    parser.add_argument(
        "--model", "-m",
        default="minimax-m2.7",
        help="Model name (matches a YAML profile in profiles/). Default: minimax-m2.7",
    )
    parser.add_argument(
        "--profile", "-p",
        help="Path to a specific profile YAML file (overrides --model)",
    )
    parser.add_argument(
        "--max-turns", "-t",
        type=int, default=10,
        help="Maximum agent turns. Default: 10",
    )
    parser.add_argument(
        "--tools",
        help="Comma-separated list of tools to enable (default: all)",
    )
    parser.add_argument(
        "--workdir", "-w",
        help="Working directory for the agent. Default: cwd",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Disable streaming (use complete() instead)",
    )

    args = parser.parse_args()

    # Load profile
    from src.profiles.loader import load_profile, find_profile

    if args.profile:
        profile = load_profile(args.profile)
    else:
        profile_path = Path(__file__).parent / "profiles" / f"{args.model}.yaml"
        if profile_path.exists():
            profile = load_profile(profile_path)
        else:
            # Try finding by name
            found = find_profile(args.model)
            if found is None:
                print(f"Error: No profile found for model '{args.model}'", file=sys.stderr)
                print(f"Available profiles in profiles/:", file=sys.stderr)
                for p in sorted(Path(__file__).parent.glob("profiles/*.yaml")):
                    print(f"  - {p.stem}", file=sys.stderr)
                sys.exit(1)
            profile = found

    print(f"🔧 Model: {profile.name} ({profile.provider}/{profile.model_id})", file=sys.stderr)
    print(f"📊 Context: {profile.context_window:,} tokens | Max output: {profile.max_output_tokens:,}", file=sys.stderr)
    print(f"💰 Cost: ${profile.cost_per_million_input}/M in, ${profile.cost_per_million_output}/M out", file=sys.stderr)
    print(f"🔄 Max turns: {args.max_turns}", file=sys.stderr)
    print("─" * 60, file=sys.stderr)

    # Initialize provider
    from src.providers import get_provider

    try:
        provider = get_provider(profile.provider, model_id=profile.model_id)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Set up tool registry
    from src.tools_impl.registry import create_default_registry

    registry = create_default_registry()

    tool_filter = None
    if args.tools:
        tool_filter = [t.strip() for t in args.tools.split(",")]
        unknown = [t for t in tool_filter if registry.get(t) is None]
        if unknown:
            print(f"Warning: Unknown tools: {', '.join(unknown)}", file=sys.stderr)

    print(f"🛠️  Tools: {', '.join(registry.list_names())}", file=sys.stderr)
    print("─" * 60, file=sys.stderr)

    # Set up agent loop
    from src.agent.loop import AgentLoop

    workdir = Path(args.workdir).resolve() if args.workdir else Path.cwd()

    loop = AgentLoop(
        provider=provider,
        profile=profile,
        registry=registry,
        workdir=workdir,
        max_turns=args.max_turns,
        tool_filter=tool_filter,
        stream=not args.no_stream,
    )

    # Run
    try:
        result = asyncio.run(loop.run(args.task))
    except KeyboardInterrupt:
        print("\n\nInterrupted.", file=sys.stderr)
        sys.exit(130)

    # Print final result to stdout
    if result:
        print(result)

    # Report stats
    stats = loop.stats
    print("\n" + "─" * 60, file=sys.stderr)
    print(f"📈 Stats:", file=sys.stderr)
    print(f"   Turns: {stats.turns}", file=sys.stderr)
    print(f"   Tokens: {stats.total_input_tokens:,} in / {stats.total_output_tokens:,} out", file=sys.stderr)
    print(f"   Cost: ${stats.total_cost_usd:.4f}", file=sys.stderr)
    print(f"   Tools: {stats.tool_calls_made} calls ({stats.tool_calls_succeeded} succeeded)", file=sys.stderr)
    print(f"   Time: {stats.elapsed_seconds:.1f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
