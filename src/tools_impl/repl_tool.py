"""
REPLTool — Execute code in Python, JavaScript, or shell REPLs.

Ported from rust/crates/tools/src/lib.rs execute_repl().
Runs code snippets in a subprocess without needing to write files.
"""
from __future__ import annotations

import asyncio
import shutil
import time

from .base import Tool, ToolContext, ToolResult

# Runtime configs for supported languages
RUNTIMES = {
    "python": {"commands": ["python3", "python"], "args": ["-c"]},
    "py": {"commands": ["python3", "python"], "args": ["-c"]},
    "javascript": {"commands": ["node"], "args": ["-e"]},
    "js": {"commands": ["node"], "args": ["-e"]},
    "node": {"commands": ["node"], "args": ["-e"]},
    "sh": {"commands": ["bash", "sh"], "args": ["-lc"]},
    "shell": {"commands": ["bash", "sh"], "args": ["-lc"]},
    "bash": {"commands": ["bash"], "args": ["-lc"]},
    "ruby": {"commands": ["ruby"], "args": ["-e"]},
    "rb": {"commands": ["ruby"], "args": ["-e"]},
}


def _find_runtime(language: str) -> tuple[str, list[str]] | None:
    """Find the first available runtime for a language."""
    config = RUNTIMES.get(language.lower().strip())
    if not config:
        return None
    for cmd in config["commands"]:
        if shutil.which(cmd):
            return cmd, config["args"]
    return None


class REPLTool(Tool):
    @property
    def name(self) -> str:
        return "repl"

    @property
    def description(self) -> str:
        return (
            "Execute code in an interactive REPL (Python, JavaScript, shell, Ruby). "
            "Runs the code snippet directly without needing to write a file first. "
            "Good for quick calculations, testing snippets, or exploring APIs."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "language": {
                    "type": "string",
                    "enum": ["python", "javascript", "sh", "bash", "ruby"],
                    "description": "Language to execute",
                },
                "code": {
                    "type": "string",
                    "description": "Code to execute",
                },
                "timeout_ms": {
                    "type": "integer",
                    "description": "Timeout in milliseconds (default: 30000)",
                },
            },
            "required": ["language", "code"],
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        language = args.get("language", "python")
        code = args.get("code", "")
        timeout_ms = args.get("timeout_ms", 30000)

        if not code.strip():
            return ToolResult(success=False, output="", error="code must not be empty")

        runtime = _find_runtime(language)
        if runtime is None:
            supported = list(set(RUNTIMES.keys()))
            return ToolResult(
                success=False, output="",
                error=f"Unsupported or unavailable language: {language}. Supported: {', '.join(sorted(supported))}",
            )

        program, run_args = runtime
        timeout_s = timeout_ms / 1000.0
        start = time.time()

        try:
            proc = await asyncio.create_subprocess_exec(
                program, *run_args, code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(context.cwd),
            )

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return ToolResult(
                    success=False, output="",
                    error=f"REPL execution timed out after {timeout_s}s",
                )

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")
            duration_ms = int((time.time() - start) * 1000)

            output_parts = []
            if stdout_str:
                output_parts.append(stdout_str)
            if stderr_str:
                output_parts.append(f"STDERR:\n{stderr_str}")
            output_parts.append(f"\n[{language} | exit {proc.returncode} | {duration_ms}ms]")

            return ToolResult(
                success=proc.returncode == 0,
                output="\n".join(output_parts),
                error=f"Exit code: {proc.returncode}" if proc.returncode != 0 else None,
                metadata={
                    "language": language,
                    "exit_code": proc.returncode,
                    "duration_ms": duration_ms,
                },
            )

        except Exception as e:
            return ToolResult(success=False, output="", error=f"REPL error: {e}")
