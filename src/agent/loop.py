"""
AgentLoop — the main agent execution loop.

1. Build system prompt from profile + tool definitions
2. Send messages to LLM provider
3. Parse response for tool calls
4. Execute tool calls via registry
5. Append tool results to conversation
6. Repeat until stop condition
"""
from __future__ import annotations

import asyncio
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from src.providers.base import (
    CompletionResult,
    LLMProvider,
    Message,
    ModelConfig,
    StreamEvent,
    UsageInfo,
)
from src.profiles.model_profile import ModelProfile
from src.tools_impl.base import ToolContext
from src.tools_impl.registry import ToolRegistry
from .context import build_system_prompt
from .compaction import compact_messages, estimate_tokens


@dataclass
class AgentStats:
    """Statistics for an agent run."""
    turns: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    tool_calls_made: int = 0
    tool_calls_succeeded: int = 0
    elapsed_seconds: float = 0.0


class AgentLoop:
    """
    Core agent loop. Manages conversation, tool execution, and termination.
    """

    def __init__(
        self,
        provider: LLMProvider,
        profile: ModelProfile,
        registry: ToolRegistry,
        workdir: Path | None = None,
        max_turns: int = 10,
        tool_filter: list[str] | None = None,
        stream: bool = True,
        compaction_threshold: int = 50_000,
    ):
        self.provider = provider
        self.profile = profile
        self.registry = registry
        self.workdir = workdir or Path.cwd()
        self.max_turns = max_turns
        self.tool_filter = tool_filter
        self.stream = stream
        self.compaction_threshold = compaction_threshold

        self.messages: list[Message] = []
        self.stats = AgentStats()

    def _build_config(self) -> ModelConfig:
        return ModelConfig(
            temperature=self.profile.optimal_temperature,
            top_p=self.profile.optimal_top_p,
            max_tokens=self.profile.max_output_tokens,
        )

    def _tool_context(self) -> ToolContext:
        return ToolContext(cwd=self.workdir)

    async def run(self, task: str) -> str:
        """Run the agent loop on a task. Returns final assistant response."""
        start_time = time.time()

        # Build system prompt
        tools = self.registry.filter(self.tool_filter)
        system_prompt = build_system_prompt(self.profile, tools, self.workdir)

        self.messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=task),
        ]

        config = self._build_config()
        tool_defs = self.registry.to_tool_defs(self.tool_filter)
        final_response = ""

        for turn in range(self.max_turns):
            self.stats.turns = turn + 1

            # Compact if needed
            self.messages = compact_messages(
                self.messages,
                max_tokens=self.compaction_threshold,
            )

            # Get completion
            if self.stream:
                result = await self._stream_turn(config, tool_defs)
            else:
                result = await self.provider.complete(self.messages, tool_defs, config)

            # Track usage
            self.stats.total_input_tokens += result.usage.input_tokens
            self.stats.total_output_tokens += result.usage.output_tokens
            self.stats.total_cost_usd += self.profile.estimate_cost(
                result.usage.input_tokens, result.usage.output_tokens
            )

            # Add assistant message to conversation
            self.messages.append(
                Message(
                    role="assistant",
                    content=result.content,
                    tool_calls=result.tool_calls if result.tool_calls else None,
                )
            )

            final_response = result.content

            # No tool calls = either done or model stalled
            if not result.tool_calls:
                # If we also got no content, the model may have stalled (e.g. reasoning-only)
                # Give it one nudge to produce output
                if not result.content.strip() and turn < self.max_turns - 1:
                    self.messages.append(
                        Message(
                            role="user",
                            content=(
                                "You didn't produce any output or tool calls. "
                                "Please use the file_edit or file_write tool to make your changes now. "
                                "Do not just describe what to do — call the tool."
                            ),
                        )
                    )
                    continue
                break

            # Execute tool calls
            for tc in result.tool_calls:
                self.stats.tool_calls_made += 1

                # Plan mode: block write tools
                try:
                    from src.tools_impl.plan_tool import is_plan_mode, WRITE_TOOLS
                    if is_plan_mode() and tc.name in WRITE_TOOLS:
                        self.messages.append(
                            Message(
                                role="tool",
                                content=f"⚠️ Blocked in plan mode: {tc.name}. Use exit_plan_mode first.",
                                tool_call_id=tc.id,
                                name=tc.name,
                            )
                        )
                        print(f"\n⚠️ {tc.name} blocked (plan mode)", file=sys.stderr)
                        continue
                except ImportError:
                    pass

                print(f"\n⚡ {tc.name}({_summarize_args(tc.arguments)})", file=sys.stderr)

                tool_result = await self.registry.execute(
                    tc.name, tc.arguments, self._tool_context()
                )

                if tool_result.success:
                    self.stats.tool_calls_succeeded += 1

                # Truncate long tool output
                output = tool_result.to_content()
                if len(output) > 20_000:
                    output = output[:20_000] + "\n... (truncated)"

                self.messages.append(
                    Message(
                        role="tool",
                        content=output,
                        tool_call_id=tc.id,
                        name=tc.name,
                    )
                )

                # Print brief tool result
                status = "✓" if tool_result.success else "✗"
                preview = output[:100].replace("\n", " ")
                print(f"  {status} {preview}", file=sys.stderr)

        self.stats.elapsed_seconds = time.time() - start_time
        return final_response

    async def _stream_turn(
        self, config: ModelConfig, tool_defs: list
    ) -> CompletionResult:
        """Stream a single turn, printing text deltas to stderr."""
        content_parts: list[str] = []
        tool_calls: list = []
        usage = UsageInfo()

        async for event in self.provider.stream(self.messages, tool_defs, config):
            if event.type == "text_delta" and event.text:
                content_parts.append(event.text)
                print(event.text, end="", file=sys.stderr, flush=True)
            elif event.type == "tool_call_delta" and event.tool_call:
                tool_calls.append(event.tool_call)
            elif event.type == "usage" and event.usage:
                usage = event.usage
            elif event.type == "done":
                if event.usage:
                    usage = event.usage
                break
            elif event.type == "error":
                print(f"\nStream error: {event.error}", file=sys.stderr)
                break

        if content_parts:
            print(file=sys.stderr)  # newline after streaming

        content = "".join(content_parts)
        stop_reason = "tool_use" if tool_calls else "stop"

        return CompletionResult(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            stop_reason=stop_reason,
        )


def _summarize_args(args: dict, max_len: int = 80) -> str:
    """Summarize tool arguments for display."""
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
