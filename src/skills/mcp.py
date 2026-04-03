"""
MCP skill builder — wrap MCP tools as callable skills.

Ports: skills/mcpSkillBuilders.ts
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from .loader import Skill


@dataclass
class MCPSkillTool:
    """A single tool exposed by an MCP skill."""
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Awaitable[Any]] | Callable[..., Any]


@dataclass
class MCPSkill:
    """
    An MCP-based skill — wraps a set of tools under a single skill name.

    Ports: skills/mcpSkillBuilders.ts
    """
    name: str
    description: str
    tools: list[MCPSkillTool] = field(default_factory=list)
    tags: list[str] = field(default_factory=lambda: ["mcp"])

    def to_skill(self) -> Skill:
        """Convert to a generic Skill for the skill loader."""
        tool_descs = "\n".join(
            f"- **{t.name}**: {t.description}" for t in self.tools
        )
        content = f"""\
# {self.name}

{self.description}

## Available Tools

{tool_descs}

## Usage

Each tool can be called with its name and input parameters.

## MCP Source

This skill is powered by the MCP (Model Context Protocol) server.
"""
        return Skill(
            name=self.name,
            description=self.description,
            content=content,
            source="mcp",
            tags=self.tags,
        )


def build_mcp_skill(
    name: str,
    description: str,
    tools: list[MCPSkillTool],
    tags: list[str] | None = None,
) -> MCPSkill:
    """
    Build an MCP skill from a name, description, and tool definitions.

    Example::

        skill = build_mcp_skill(
            name="filesystem",
            description="File system operations",
            tools=[
                MCPSkillTool(
                    name="read_file",
                    description="Read a file",
                    input_schema={"path": {"type": "string"}},
                    handler=read_file_handler,
                ),
            ],
        )
    """
    return MCPSkill(
        name=name,
        description=description,
        tools=tools,
        tags=tags or ["mcp"],
    )


def mcp_tool(
    name: str,
    description: str,
    input_schema: dict[str, Any] | None = None,
):
    """
    Decorator to declare an async function as an MCP tool.

    Example::

        @mcp_tool(name="grep", description="Search for pattern in files")
        async def grep_tool(pattern: str, path: str = ".") -> str:
            ...
    """
    def decorator(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        # Attach metadata to the function
        fn._mcp_tool_name = name  # type: ignore[attr-defined]
        fn._mcp_tool_description = description  # type: ignore[attr-defined]
        fn._mcp_tool_schema = input_schema or _infer_schema(fn)  # type: ignore[attr-defined]
        return fn

    return decorator


def _infer_schema(fn: Callable) -> dict[str, Any]:
    """Heuristic: try to build a schema from function signature."""
    import inspect
    sig = inspect.signature(fn)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for param_name, param in sig.parameters.items():
        if param_name in ("cls", "self"):
            continue
        if param.annotation is inspect.Parameter.empty:
            param_type = "string"
        elif param.annotation in (int, float):
            param_type = "number"
        elif param.annotation is bool:
            param_type = "boolean"
        else:
            param_type = "string"
        properties[param_name] = {"type": param_type}
        if param.default is inspect.Parameter.empty:
            required.append(param_name)
    return {"type": "object", "properties": properties, "required": required}


def extract_tools_from_module(module: Any) -> list[MCPSkillTool]:
    """
    Scan a Python module for functions decorated with @mcp_tool
    and return them as MCPSkillTool instances.
    """
    tools: list[MCPSkillTool] = []
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if callable(obj) and hasattr(obj, "_mcp_tool_name"):
            tools.append(MCPSkillTool(
                name=obj._mcp_tool_name,
                description=obj._mcp_tool_description,
                input_schema=obj._mcp_tool_schema,
                handler=obj,
            ))
    return tools


__all__ = [
    "MCPSkill",
    "MCPSkillTool",
    "build_mcp_skill",
    "mcp_tool",
    "extract_tools_from_module",
]
