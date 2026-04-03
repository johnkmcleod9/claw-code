"""
Plan mode tools — think before acting.

EnterPlanModeTool: Switch to read-only mode (no writes/executions)
ExitPlanModeTool: Switch back to full mode

When in plan mode, the agent can only use read-only tools (file_read, grep, glob,
web_search, web_fetch). Write tools (file_write, file_edit, bash) are blocked.
"""
from __future__ import annotations

from .base import Tool, ToolContext, ToolResult

# Global plan mode state
_plan_mode = False
_plan_content: list[str] = []


def is_plan_mode() -> bool:
    return _plan_mode


def get_plan() -> list[str]:
    return _plan_content


WRITE_TOOLS = {"bash", "file_write", "file_edit", "agent", "notebook_edit", "repl", "config"}
READ_TOOLS = {"file_read", "grep", "glob", "web_search", "web_fetch", "todo_read",
              "task_list", "task_get", "skill", "tool_search", "mcp_resources", "sleep"}


class EnterPlanModeTool(Tool):
    @property
    def name(self) -> str:
        return "enter_plan_mode"

    @property
    def description(self) -> str:
        return (
            "Switch to plan mode — read-only exploration without making changes. "
            "Use this to analyze code, explore options, and form a plan before acting. "
            "Write tools (bash, file_write, file_edit) are blocked in plan mode. "
            "Call exit_plan_mode when ready to execute."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why entering plan mode (helps track intent)",
                },
            },
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        global _plan_mode, _plan_content
        _plan_mode = True
        _plan_content = []
        reason = args.get("reason", "exploring before acting")
        return ToolResult(
            success=True,
            output=(
                f"📋 **Plan mode activated** — {reason}\n\n"
                f"Read-only tools available: {', '.join(sorted(READ_TOOLS))}\n"
                f"Blocked until exit: {', '.join(sorted(WRITE_TOOLS))}\n\n"
                f"Call `exit_plan_mode` with your plan when ready to execute."
            ),
        )


class ExitPlanModeTool(Tool):
    @property
    def name(self) -> str:
        return "exit_plan_mode"

    @property
    def description(self) -> str:
        return (
            "Exit plan mode and return to full execution mode. "
            "Provide a summary of the plan you've formed."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "plan": {
                    "type": "string",
                    "description": "Summary of the plan formed during exploration",
                },
            },
            "required": ["plan"],
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        global _plan_mode
        plan = args.get("plan", "")
        _plan_mode = False

        if not plan.strip():
            return ToolResult(success=False, output="", error="plan summary is required")

        return ToolResult(
            success=True,
            output=(
                f"✅ **Plan mode deactivated** — full execution restored\n\n"
                f"## Plan\n{plan}\n\n"
                f"All tools now available. Proceed with execution."
            ),
        )
