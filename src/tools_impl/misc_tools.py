"""
Miscellaneous small tools ported from Claude Code.

- SleepTool: pause execution
- AskUserTool: ask the user a question
- BriefTool: summarize long content
- ToolSearchTool: search available tools
"""
from __future__ import annotations

import asyncio

from .base import Tool, ToolContext, ToolResult


class SleepTool(Tool):
    @property
    def name(self) -> str:
        return "sleep"

    @property
    def description(self) -> str:
        return "Pause execution for a specified number of seconds. Use when waiting for processes."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "seconds": {
                    "type": "number",
                    "description": "Seconds to sleep (max 300)",
                    "minimum": 0.1,
                    "maximum": 300,
                },
            },
            "required": ["seconds"],
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        seconds = min(args.get("seconds", 1), 300)
        await asyncio.sleep(seconds)
        return ToolResult(success=True, output=f"Slept for {seconds}s")


class AskUserTool(Tool):
    @property
    def name(self) -> str:
        return "ask_user"

    @property
    def description(self) -> str:
        return (
            "Ask the user a question and wait for their response. "
            "Use when you need clarification, confirmation, or a decision."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Question to ask the user",
                },
            },
            "required": ["question"],
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        question = args.get("question", "")
        if not question:
            return ToolResult(success=False, output="", error="question is required")

        try:
            print(f"\n💬 Agent asks: {question}")
            response = input("Your answer: ")
            return ToolResult(success=True, output=f"User response: {response}")
        except (EOFError, KeyboardInterrupt):
            return ToolResult(success=True, output="User did not respond (input cancelled)")


class ToolSearchTool(Tool):
    """Search available tools by keyword."""

    def __init__(self, registry=None):
        self._registry = registry

    @property
    def name(self) -> str:
        return "tool_search"

    @property
    def description(self) -> str:
        return "Search for available tools by name or keyword."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (tool name or keyword)",
                },
            },
            "required": ["query"],
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        query = args.get("query", "").lower()
        if not query:
            return ToolResult(success=False, output="", error="query is required")

        if self._registry is None:
            return ToolResult(success=True, output="No tool registry available")

        matches = []
        for tool in self._registry.list_tools():
            if query in tool.name.lower() or query in tool.description.lower():
                matches.append(f"- **{tool.name}**: {tool.description}")

        if not matches:
            all_tools = [t.name for t in self._registry.list_tools()]
            return ToolResult(
                success=True,
                output=f"No tools matching '{query}'. Available: {', '.join(all_tools)}",
            )

        return ToolResult(success=True, output=f"Tools matching '{query}':\n\n" + "\n".join(matches))
