"""
Base types and Protocol for LLM providers.
All providers implement the LLMProvider Protocol.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import AsyncIterator, Protocol, runtime_checkable


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class ToolDef:
    name: str
    description: str
    parameters: dict  # JSON Schema


@dataclass
class UsageInfo:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class Message:
    role: str  # "user" | "assistant" | "system" | "tool"
    content: str | list[dict]
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None  # for tool role messages


@dataclass
class CompletionResult:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: UsageInfo = field(default_factory=UsageInfo)
    stop_reason: str = "stop"  # "stop" | "tool_use" | "max_tokens" | "error"


@dataclass
class StreamEvent:
    type: str  # "text_delta" | "tool_call_delta" | "done" | "error"
    text: str | None = None
    tool_call: ToolCall | None = None
    error: str | None = None
    usage: UsageInfo | None = None


@dataclass
class ModelConfig:
    temperature: float = 0.7
    top_p: float = 0.95
    max_tokens: int = 8192
    tool_choice: str = "auto"  # "auto" | "none" | "required"
    extra: dict = field(default_factory=dict)


@runtime_checkable
class LLMProvider(Protocol):
    """Abstract protocol for LLM providers."""

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDef],
        config: ModelConfig,
    ) -> CompletionResult:
        """Send messages and return a single completion result."""
        ...

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDef],
        config: ModelConfig,
    ) -> AsyncIterator[StreamEvent]:
        """Stream completion events."""
        ...
