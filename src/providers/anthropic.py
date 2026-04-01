"""
Anthropic provider — direct API access for Claude models.
Uses the anthropic Python SDK. Supports tool_use blocks in responses.
API key: ANTHROPIC_API_KEY env var.
"""
from __future__ import annotations

import json
import os
from typing import AsyncIterator

from .base import (
    CompletionResult,
    Message,
    ModelConfig,
    StreamEvent,
    ToolCall,
    ToolDef,
    UsageInfo,
)


def _messages_to_anthropic(messages: list[Message]) -> tuple[str | None, list[dict]]:
    """Convert messages. Extract system prompt; format rest for Anthropic API."""
    system_prompt: str | None = None
    result: list[dict] = []

    for msg in messages:
        if msg.role == "system":
            # Anthropic uses top-level system param
            system_prompt = msg.content if isinstance(msg.content, str) else json.dumps(msg.content)
            continue

        if msg.role == "tool":
            # Anthropic expects tool_result content blocks
            result.append({
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id or "",
                        "content": msg.content if isinstance(msg.content, str) else json.dumps(msg.content),
                    }
                ],
            })
            continue

        if msg.role == "assistant" and msg.tool_calls:
            # Assistant message with tool_use blocks
            content_blocks: list[dict] = []
            if msg.content:
                text = msg.content if isinstance(msg.content, str) else json.dumps(msg.content)
                if text.strip():
                    content_blocks.append({"type": "text", "text": text})
            for tc in msg.tool_calls:
                content_blocks.append({
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.name,
                    "input": tc.arguments,
                })
            result.append({"role": "assistant", "content": content_blocks})
            continue

        # Regular user or assistant message
        d: dict = {"role": msg.role}
        if isinstance(msg.content, str):
            d["content"] = msg.content
        else:
            d["content"] = msg.content
        result.append(d)

    return system_prompt, result


def _tools_to_anthropic(tools: list[ToolDef]) -> list[dict]:
    return [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.parameters,
        }
        for t in tools
    ]


class AnthropicProvider:
    """Direct Anthropic API provider for Claude models."""

    def __init__(self, model_id: str = "claude-sonnet-4-20250514", api_key: str | None = None):
        try:
            import anthropic
        except ImportError:
            raise ImportError("anthropic package required: pip install anthropic")

        self.model_id = model_id
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self._client = anthropic.AsyncAnthropic(api_key=self.api_key)

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDef],
        config: ModelConfig,
    ) -> CompletionResult:
        system_prompt, api_messages = _messages_to_anthropic(messages)

        kwargs: dict = {
            "model": self.model_id,
            "messages": api_messages,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "top_p": config.top_p,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            kwargs["tools"] = _tools_to_anthropic(tools)
            if config.tool_choice != "auto":
                kwargs["tool_choice"] = {"type": config.tool_choice}

        response = await self._client.messages.create(**kwargs)

        # Parse response
        content_text = ""
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input if isinstance(block.input, dict) else {},
                    )
                )

        usage = UsageInfo(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
        )

        stop_reason = response.stop_reason or "stop"
        if stop_reason == "end_turn":
            stop_reason = "stop"
        elif stop_reason == "tool_use":
            stop_reason = "tool_use"

        return CompletionResult(
            content=content_text,
            tool_calls=tool_calls,
            usage=usage,
            stop_reason=stop_reason,
        )

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDef],
        config: ModelConfig,
    ) -> AsyncIterator[StreamEvent]:
        system_prompt, api_messages = _messages_to_anthropic(messages)

        kwargs: dict = {
            "model": self.model_id,
            "messages": api_messages,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "top_p": config.top_p,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            kwargs["tools"] = _tools_to_anthropic(tools)
            if config.tool_choice != "auto":
                kwargs["tool_choice"] = {"type": config.tool_choice}

        current_tool_id = ""
        current_tool_name = ""
        current_tool_args = ""

        async with self._client.messages.stream(**kwargs) as stream:
            async for event in stream:
                if event.type == "content_block_start":
                    block = event.content_block
                    if hasattr(block, "type") and block.type == "tool_use":
                        current_tool_id = block.id
                        current_tool_name = block.name
                        current_tool_args = ""
                elif event.type == "content_block_delta":
                    delta = event.delta
                    if hasattr(delta, "type"):
                        if delta.type == "text_delta":
                            yield StreamEvent(type="text_delta", text=delta.text)
                        elif delta.type == "input_json_delta":
                            current_tool_args += delta.partial_json
                elif event.type == "content_block_stop":
                    if current_tool_id:
                        try:
                            args = json.loads(current_tool_args) if current_tool_args else {}
                        except json.JSONDecodeError:
                            args = {"_raw": current_tool_args}
                        yield StreamEvent(
                            type="tool_call_delta",
                            tool_call=ToolCall(
                                id=current_tool_id,
                                name=current_tool_name,
                                arguments=args,
                            ),
                        )
                        current_tool_id = ""
                        current_tool_name = ""
                        current_tool_args = ""
                elif event.type == "message_stop":
                    yield StreamEvent(type="done")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self._client.close()
