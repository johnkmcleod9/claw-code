"""
TodoWriteTool — Session task list management.

Ported from rust/crates/tools/src/lib.rs execute_todo_write().
Maintains a structured task list that persists within a session.
The agent uses this to track progress on multi-step tasks.
"""
from __future__ import annotations

import json
from pathlib import Path

from .base import Tool, ToolContext, ToolResult

# Session-scoped todo storage (persists within a REPL session)
_session_todos: list[dict] = []


def _render_todos(todos: list[dict]) -> str:
    """Render todos as a readable checklist."""
    if not todos:
        return "No tasks in the current session."

    lines = ["## Session Tasks\n"]
    for i, todo in enumerate(todos, 1):
        status = todo.get("status", "pending")
        content = todo.get("content", "")
        active = todo.get("activeForm", "")

        if status == "completed":
            icon = "✅"
        elif status == "in_progress":
            icon = "🔄"
        else:
            icon = "⬜"

        line = f"{icon} {i}. {content}"
        if status == "in_progress" and active:
            line += f" — *{active}*"
        lines.append(line)

    # Summary
    total = len(todos)
    done = sum(1 for t in todos if t.get("status") == "completed")
    in_prog = sum(1 for t in todos if t.get("status") == "in_progress")
    pending = total - done - in_prog
    lines.append(f"\n**Progress:** {done}/{total} complete" +
                 (f" | {in_prog} in progress" if in_prog else "") +
                 (f" | {pending} pending" if pending else ""))

    return "\n".join(lines)


class TodoWriteTool(Tool):
    @property
    def name(self) -> str:
        return "todo_write"

    @property
    def description(self) -> str:
        return (
            "Update the structured task list for the current session. "
            "Use this to plan multi-step work, track progress, and show what's done. "
            "Send the complete list each time (replaces previous). "
            "At most one item can be 'in_progress' at a time."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "Task description",
                            },
                            "activeForm": {
                                "type": "string",
                                "description": "What's currently being done (shown when in_progress)",
                            },
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                                "description": "Task status",
                            },
                        },
                        "required": ["content", "status"],
                    },
                    "description": "Complete task list (replaces previous)",
                },
            },
            "required": ["todos"],
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        global _session_todos
        todos = args.get("todos", [])

        if not todos:
            return ToolResult(success=False, output="", error="todos must not be empty")

        # Validate: at most one in_progress
        in_progress = sum(1 for t in todos if t.get("status") == "in_progress")
        if in_progress > 1:
            return ToolResult(
                success=False, output="",
                error="At most one todo item can be 'in_progress' at a time",
            )

        # Validate: no empty content
        for t in todos:
            if not t.get("content", "").strip():
                return ToolResult(success=False, output="", error="Todo content must not be empty")

        # Update session todos
        _session_todos = todos

        # Also save to .claw-todos.md in the working directory for persistence
        try:
            todo_file = context.cwd / ".claw-todos.md"
            todo_file.write_text(_render_todos(todos) + "\n")
        except Exception:
            pass  # Non-fatal: in-memory is primary

        return ToolResult(
            success=True,
            output=_render_todos(todos),
            metadata={"count": len(todos)},
        )


class TodoReadTool(Tool):
    """Read the current session task list."""

    @property
    def name(self) -> str:
        return "todo_read"

    @property
    def description(self) -> str:
        return "Read the current session task list to check progress."

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        return ToolResult(success=True, output=_render_todos(_session_todos))
