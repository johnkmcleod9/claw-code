"""
Team mode — multi-agent orchestration with shared task lists.

Implements Claude Code's Agent Teams pattern:
- Orchestrator breaks work into subtasks with dependencies
- Sub-agents execute tasks in parallel within authorized file scopes
- File-level locking prevents write conflicts
- Shared task list coordinates everything

Tools:
  team_create  — Activate team mode with a task breakdown
  team_task    — Create/update tasks in the shared task list
  team_assign  — Assign a task to a sub-agent
  team_status  — View team status, task progress, agent activity
  team_stop    — Deactivate team mode
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .base import Tool, ToolContext, ToolResult

# ─── Data model ───

class TaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class TeamTask:
    id: str
    description: str
    files: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    agent_id: str | None = None
    result: str | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None


@dataclass
class TeamState:
    active: bool = False
    objective: str = ""
    tasks: dict[str, TeamTask] = field(default_factory=dict)
    file_locks: dict[str, str] = field(default_factory=dict)  # filepath → task_id
    agents: dict[str, dict] = field(default_factory=dict)  # agent_id → info
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "active": self.active,
            "objective": self.objective,
            "tasks": {k: asdict(v) for k, v in self.tasks.items()},
            "file_locks": self.file_locks,
            "agents": self.agents,
        }


# Global team state
_team = TeamState()

TEAM_STATE_FILE = Path.home() / ".claw-code" / "team-state.json"


def _save_state():
    TEAM_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    TEAM_STATE_FILE.write_text(json.dumps(_team.to_dict(), indent=2))


def _load_state():
    global _team
    if TEAM_STATE_FILE.exists():
        try:
            data = json.loads(TEAM_STATE_FILE.read_text())
            _team.active = data.get("active", False)
            _team.objective = data.get("objective", "")
            _team.file_locks = data.get("file_locks", {})
            _team.agents = data.get("agents", {})
            for tid, tdata in data.get("tasks", {}).items():
                _team.tasks[tid] = TeamTask(
                    id=tdata["id"],
                    description=tdata["description"],
                    files=tdata.get("files", []),
                    depends_on=tdata.get("depends_on", []),
                    status=TaskStatus(tdata.get("status", "pending")),
                    agent_id=tdata.get("agent_id"),
                    result=tdata.get("result"),
                    error=tdata.get("error"),
                    created_at=tdata.get("created_at", 0),
                    started_at=tdata.get("started_at"),
                    completed_at=tdata.get("completed_at"),
                )
        except Exception:
            pass


def _can_start(task: TeamTask) -> bool:
    """Check if all dependencies are completed."""
    for dep_id in task.depends_on:
        dep = _team.tasks.get(dep_id)
        if not dep or dep.status != TaskStatus.COMPLETED:
            return False
    return True


def _acquire_locks(task: TeamTask) -> list[str]:
    """Try to acquire file locks for a task. Returns list of conflicting files."""
    conflicts = []
    for f in task.files:
        if f in _team.file_locks and _team.file_locks[f] != task.id:
            conflicts.append(f"{f} (locked by task {_team.file_locks[f]})")
    return conflicts


def _lock_files(task: TeamTask):
    for f in task.files:
        _team.file_locks[f] = task.id


def _unlock_files(task: TeamTask):
    for f in task.files:
        if _team.file_locks.get(f) == task.id:
            del _team.file_locks[f]


def _status_summary() -> str:
    if not _team.active:
        return "Team mode is not active."

    counts = {}
    for t in _team.tasks.values():
        counts[t.status.value] = counts.get(t.status.value, 0) + 1

    total = len(_team.tasks)
    done = counts.get("completed", 0)
    progress = f"{done}/{total}" if total else "0/0"

    lines = [
        f"## 🏗️ Team Mode — {progress} tasks complete",
        f"**Objective:** {_team.objective}",
        "",
        "### Task Breakdown",
    ]

    # Sort: in_progress first, then pending, then completed
    order = {"in_progress": 0, "assigned": 1, "blocked": 2, "pending": 3, "completed": 4, "failed": 5}
    sorted_tasks = sorted(_team.tasks.values(), key=lambda t: order.get(t.status.value, 9))

    for t in sorted_tasks:
        icon = {
            "pending": "⬜", "assigned": "📋", "in_progress": "🔄",
            "completed": "✅", "failed": "❌", "blocked": "🚫",
        }.get(t.status.value, "❓")

        deps = ""
        if t.depends_on:
            deps = f" (after: {', '.join(t.depends_on)})"

        agent = f" → agent:{t.agent_id}" if t.agent_id else ""
        files = f" [{', '.join(t.files[:3])}]" if t.files else ""

        lines.append(f"  {icon} **{t.id}**: {t.description}{deps}{agent}{files}")
        if t.error:
            lines.append(f"      ⚠️ {t.error}")

    if _team.file_locks:
        lines.append(f"\n### File Locks ({len(_team.file_locks)})")
        for f, tid in _team.file_locks.items():
            lines.append(f"  🔒 {f} → {tid}")

    lines.append(f"\n**Agents:** {len(_team.agents)} | **Locked files:** {len(_team.file_locks)}")

    return "\n".join(lines)


# ─── Tools ───

class TeamCreateTool(Tool):
    """Activate team mode with an objective and task breakdown."""

    @property
    def name(self) -> str:
        return "team_create"

    @property
    def description(self) -> str:
        return (
            "Activate team mode for parallel multi-agent work. "
            "Provide an objective and a list of tasks with dependencies. "
            "Each task specifies which files it can modify (file-level locking). "
            "Sub-agents will be spawned to work on tasks in parallel."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "objective": {
                    "type": "string",
                    "description": "High-level objective for the team",
                },
                "tasks": {
                    "type": "array",
                    "description": "Task breakdown",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "Short task ID (e.g., 'auth', 'api', 'tests')"},
                            "description": {"type": "string"},
                            "files": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Files this task is authorized to modify",
                            },
                            "depends_on": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Task IDs that must complete before this one",
                            },
                        },
                        "required": ["id", "description"],
                    },
                },
            },
            "required": ["objective", "tasks"],
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        global _team
        _load_state()

        if _team.active:
            return ToolResult(
                success=False, output="",
                error="Team already active. Use team_stop first, or team_status to check progress.",
            )

        objective = args.get("objective", "")
        tasks_data = args.get("tasks", [])

        if not tasks_data:
            return ToolResult(success=False, output="", error="At least one task is required")

        _team = TeamState(active=True, objective=objective)

        for td in tasks_data:
            task = TeamTask(
                id=td["id"],
                description=td["description"],
                files=td.get("files", []),
                depends_on=td.get("depends_on", []),
            )
            _team.tasks[task.id] = task

        # Validate dependencies
        for t in _team.tasks.values():
            for dep in t.depends_on:
                if dep not in _team.tasks:
                    return ToolResult(
                        success=False, output="",
                        error=f"Task '{t.id}' depends on unknown task '{dep}'",
                    )

        _save_state()
        return ToolResult(success=True, output=_status_summary())


class TeamTaskTool(Tool):
    """Update a task's status, result, or error."""

    @property
    def name(self) -> str:
        return "team_task"

    @property
    def description(self) -> str:
        return (
            "Update a task in the team task list. "
            "Set status, record results, or report errors. "
            "File locks are automatically managed based on task status."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID to update"},
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "completed", "failed", "blocked"],
                },
                "result": {"type": "string", "description": "Result summary when completing"},
                "error": {"type": "string", "description": "Error message if failed"},
                "agent_id": {"type": "string", "description": "Agent ID working on this task"},
            },
            "required": ["task_id"],
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        _load_state()
        if not _team.active:
            return ToolResult(success=False, output="", error="Team mode not active")

        task_id = args.get("task_id", "")
        task = _team.tasks.get(task_id)
        if not task:
            return ToolResult(
                success=False, output="",
                error=f"Unknown task: {task_id}. Available: {', '.join(_team.tasks)}",
            )

        new_status = args.get("status")
        if new_status:
            old_status = task.status
            task.status = TaskStatus(new_status)

            if new_status == "in_progress":
                # Check dependencies
                if not _can_start(task):
                    pending_deps = [d for d in task.depends_on
                                    if _team.tasks.get(d, TeamTask(id="?", description="")).status != TaskStatus.COMPLETED]
                    task.status = TaskStatus.BLOCKED
                    _save_state()
                    return ToolResult(
                        success=False, output="",
                        error=f"Blocked: waiting on {', '.join(pending_deps)}",
                    )

                # Acquire file locks
                conflicts = _acquire_locks(task)
                if conflicts:
                    task.status = TaskStatus.BLOCKED
                    _save_state()
                    return ToolResult(
                        success=False, output="",
                        error=f"File conflicts: {'; '.join(conflicts)}",
                    )
                _lock_files(task)
                task.started_at = time.time()

            elif new_status in ("completed", "failed"):
                _unlock_files(task)
                task.completed_at = time.time()

                # Check if any blocked tasks can now start
                for t in _team.tasks.values():
                    if t.status == TaskStatus.BLOCKED and _can_start(t):
                        conflicts = _acquire_locks(t)
                        if not conflicts:
                            t.status = TaskStatus.PENDING  # Ready to be picked up

        if args.get("result"):
            task.result = args["result"]
        if args.get("error"):
            task.error = args["error"]
        if args.get("agent_id"):
            task.agent_id = args["agent_id"]

        _save_state()
        return ToolResult(success=True, output=_status_summary())


class TeamAssignTool(Tool):
    """Assign a task to a sub-agent and spawn it."""

    @property
    def name(self) -> str:
        return "team_assign"

    @property
    def description(self) -> str:
        return (
            "Assign a pending task to a sub-agent. "
            "Spawns a sub-agent process with the task description and authorized files. "
            "The agent works independently and reports back via team_task."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task to assign"},
                "model": {"type": "string", "description": "Model for the sub-agent (default: session model)"},
            },
            "required": ["task_id"],
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        _load_state()
        if not _team.active:
            return ToolResult(success=False, output="", error="Team mode not active")

        task_id = args.get("task_id", "")
        task = _team.tasks.get(task_id)
        if not task:
            return ToolResult(success=False, output="", error=f"Unknown task: {task_id}")

        if task.status not in (TaskStatus.PENDING, TaskStatus.BLOCKED):
            return ToolResult(
                success=False, output="",
                error=f"Task {task_id} is {task.status.value}, not assignable",
            )

        if not _can_start(task):
            pending = [d for d in task.depends_on
                       if _team.tasks.get(d, TeamTask(id="?", description="")).status != TaskStatus.COMPLETED]
            return ToolResult(
                success=False, output="",
                error=f"Task blocked on: {', '.join(pending)}",
            )

        conflicts = _acquire_locks(task)
        if conflicts:
            return ToolResult(
                success=False, output="",
                error=f"File conflicts: {'; '.join(conflicts)}",
            )

        # Lock files and update status
        _lock_files(task)
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = time.time()

        # Build the sub-agent prompt
        model = args.get("model", "")
        file_scope = "\n".join(f"  - {f}" for f in task.files) if task.files else "  (any files)"

        agent_prompt = (
            f"You are a sub-agent working on task '{task_id}'.\n\n"
            f"## Objective\n{task.description}\n\n"
            f"## Authorized Files\n{file_scope}\n\n"
            f"## Rules\n"
            f"- ONLY modify the files listed above\n"
            f"- Do NOT modify files outside your scope\n"
            f"- When done, summarize what you changed\n"
            f"- If stuck, explain what you need\n\n"
            f"## Context\n"
            f"Team objective: {_team.objective}\n"
            f"Working directory: {context.cwd}\n"
        )

        # Spawn via the agent tool
        from .agent_tool import AgentTool
        agent_tool = AgentTool()
        agent_args = {
            "prompt": agent_prompt,
            "task": task.description,
        }
        if model:
            agent_args["model"] = model

        result = await agent_tool.execute(agent_args, context)

        if result.success and result.metadata:
            agent_id = result.metadata.get("agent_id", "unknown")
            task.agent_id = agent_id
            _team.agents[agent_id] = {
                "task_id": task_id,
                "model": model,
                "spawned_at": time.time(),
            }

        _save_state()
        return ToolResult(
            success=True,
            output=f"🚀 Task `{task_id}` assigned to agent `{task.agent_id}`\n\n{_status_summary()}",
            metadata={"task_id": task_id, "agent_id": task.agent_id},
        )


class TeamStatusTool(Tool):
    """View team status."""

    @property
    def name(self) -> str:
        return "team_status"

    @property
    def description(self) -> str:
        return "View the current team status — tasks, progress, file locks, and agents."

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        _load_state()
        return ToolResult(success=True, output=_status_summary())


class TeamStopTool(Tool):
    """Deactivate team mode."""

    @property
    def name(self) -> str:
        return "team_stop"

    @property
    def description(self) -> str:
        return "Deactivate team mode. Releases all file locks and generates a summary."

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        global _team
        _load_state()

        if not _team.active:
            return ToolResult(success=True, output="Team mode was not active.")

        # Final summary
        summary = _status_summary()

        completed = sum(1 for t in _team.tasks.values() if t.status == TaskStatus.COMPLETED)
        total = len(_team.tasks)
        failed = sum(1 for t in _team.tasks.values() if t.status == TaskStatus.FAILED)

        result_lines = [
            summary,
            "",
            "---",
            f"## Team Mode Deactivated",
            f"**Completed:** {completed}/{total}",
        ]
        if failed:
            result_lines.append(f"**Failed:** {failed}")

        # Collect results
        for t in _team.tasks.values():
            if t.result:
                result_lines.append(f"\n### {t.id}: {t.description}")
                result_lines.append(t.result)

        _team = TeamState()  # Reset
        _save_state()

        return ToolResult(success=True, output="\n".join(result_lines))
