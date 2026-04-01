"""
LM Studio provider for local models.
OpenAI-compatible API at http://localhost:1234/v1/chat/completions.
No API key required.
"""
from __future__ import annotations

import json
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

LMSTUDIO_BASE_URL = "http://localhost:1234/v1"


def _messages_to_openai(messages: list[Message]) -> list[dict]:
    """Convert messages to OpenAI-compatible format (same as OpenRouter)."""
    result = []
    for msg in messages:
        d: dict = {"role": msg.role}
        if msg.role == "tool":
            d["tool_call_id"] = msg.tool_call_id or ""
            d["content"] = msg.content if isinstance(msg.content, str) else json.dumps(msg.content)
            if msg.name:
                d["name"] = msg.name
            result.append(d)
            continue

        if isinstance(msg.content, str):
            d["content"] = msg.content
        else:
            d["content"] = msg.content

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
                repaired = _repair_json(str(raw_args))
                if repaired is not None:
                    args = repaired
                else:
                    args = {"_raw": raw_args}
        calls.append(
            ToolCall(id=tc.get("id", str(uuid.uuid4())), name=fn.get("name", ""), arguments=args)
        )
    return calls


class LMStudioProvider:
    """LM Studio local model provider. OpenAI-compatible API."""

    def __init__(self, model_id: str = "local-model", base_url: str | None = None):
        self.model_id = model_id
        self.base_url = base_url or LMSTUDIO_BASE_URL
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=300.0,  # Local models can be slow
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
            cost_usd=0.0,  # Local models are free
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

                choice = data.get("choices", [{}])[0]
                delta = choice.get("delta", {})

                if delta.get("content"):
                    yield StreamEvent(type="text_delta", text=delta["content"])

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

                finish = choice.get("finish_reason")
                if finish in ("tool_calls", "stop") and accumulated_tool_calls:
                    for idx in sorted(accumulated_tool_calls):
                        acc = accumulated_tool_calls[idx]
                        try:
                            args = json.loads(acc["arguments"] or "{}")
                        except json.JSONDecodeError:
                            repaired = _repair_json(acc["arguments"])
                            if repaired is not None:
                                args = repaired
                            else:
                                args = {"_raw": acc["arguments"]}
                        tc = ToolCall(id=acc["id"], name=acc["name"], arguments=args)
                        yield StreamEvent(type="tool_call_delta", tool_call=tc)

        yield StreamEvent(type="done")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self._client.aclose()
