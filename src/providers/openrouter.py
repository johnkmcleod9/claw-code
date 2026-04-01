"""
OpenRouter provider — routes to MiniMax M2.7, Mercury 2, Qwen, etc.
Uses httpx for async HTTP.
Endpoint: https://openrouter.ai/api/v1/chat/completions
API key: OPENROUTER_API_KEY env var
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import AsyncIterator

import httpx

from .base import (
    CompletionResult,
    Message,
    ModelConfig,
    StreamEvent,
    ToolCall,
    ToolDef,
    UsageInfo,
)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _messages_to_openai(messages: list[Message]) -> list[dict]:
    """Convert our Message objects to OpenAI-compatible format."""
    result = []
    for msg in messages:
        d: dict = {"role": msg.role}

        # Tool result messages
        if msg.role == "tool":
            d["tool_call_id"] = msg.tool_call_id or ""
            d["content"] = msg.content if isinstance(msg.content, str) else json.dumps(msg.content)
            if msg.name:
                d["name"] = msg.name
            result.append(d)
            continue

        # Content
        if isinstance(msg.content, str):
            d["content"] = msg.content
        else:
            d["content"] = msg.content

        # Tool calls on assistant messages
        if msg.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in msg.tool_calls
            ]

        result.append(d)
    return result


def _tools_to_openai(tools: list[ToolDef]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in tools
    ]


def _repair_json(text: str) -> dict | None:
    """Try to repair malformed JSON from model tool calls.

    Handles common issues:
    - Leading/trailing whitespace
    - Truncated JSON (missing closing braces)
    - Double-encoded JSON (JSON string containing JSON)
    """
    text = text.strip()
    if not text:
        return None

    # First: straightforward parse
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        # If it parsed to a string, try parsing that string (double-encoded)
        if isinstance(parsed, str):
            try:
                inner = json.loads(parsed)
                if isinstance(inner, dict):
                    return inner
            except (json.JSONDecodeError, TypeError):
                pass
        return None
    except json.JSONDecodeError:
        pass

    # Try adding missing closing braces (truncated JSON)
    open_braces = text.count("{") - text.count("}")
    if open_braces > 0:
        repaired = text + ("}" * open_braces)
        try:
            parsed = json.loads(repaired)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # Try adding missing closing bracket + braces
    open_brackets = text.count("[") - text.count("]")
    if open_brackets > 0:
        repaired = text + ("]" * open_brackets) + ("}" * max(0, open_braces))
        try:
            parsed = json.loads(repaired)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # Handle truncated string values (common with output token limits)
    # If JSON has an unterminated string, close it and try to parse
    # This saves partial content rather than losing the entire tool call
    if '"' in text:
        # Close any open string, then close remaining braces/brackets
        repaired = text + '"'
        open_braces_r = repaired.count("{") - repaired.count("}")
        open_brackets_r = repaired.count("[") - repaired.count("]")
        if open_brackets_r > 0:
            repaired += "]" * open_brackets_r
        if open_braces_r > 0:
            repaired += "}" * open_braces_r
        try:
            parsed = json.loads(repaired)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    return None


def _parse_tool_calls(raw: list[dict]) -> list[ToolCall]:
    calls = []
    for tc in raw:
        fn = tc.get("function", {})
        raw_args = fn.get("arguments", "{}")

        # Some providers return arguments already parsed as a dict
        if isinstance(raw_args, dict):
            args = raw_args
        else:
            try:
                args = json.loads(raw_args)
            except (json.JSONDecodeError, TypeError):
                # Try repair before falling back to _raw
                repaired = _repair_json(str(raw_args))
                if repaired is not None:
                    args = repaired
                else:
                    args = {"_raw": raw_args}
        calls.append(ToolCall(id=tc.get("id", str(uuid.uuid4())), name=fn.get("name", ""), arguments=args))
    return calls


class OpenRouterProvider:
    """OpenRouter API provider. Covers MiniMax, Mercury, Qwen, and more."""

    def __init__(self, model_id: str, api_key: str | None = None):
        self.model_id = model_id
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not set")
        self._client = httpx.AsyncClient(
            base_url=OPENROUTER_BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://pathwisesolutions.com",
                "X-Title": "Pathwise Adaptive Harness",
            },
            timeout=300.0,
        )

    def _build_payload(
        self,
        messages: list[Message],
        tools: list[ToolDef],
        config: ModelConfig,
        stream: bool = False,
    ) -> dict:
        payload: dict = {
            "model": self.model_id,
            "messages": _messages_to_openai(messages),
            "temperature": config.temperature,
            "top_p": config.top_p,
            "max_tokens": config.max_tokens,
            "stream": stream,
        }
        if tools:
            payload["tools"] = _tools_to_openai(tools)
            payload["tool_choice"] = config.tool_choice
        payload.update(config.extra)
        return payload

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDef],
        config: ModelConfig,
    ) -> CompletionResult:
        payload = self._build_payload(messages, tools, config, stream=False)
        resp = await self._client.post("/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]
        message = choice["message"]
        content = message.get("content") or ""
        tool_calls = _parse_tool_calls(message.get("tool_calls") or [])
        stop_reason = choice.get("finish_reason", "stop")
        if tool_calls and stop_reason == "stop":
            stop_reason = "tool_use"

        usage_raw = data.get("usage", {})
        usage = UsageInfo(
            input_tokens=usage_raw.get("prompt_tokens", 0),
            output_tokens=usage_raw.get("completion_tokens", 0),
            total_tokens=usage_raw.get("total_tokens", 0),
        )

        return CompletionResult(
            content=content,
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
        payload = self._build_payload(messages, tools, config, stream=True)
        accumulated_tool_calls: dict[int, dict] = {}

        async with self._client.stream("POST", "/chat/completions", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    yield StreamEvent(type="done")
                    return
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                choices = data.get("choices", [])
                if not choices:
                    continue  # skip empty-choices chunks (e.g. reasoning-only)
                choice = choices[0]
                delta = choice.get("delta", {})

                # Text content
                if delta.get("content"):
                    yield StreamEvent(type="text_delta", text=delta["content"])

                # Tool calls (accumulate)
                for tc_delta in delta.get("tool_calls", []):
                    idx = tc_delta.get("index", 0)
                    if idx not in accumulated_tool_calls:
                        accumulated_tool_calls[idx] = {
                            "id": tc_delta.get("id", str(uuid.uuid4())),
                            "name": tc_delta.get("function", {}).get("name", ""),
                            "arguments": "",
                        }
                    acc = accumulated_tool_calls[idx]
                    if tc_delta.get("id"):
                        acc["id"] = tc_delta["id"]
                    fn = tc_delta.get("function", {})
                    if fn.get("name"):
                        acc["name"] = fn["name"]
                    if fn.get("arguments"):
                        acc["arguments"] += fn["arguments"]

                # Capture usage from stream chunks (OpenRouter includes in final chunk)
                usage_raw = data.get("usage")
                if usage_raw:
                    stream_usage = UsageInfo(
                        input_tokens=usage_raw.get("prompt_tokens", 0),
                        output_tokens=usage_raw.get("completion_tokens", 0),
                        total_tokens=usage_raw.get("total_tokens", 0),
                    )
                    yield StreamEvent(type="usage", usage=stream_usage)

                finish = choice.get("finish_reason")
                if finish and accumulated_tool_calls:
                    for idx in sorted(accumulated_tool_calls):
                        acc = accumulated_tool_calls[idx]
                        try:
                            args = json.loads(acc["arguments"] or "{}")
                        except json.JSONDecodeError:
                            # Try repair before falling back to _raw
                            repaired = _repair_json(acc["arguments"])
                            if repaired is not None:
                                args = repaired
                            else:
                                args = {"_raw": acc["arguments"]}
                        tc = ToolCall(id=acc["id"], name=acc["name"], arguments=args)
                        yield StreamEvent(type="tool_call_delta", tool_call=tc)
                    accumulated_tool_calls.clear()  # prevent duplicate emission

        yield StreamEvent(type="done")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self._client.aclose()
