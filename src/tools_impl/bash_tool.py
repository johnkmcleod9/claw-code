"""BashTool — execute shell commands with timeout and output capture."""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from .base import Tool, ToolContext, ToolResult


class BashTool(Tool):
    @property
    def name(self) -> str:
        return "bash"

    @property
    def description(self) -> str:
        return "Execute a shell command. Captures stdout and stderr. Has a configurable timeout."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute",
                },
                "timeout": {
                    "type": "number",
                    "description": "Timeout in seconds (default: 30)",
                },
            },
            "required": ["command"],
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        command = args.get("command", "")
        timeout = args.get("timeout", context.timeout)

        if not command:
            return ToolResult(success=False, output="", error="command is required")

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(context.cwd),
                env={**dict(__import__("os").environ), **context.env} if context.env else None,
            )

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Command timed out after {timeout}s",
                )

            stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
            stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""

            output = stdout_str
            if stderr_str:
                output += f"\nSTDERR:\n{stderr_str}" if output else f"STDERR:\n{stderr_str}"

            # Truncate very long output
            max_output = 100_000
            if len(output) > max_output:
                output = output[:max_output] + f"\n... (truncated, total {len(stdout_str) + len(stderr_str)} chars)"

            return ToolResult(
                success=proc.returncode == 0,
                output=output,
                error=f"Exit code: {proc.returncode}" if proc.returncode != 0 else None,
                metadata={"exit_code": proc.returncode, "command": command},
            )

        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
