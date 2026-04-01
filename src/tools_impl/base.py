"""
Base classes for executable tools.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ToolContext:
    """Context passed to tool execution."""
    cwd: Path = field(default_factory=Path.cwd)
    allowed_paths: list[Path] | None = None  # None = no restriction
    timeout: float = 30.0
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class ToolResult:
    """Result of tool execution."""
    success: bool
    output: str
    error: str | None = None
    metadata: dict = field(default_factory=dict)

    def to_content(self) -> str:
        """Format result as content string for the LLM."""
        if self.success:
            return self.output
        else:
            msg = f"Error: {self.error}" if self.error else "Tool execution failed"
            if self.output:
                msg += f"\nOutput: {self.output}"
            return msg


class Tool(ABC):
    """Abstract base class for all tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name (used in tool calls)."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description."""
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict:
        """JSON Schema for tool parameters."""
        ...

    @abstractmethod
    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        """Execute the tool with given arguments."""
        ...

    def to_tool_def(self):
        """Convert to a ToolDef for the provider."""
        from src.providers.base import ToolDef
        return ToolDef(name=self.name, description=self.description, parameters=self.parameters)
