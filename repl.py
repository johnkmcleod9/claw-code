#!/usr/bin/env python3
"""
Claw Code — Interactive REPL for multi-model coding agent.

Usage:
    python repl.py                          # Start REPL with default model
    python repl.py --model deepseek         # Use specific model
    python repl.py --workdir ~/myproject    # Set working directory
    python repl.py --task "Fix the bug"     # One-shot mode (run and exit)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent))

from src.providers import get_provider
from src.providers.base import Message, ModelConfig, LLMProvider
from src.profiles.loader import load_profile, find_profile
from src.profiles.model_profile import ModelProfile
from src.tools_impl.registry import create_default_registry, ToolRegistry
from src.agent.loop import AgentLoop, AgentStats
from src.agent.context import build_system_prompt
from config import load_config, get_model_config, CONFIG_PATH

# ANSI colors
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    GRAY = "\033[90m"

    @staticmethod
    def disable():
        for attr in dir(C):
            if attr.isupper() and not attr.startswith('_'):
                setattr(C, attr, "")


def print_banner(profile_name: str, model_id: str, workdir: Path):
    print(f"""
{C.CYAN}{C.BOLD}  ╔═══════════════════════════════╗
  ║  🐾 Claw Code v0.1           ║
  ╚═══════════════════════════════╝{C.RESET}
  {C.DIM}Model:{C.RESET}  {C.GREEN}{profile_name}{C.RESET} ({C.DIM}{model_id}{C.RESET})
  {C.DIM}Dir:{C.RESET}    {C.YELLOW}{workdir}{C.RESET}
  {C.DIM}Type /help for commands{C.RESET}
""")


def print_help():
    print(f"""
{C.BOLD}Commands:{C.RESET}
  {C.CYAN}/model <name>{C.RESET}    Switch model (e.g., /model sonnet, /model deepseek)
  {C.CYAN}/models{C.RESET}          List available models
  {C.CYAN}/cost{C.RESET}            Show session cost & token usage
  {C.CYAN}/clear{C.RESET}           Clear conversation history
  {C.CYAN}/compact{C.RESET}         Compact conversation (keep summary)
  {C.CYAN}/approval{C.RESET}        Toggle tool approval mode (on/off)
  {C.CYAN}/plan{C.RESET}            Toggle plan mode (read-only exploration)
  {C.CYAN}/tools{C.RESET}           List all available tools
  {C.CYAN}/workdir <path>{C.RESET}  Change working directory
  {C.CYAN}/help{C.RESET}            Show this help
  {C.CYAN}/quit{C.RESET}            Exit

{C.BOLD}Tips:{C.RESET}
  • Multi-line input: end a line with \\ to continue
  • Press Ctrl+C to cancel current generation
  • Press Ctrl+D or type /quit to exit
  • The agent can use plan mode, worktrees, sub-agents, MCP, and skills
""")


class InteractiveSession:
    """Manages an interactive coding session with conversation persistence."""

    def __init__(
        self,
        config: dict,
        model_name: str,
        workdir: Path,
        approval_mode: bool = True,
        no_color: bool = False,
        max_turns: int = 25,
    ):
        self.config = config
        self.workdir = workdir
        self.approval_mode = approval_mode
        self.max_turns = max_turns
        self.messages: list[Message] = []
        self.total_stats = AgentStats()
        self.turn_count = 0

        if no_color:
            C.disable()

        # Load model
        self._load_model(model_name)

    def _load_model(self, model_name: str):
        """Load a model by name, checking config aliases first."""
        model_cfg = get_model_config(self.config, model_name)

        if model_cfg:
            self.model_name = model_name
            self.provider_name = model_cfg["provider"]
            self.model_id = model_cfg["model_id"]

            # Try to load a YAML profile if one exists
            profile_path = Path(__file__).parent / "profiles" / f"{model_name}.yaml"
            if profile_path.exists():
                self.profile = load_profile(profile_path)
            else:
                # Create a minimal profile from config
                self.profile = ModelProfile(
                    name=model_name,
                    provider=self.provider_name,
                    model_id=self.model_id,
                    context_window=model_cfg.get("context_window", 128000),
                    max_output_tokens=model_cfg.get("max_output_tokens", 8192),
                    cost_per_million_input=model_cfg.get("cost_input", 0.0),
                    cost_per_million_output=model_cfg.get("cost_output", 0.0),
                    optimal_temperature=model_cfg.get("temperature", 0.7),
                    optimal_top_p=model_cfg.get("top_p", 0.95),
                )
        else:
            # Fall back to YAML profile lookup
            profile_path = Path(__file__).parent / "profiles" / f"{model_name}.yaml"
            if profile_path.exists():
                self.profile = load_profile(profile_path)
            else:
                found = find_profile(model_name)
                if found is None:
                    raise ValueError(f"Unknown model: {model_name}")
                self.profile = found

            self.model_name = self.profile.name
            self.provider_name = self.profile.provider
            self.model_id = self.profile.model_id

        # Initialize provider
        self.provider = get_provider(self.provider_name, model_id=self.model_id)

        # Registry
        self.registry = create_default_registry()

    def switch_model(self, model_name: str) -> bool:
        """Switch to a different model, preserving conversation."""
        try:
            self._load_model(model_name)
            # Rebuild system prompt for new model
            if self.messages:
                tools = self.registry.list_tools()
                self.messages[0] = Message(
                    role="system",
                    content=build_system_prompt(self.profile, tools, self.workdir),
                )
            print(f"{C.GREEN}✓ Switched to {self.model_name} ({self.model_id}){C.RESET}")
            return True
        except (ValueError, Exception) as e:
            print(f"{C.RED}✗ Failed to switch: {e}{C.RESET}")
            return False

    def list_models(self):
        """List available models from config and profiles."""
        print(f"\n{C.BOLD}Available models:{C.RESET}")

        # From config
        models = self.config.get("models", {})
        if models:
            print(f"  {C.DIM}From config (~/.claw-code/config.json):{C.RESET}")
            for name, cfg in models.items():
                marker = " ← current" if name == self.model_name else ""
                print(f"    {C.CYAN}{name:<20}{C.RESET} {cfg['provider']}/{cfg['model_id']}{C.GREEN}{marker}{C.RESET}")

        # From YAML profiles
        profiles_dir = Path(__file__).parent / "profiles"
        yamls = sorted(profiles_dir.glob("*.yaml"))
        if yamls:
            print(f"  {C.DIM}From profiles/ directory:{C.RESET}")
            for p in yamls:
                name = p.stem
                if name not in models:
                    marker = " ← current" if name == self.model_name else ""
                    print(f"    {C.CYAN}{name:<20}{C.RESET} (YAML profile){C.GREEN}{marker}{C.RESET}")

        print()

    def show_cost(self):
        """Show session cost and token usage."""
        s = self.total_stats
        print(f"""
{C.BOLD}Session Stats:{C.RESET}
  {C.DIM}Turns:{C.RESET}       {s.turns}
  {C.DIM}Tokens in:{C.RESET}   {s.total_input_tokens:,}
  {C.DIM}Tokens out:{C.RESET}  {s.total_output_tokens:,}
  {C.DIM}Cost:{C.RESET}        ${s.total_cost_usd:.4f}
  {C.DIM}Tool calls:{C.RESET}  {s.tool_calls_made} ({s.tool_calls_succeeded} succeeded)
  {C.DIM}Model:{C.RESET}       {self.model_name} ({self.model_id})
""")

    def clear_conversation(self):
        """Clear conversation history."""
        self.messages = []
        self.turn_count = 0
        print(f"{C.GREEN}✓ Conversation cleared{C.RESET}")

    def change_workdir(self, path_str: str):
        """Change working directory."""
        new_path = Path(path_str).expanduser().resolve()
        if not new_path.is_dir():
            print(f"{C.RED}✗ Not a directory: {new_path}{C.RESET}")
            return
        self.workdir = new_path
        # Rebuild system prompt
        if self.messages:
            tools = self.registry.list_tools()
            self.messages[0] = Message(
                role="system",
                content=build_system_prompt(self.profile, tools, self.workdir),
            )
        print(f"{C.GREEN}✓ Working directory: {self.workdir}{C.RESET}")

    async def run_turn(self, user_input: str) -> str:
        """Run a single conversation turn. Returns assistant response."""
        self.turn_count += 1

        # Build system prompt on first turn
        tools = self.registry.list_tools()
        if not self.messages:
            system_prompt = build_system_prompt(self.profile, tools, self.workdir)
            self.messages.append(Message(role="system", content=system_prompt))

        # Add user message
        self.messages.append(Message(role="user", content=user_input))

        # Create an agent loop for this turn
        loop = AgentLoop(
            provider=self.provider,
            profile=self.profile,
            registry=self.registry,
            workdir=self.workdir,
            max_turns=self.max_turns,
            stream=True,
        )

        # Share our conversation history with the loop
        loop.messages = list(self.messages)

        config = loop._build_config()
        tool_defs = self.registry.to_tool_defs()
        final_response = ""

        for turn in range(self.max_turns):
            loop.stats.turns = turn + 1

            # Compact if needed
            from src.agent.compaction import compact_messages
            loop.messages = compact_messages(
                loop.messages,
                max_tokens=loop.compaction_threshold,
            )

            # Get completion (streaming)
            print(f"\n{C.MAGENTA}─── {self.model_name} ───{C.RESET}")
            result = await loop._stream_turn(config, tool_defs)

            # Track usage
            loop.stats.total_input_tokens += result.usage.input_tokens
            loop.stats.total_output_tokens += result.usage.output_tokens
            loop.stats.total_cost_usd += self.profile.estimate_cost(
                result.usage.input_tokens, result.usage.output_tokens
            )

            # Add assistant message
            loop.messages.append(
                Message(
                    role="assistant",
                    content=result.content,
                    tool_calls=result.tool_calls if result.tool_calls else None,
                )
            )

            final_response = result.content

            # No tool calls = done
            if not result.tool_calls:
                if not result.content.strip() and turn < self.max_turns - 1:
                    loop.messages.append(
                        Message(role="user", content="Please use your tools to complete the task.")
                    )
                    continue
                break

            # Execute tool calls (with approval gates)
            for tc in result.tool_calls:
                loop.stats.tool_calls_made += 1

                # Approval gate for dangerous tools
                if self.approval_mode and tc.name in ("bash", "file_write", "file_edit"):
                    approved = self._prompt_approval(tc)
                    if not approved:
                        loop.messages.append(
                            Message(
                                role="tool",
                                content="⚠️ User denied this tool call.",
                                tool_call_id=tc.id,
                                name=tc.name,
                            )
                        )
                        print(f"  {C.YELLOW}⚠ Skipped (denied){C.RESET}")
                        continue

                print(f"\n{C.CYAN}⚡ {tc.name}{C.RESET}({C.DIM}{_summarize_args(tc.arguments)}{C.RESET})")

                tool_result = await self.registry.execute(
                    tc.name, tc.arguments, loop._tool_context()
                )

                if tool_result.success:
                    loop.stats.tool_calls_succeeded += 1

                output = tool_result.to_content()
                if len(output) > 20_000:
                    output = output[:20_000] + "\n... (truncated)"

                loop.messages.append(
                    Message(
                        role="tool",
                        content=output,
                        tool_call_id=tc.id,
                        name=tc.name,
                    )
                )

                status = f"{C.GREEN}✓{C.RESET}" if tool_result.success else f"{C.RED}✗{C.RESET}"
                preview = output[:120].replace("\n", " ")
                print(f"  {status} {C.DIM}{preview}{C.RESET}")

        # Update our persistent conversation from the loop
        self.messages = loop.messages

        # Accumulate stats
        self.total_stats.turns += loop.stats.turns
        self.total_stats.total_input_tokens += loop.stats.total_input_tokens
        self.total_stats.total_output_tokens += loop.stats.total_output_tokens
        self.total_stats.total_cost_usd += loop.stats.total_cost_usd
        self.total_stats.tool_calls_made += loop.stats.tool_calls_made
        self.total_stats.tool_calls_succeeded += loop.stats.tool_calls_succeeded

        # Show turn cost
        if loop.stats.total_cost_usd > 0:
            print(f"\n{C.DIM}[{loop.stats.total_input_tokens:,} in / {loop.stats.total_output_tokens:,} out | ${loop.stats.total_cost_usd:.4f} | {loop.stats.tool_calls_made} tools]{C.RESET}")

        return final_response

    def _prompt_approval(self, tc) -> bool:
        """Prompt user to approve a tool call."""
        print(f"\n{C.YELLOW}{'─' * 50}")
        print(f"⚠️  Approval required: {C.BOLD}{tc.name}{C.RESET}")

        if tc.name == "bash":
            cmd = tc.arguments.get("command", "")
            print(f"{C.YELLOW}  Command: {C.WHITE}{cmd}{C.RESET}")
        elif tc.name in ("file_write", "file_edit"):
            path = tc.arguments.get("path", tc.arguments.get("file_path", ""))
            print(f"{C.YELLOW}  File: {C.WHITE}{path}{C.RESET}")
            if tc.name == "file_edit":
                old = tc.arguments.get("old_text", "")[:80]
                new = tc.arguments.get("new_text", "")[:80]
                print(f"{C.RED}  - {old}{C.RESET}")
                print(f"{C.GREEN}  + {new}{C.RESET}")

        print(f"{C.YELLOW}{'─' * 50}{C.RESET}")

        try:
            response = input(f"{C.YELLOW}  [Y]es / [n]o / [a]lways: {C.RESET}").strip().lower()
            if response in ("a", "always"):
                self.approval_mode = False
                print(f"{C.GREEN}  ✓ Auto-approve enabled for this session{C.RESET}")
                return True
            return response in ("", "y", "yes")
        except (EOFError, KeyboardInterrupt):
            print()
            return False


def _summarize_args(args: dict, max_len: int = 80) -> str:
    parts = []
    for k, v in args.items():
        val_str = str(v)
        if len(val_str) > 40:
            val_str = val_str[:37] + "..."
        parts.append(f"{k}={val_str}")
    result = ", ".join(parts)
    if len(result) > max_len:
        result = result[:max_len - 3] + "..."
    return result


def read_multiline_input() -> str | None:
    """Read input, supporting multi-line with trailing backslash."""
    try:
        line = input(f"{C.BLUE}{C.BOLD}> {C.RESET}")
    except EOFError:
        return None
    except KeyboardInterrupt:
        print()
        return ""

    lines = [line]
    while lines[-1].endswith("\\"):
        lines[-1] = lines[-1][:-1]  # remove trailing backslash
        try:
            lines.append(input(f"{C.DIM}... {C.RESET}"))
        except (EOFError, KeyboardInterrupt):
            break

    return "\n".join(lines)


async def async_main():
    parser = argparse.ArgumentParser(
        description="Claw Code — Interactive multi-model coding agent",
    )
    parser.add_argument(
        "--model", "-m",
        default=None,
        help="Model name (from config or profiles/). Default: from config",
    )
    parser.add_argument(
        "--workdir", "-w",
        default=".",
        help="Working directory. Default: current directory",
    )
    parser.add_argument(
        "--task", "-t",
        help="One-shot task (run and exit instead of REPL)",
    )
    parser.add_argument(
        "--no-approval",
        action="store_true",
        help="Disable approval gates (auto-approve all tools)",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable color output",
    )
    parser.add_argument(
        "--max-turns",
        type=int, default=25,
        help="Maximum agent turns per interaction. Default: 25",
    )

    args = parser.parse_args()

    # Load config
    config = load_config()
    model_name = args.model or config.get("default_model", "deepseek")
    workdir = Path(args.workdir).expanduser().resolve()

    if not workdir.is_dir():
        print(f"Error: Working directory does not exist: {workdir}", file=sys.stderr)
        sys.exit(1)

    # Create session
    try:
        session = InteractiveSession(
            config=config,
            model_name=model_name,
            workdir=workdir,
            approval_mode=not args.no_approval,
            no_color=args.no_color,
            max_turns=args.max_turns,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        print(f"\nRun with --model <name> or set up ~/.claw-code/config.json", file=sys.stderr)
        sys.exit(1)

    # One-shot mode
    if args.task:
        await session.run_turn(args.task)
        session.show_cost()
        return

    # Interactive REPL
    print_banner(session.model_name, session.model_id, workdir)

    while True:
        user_input = read_multiline_input()

        if user_input is None:
            # EOF (Ctrl+D)
            print(f"\n{C.DIM}Goodbye!{C.RESET}")
            session.show_cost()
            break

        if not user_input.strip():
            continue

        text = user_input.strip()

        # Handle commands
        if text.startswith("/"):
            parts = text.split(None, 1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if cmd in ("/quit", "/exit", "/q"):
                print(f"\n{C.DIM}Goodbye!{C.RESET}")
                session.show_cost()
                break
            elif cmd == "/help":
                print_help()
            elif cmd == "/model":
                if arg:
                    session.switch_model(arg)
                else:
                    print(f"{C.DIM}Current: {session.model_name}. Usage: /model <name>{C.RESET}")
            elif cmd == "/models":
                session.list_models()
            elif cmd == "/cost":
                session.show_cost()
            elif cmd == "/clear":
                session.clear_conversation()
            elif cmd == "/compact":
                if session.messages:
                    from src.agent.compaction import compact_messages
                    before = len(session.messages)
                    session.messages = compact_messages(session.messages, max_tokens=20_000)
                    print(f"{C.GREEN}✓ Compacted {before} → {len(session.messages)} messages{C.RESET}")
                else:
                    print(f"{C.DIM}Nothing to compact{C.RESET}")
            elif cmd == "/approval":
                session.approval_mode = not session.approval_mode
                state = "ON" if session.approval_mode else "OFF"
                print(f"{C.GREEN}✓ Approval mode: {state}{C.RESET}")
            elif cmd == "/workdir":
                if arg:
                    session.change_workdir(arg)
                else:
                    print(f"{C.DIM}Current: {session.workdir}. Usage: /workdir <path>{C.RESET}")
            elif cmd == "/plan":
                from src.tools_impl.plan_tool import _plan_mode, is_plan_mode
                import src.tools_impl.plan_tool as pm
                pm._plan_mode = not pm._plan_mode
                state = "ON (read-only)" if pm._plan_mode else "OFF (full access)"
                print(f"{C.GREEN}✓ Plan mode: {state}{C.RESET}")
            elif cmd == "/tools":
                tools = session.registry.list_tools()
                print(f"\n{C.BOLD}Available tools ({len(tools)}):{C.RESET}")
                for t in tools:
                    print(f"  {C.CYAN}{t.name:<20}{C.RESET} {t.description[:60]}")
                print()
            else:
                print(f"{C.RED}Unknown command: {cmd}. Type /help{C.RESET}")
            continue

        # Run the agent
        try:
            await session.run_turn(text)
        except KeyboardInterrupt:
            print(f"\n{C.YELLOW}⚠ Cancelled{C.RESET}")
        except Exception as e:
            print(f"\n{C.RED}Error: {e}{C.RESET}")
            import traceback
            traceback.print_exc()


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
