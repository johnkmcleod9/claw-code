"""
ToolRegistry — loads all tools and provides lookup/filtering.
"""
from __future__ import annotations

import json

from .base import Tool, ToolContext, ToolResult
from src.providers.base import ToolDef


class ToolRegistry:
    """Registry of available tools. Provides lookup, filtering, and execution."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool instance."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        """List all registered tools."""
        return list(self._tools.values())

    def list_names(self) -> list[str]:
        """List all tool names."""
        return list(self._tools.keys())

    def filter(self, names: list[str] | None = None) -> list[Tool]:
        """Get tools filtered by name list. None = all tools."""
        if names is None:
            return self.list_tools()
        return [t for n in names if (t := self._tools.get(n))]

    def to_tool_defs(self, names: list[str] | None = None) -> list[ToolDef]:
        """Convert tools to ToolDef list for provider."""
        return [t.to_tool_def() for t in self.filter(names)]

    async def execute(self, name: str, args: dict, context: ToolContext) -> ToolResult:
        """Execute a tool by name.

        Includes _raw unwrapping: if a provider stored malformed tool call
        arguments as {"_raw": "<json string>"}, we attempt to parse that
        string back into proper arguments before execution.
        """
        tool = self.get(name)
        if tool is None:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool: {name}. Available: {', '.join(self.list_names())}",
            )

        # Safety net: unwrap _raw arguments from providers that failed JSON parsing
        if "_raw" in args and len(args) == 1:
            raw_val = args["_raw"]
            if isinstance(raw_val, dict):
                # _raw is already a parsed dict — use it directly
                args = raw_val
            elif isinstance(raw_val, str):
                try:
                    parsed = json.loads(raw_val)
                    if isinstance(parsed, dict):
                        args = parsed
                except (json.JSONDecodeError, TypeError):
                    pass

        try:
            return await tool.execute(args, context)
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Tool '{name}' raised: {e}")


def create_default_registry() -> ToolRegistry:
    """Create a registry with all built-in tools."""
    from .file_read import FileReadTool
    from .file_write import FileWriteTool
    from .file_edit import FileEditTool
    from .bash_tool import BashTool
    from .grep_tool import GrepTool
    from .glob_tool import GlobTool
    from .web_search import WebSearchTool
    from .web_fetch import WebFetchTool
    from .todo_tool import TodoWriteTool, TodoReadTool
    from .skill_tool import SkillTool
    from .agent_tool import AgentTool, TaskListTool, TaskGetTool
    from .notebook_edit import NotebookEditTool
    from .misc_tools import SleepTool, AskUserTool, ToolSearchTool
    from .mcp_tool import MCPTool, ListMcpResourcesTool
    from .repl_tool import REPLTool
    from .config_tool import ConfigTool
    from .plan_tool import EnterPlanModeTool, ExitPlanModeTool
    from .worktree_tool import EnterWorktreeTool, ExitWorktreeTool
    from .team_tool import TeamCreateTool, TeamTaskTool, TeamAssignTool, TeamStatusTool, TeamStopTool
    from .dream_tool import DreamTool

    registry = ToolRegistry()

    # Core file tools
    registry.register(FileReadTool())
    registry.register(FileWriteTool())
    registry.register(FileEditTool())

    # Shell & REPL
    registry.register(BashTool())
    registry.register(REPLTool())

    # Search tools
    registry.register(GrepTool())
    registry.register(GlobTool())

    # Web tools
    registry.register(WebSearchTool())
    registry.register(WebFetchTool())

    # Task management
    registry.register(TodoWriteTool())
    registry.register(TodoReadTool())

    # Skills
    registry.register(SkillTool())

    # Agent / sub-agent tools
    registry.register(AgentTool())
    registry.register(TaskListTool())
    registry.register(TaskGetTool())

    # MCP integration
    registry.register(MCPTool())
    registry.register(ListMcpResourcesTool())

    # Notebook
    registry.register(NotebookEditTool())

    # Plan mode
    registry.register(EnterPlanModeTool())
    registry.register(ExitPlanModeTool())

    # Git worktree
    registry.register(EnterWorktreeTool())
    registry.register(ExitWorktreeTool())

    # Team mode (multi-agent orchestration)
    registry.register(TeamCreateTool())
    registry.register(TeamTaskTool())
    registry.register(TeamAssignTool())
    registry.register(TeamStatusTool())
    registry.register(TeamStopTool())

    # Dream mode (background reasoning)
    registry.register(DreamTool())

    # Config
    registry.register(ConfigTool())

    # Utility tools
    registry.register(SleepTool())
    registry.register(AskUserTool())
    registry.register(ToolSearchTool(registry))

    return registry
