"""
AgentTool — Launch sub-agents for parallel work.

Ported from rust/crates/tools/src/lib.rs execute_agent().
Spawns a sub-agent as a separate process with its own model, prompt, and tools.
Results are stored on disk and can be retrieved via task tools.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .base import Tool, ToolContext, ToolResult

AGENT_STORE = Path.home() / ".claw-code" / "agents"

# Track running sub-agents in-process
_running_agents: dict[str, dict] = {}


def _agent_id() -> str:
    return f"agent-{uuid.uuid4().hex[:8]}"


def _slugify(text: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in text.lower())[:50].strip("-")


class AgentTool(Tool):
    @property
    def name(self) -> str:
        return "agent"

    @property
    def description(self) -> str:
        return (
            "Launch a sub-agent to work on a task in parallel. "
            "The sub-agent gets its own conversation, model, and tools. "
            "Use this to delegate research, coding subtasks, or any work that can "
            "happen independently. Check results with task_get or task_list."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Brief description of what the agent should do",
                },
                "prompt": {
                    "type": "string",
                    "description": "Detailed prompt/instructions for the sub-agent",
                },
                "name": {
                    "type": "string",
                    "description": "Optional name for the agent (auto-generated if omitted)",
                },
                "model": {
                    "type": "string",
                    "description": "Model to use (e.g., 'deepseek', 'minimax'). Uses parent's model if omitted.",
                },
            },
            "required": ["description", "prompt"],
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        description = args.get("description", "").strip()
        prompt = args.get("prompt", "").strip()
        name = args.get("name", "")
        model = args.get("model", "")

        if not description:
            return ToolResult(success=False, output="", error="description is required")
        if not prompt:
            return ToolResult(success=False, output="", error="prompt is required")

        agent_id = _agent_id()
        agent_name = _slugify(name) if name else _slugify(description)
        created_at = datetime.now(timezone.utc).isoformat()

        # Create agent store
        AGENT_STORE.mkdir(parents=True, exist_ok=True)

        # Write task file
        task_file = AGENT_STORE / f"{agent_id}.md"
        task_file.write_text(
            f"# Agent Task\n\n"
            f"- id: {agent_id}\n"
            f"- name: {agent_name}\n"
            f"- description: {description}\n"
            f"- model: {model or 'default'}\n"
            f"- created_at: {created_at}\n"
            f"- status: running\n\n"
            f"## Prompt\n\n{prompt}\n"
        )

        # Write manifest
        manifest = {
            "agent_id": agent_id,
            "name": agent_name,
            "description": description,
            "model": model or "default",
            "status": "running",
            "created_at": created_at,
            "output_file": str(task_file),
            "workdir": str(context.cwd),
        }
        manifest_file = AGENT_STORE / f"{agent_id}.json"
        manifest_file.write_text(json.dumps(manifest, indent=2))

        # Launch the sub-agent as a background process
        model_flag = f"--model {model}" if model else ""
        claw_path = Path(__file__).parent.parent.parent / "repl.py"
        cmd = (
            f"cd {context.cwd} && python3 {claw_path} "
            f"--task {json.dumps(prompt)} "
            f"{model_flag} "
            f"--no-approval --workdir {context.cwd} "
            f"2>&1 | tee {AGENT_STORE / f'{agent_id}.output.txt'}"
        )

        # Start in background
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(context.cwd),
        )

        _running_agents[agent_id] = {
            "process": process,
            "manifest": manifest,
            "started": time.time(),
        }

        return ToolResult(
            success=True,
            output=(
                f"🚀 Agent launched: **{agent_name}** (`{agent_id}`)\n"
                f"- Model: {model or 'default'}\n"
                f"- Task: {description}\n"
                f"- Use `task_get` with id `{agent_id}` to check status/results"
            ),
            metadata=manifest,
        )


class TaskListTool(Tool):
    @property
    def name(self) -> str:
        return "task_list"

    @property
    def description(self) -> str:
        return "List all sub-agent tasks and their status."

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        if not AGENT_STORE.exists():
            return ToolResult(success=True, output="No agents have been launched yet.")

        manifests = sorted(AGENT_STORE.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not manifests:
            return ToolResult(success=True, output="No agents found.")

        lines = ["## Agent Tasks\n"]
        for mf in manifests[:20]:
            try:
                data = json.loads(mf.read_text())
                agent_id = data["agent_id"]

                # Check if still running
                if agent_id in _running_agents:
                    proc = _running_agents[agent_id]["process"]
                    if proc.returncode is not None:
                        data["status"] = "completed"
                        mf.write_text(json.dumps(data, indent=2))
                        del _running_agents[agent_id]

                status_icon = {"running": "🔄", "completed": "✅", "failed": "❌", "queued": "⬜"}.get(
                    data.get("status", ""), "❓"
                )
                lines.append(f"{status_icon} **{data.get('name', agent_id)}** (`{agent_id}`)")
                lines.append(f"   {data.get('description', '')}")
                lines.append(f"   Status: {data.get('status', 'unknown')} | Model: {data.get('model', 'default')}")
                lines.append("")
            except Exception:
                continue

        return ToolResult(success=True, output="\n".join(lines))


class TaskGetTool(Tool):
    @property
    def name(self) -> str:
        return "task_get"

    @property
    def description(self) -> str:
        return "Get the status and output of a sub-agent task by ID."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "Agent task ID (e.g., agent-a1b2c3d4)",
                },
            },
            "required": ["id"],
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        agent_id = args.get("id", "").strip()
        if not agent_id:
            return ToolResult(success=False, output="", error="id is required")

        manifest_file = AGENT_STORE / f"{agent_id}.json"
        output_file = AGENT_STORE / f"{agent_id}.output.txt"

        if not manifest_file.exists():
            return ToolResult(success=False, output="", error=f"Agent {agent_id} not found")

        data = json.loads(manifest_file.read_text())

        # Check if still running
        if agent_id in _running_agents:
            proc = _running_agents[agent_id]["process"]
            if proc.returncode is not None:
                data["status"] = "completed"
                manifest_file.write_text(json.dumps(data, indent=2))
                del _running_agents[agent_id]

        lines = [
            f"## Agent: {data.get('name', agent_id)}",
            f"- ID: {agent_id}",
            f"- Status: {data.get('status', 'unknown')}",
            f"- Model: {data.get('model', 'default')}",
            f"- Created: {data.get('created_at', 'unknown')}",
            f"- Description: {data.get('description', '')}",
        ]

        if output_file.exists():
            output = output_file.read_text()
            if len(output) > 20_000:
                output = output[:20_000] + "\n... (truncated)"
            lines.append(f"\n## Output\n\n{output}")
        elif data.get("status") == "running":
            lines.append("\n*Agent is still running...*")

        return ToolResult(success=True, output="\n".join(lines), metadata=data)
