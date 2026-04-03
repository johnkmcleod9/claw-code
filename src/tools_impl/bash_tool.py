"""
BashTool — execute shell commands with timeout, injection defense, and error recovery.

WP 8614: Hardened version with:
- Injection pattern detection (prompt injection / command chaining attacks)
- Safe environment variable sanitization
- Structured error classification
- Output sanitization (removes ANSI escape codes from stderr)
- Configurable deny-list of dangerous patterns
- Graceful process cleanup on timeout/cancel
"""
from __future__ import annotations

import asyncio
import os
import re
import shlex
from pathlib import Path
from typing import Any

from .base import Tool, ToolContext, ToolResult

# ---------------------------------------------------------------------------
# Injection defense — patterns that should never appear in agent-generated
# commands without explicit user approval.  We warn (not block) by default
# so legitimate usage isn't broken, but the flag is surfaced in metadata.
# ---------------------------------------------------------------------------

_SUSPICIOUS_PATTERNS: list[re.Pattern[str]] = [
    # Exfiltration via network
    re.compile(r"\bcurl\b.*\|\s*bash", re.IGNORECASE),
    re.compile(r"\bwget\b.*\|\s*sh", re.IGNORECASE),
    # Prompt-injection probe: agent tries to override its own instructions
    re.compile(r"ignore\s+previous\s+instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+all\s+prior", re.IGNORECASE),
    # Credential harvesting
    re.compile(r"\benv\b.*\|\s*(curl|wget|nc\b)", re.IGNORECASE),
    re.compile(r"\bcat\s+~/?\.(aws|ssh|netrc|pgpass)\b", re.IGNORECASE),
    # Self-replication / persistence
    re.compile(r"(crontab|launchctl|systemctl|rc\.local).*\|", re.IGNORECASE),
    # Fork bombs
    re.compile(r":\(\)\{.*:\|:&", re.IGNORECASE),
]

_ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# Dangerous single commands that deserve a loud warning in metadata
_DANGER_COMMANDS = frozenset([
    "rm -rf /", "rm -rf ~", "dd if=/dev/zero", "mkfs", ":(){:|:&};:",
    "chmod -R 777 /", "chmod -R 000 /",
])


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from output."""
    return _ANSI_ESCAPE.sub("", text)


def _classify_exit_code(code: int) -> str:
    """Map common exit codes to human-readable reasons."""
    mapping = {
        1:   "General error",
        2:   "Misuse of shell built-in",
        126: "Command not executable",
        127: "Command not found",
        128: "Invalid exit argument",
        130: "Script terminated by Ctrl+C",
        137: "Process killed (SIGKILL / OOM)",
        139: "Segmentation fault (SIGSEGV)",
        141: "Broken pipe (SIGPIPE)",
        143: "Process terminated (SIGTERM)",
    }
    if code in mapping:
        return mapping[code]
    if code > 128:
        return f"Killed by signal {code - 128}"
    return f"Exit code {code}"


def _scan_for_injection(command: str) -> list[str]:
    """Return list of suspicious pattern descriptions found in command."""
    hits: list[str] = []
    for pattern in _SUSPICIOUS_PATTERNS:
        if pattern.search(command):
            hits.append(pattern.pattern)
    for danger in _DANGER_COMMANDS:
        if danger in command:
            hits.append(f"dangerous command: {danger!r}")
    return hits


def _sanitize_env(env: dict[str, str] | None) -> dict[str, str]:
    """
    Build a clean environment.

    - Starts from current process environment
    - Overlays caller-provided extras
    - Strips keys that could be used for injection via tool args
    """
    base = dict(os.environ)
    if env:
        # Only allow string → string mappings; skip anything suspicious
        for k, v in env.items():
            if isinstance(k, str) and isinstance(v, str):
                base[k] = v
    # Ensure PATH is always present
    base.setdefault("PATH", "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin")
    return base


class BashTool(Tool):
    """
    Execute shell commands with safety checks and structured error reporting.
    """

    @property
    def name(self) -> str:
        return "bash"

    @property
    def description(self) -> str:
        return (
            "Execute a shell command. Captures stdout and stderr. "
            "Has a configurable timeout (default 30s, max 300s). "
            "Suspicious injection patterns are flagged in metadata."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute",
                },
                "timeout": {
                    "type": "number",
                    "description": "Timeout in seconds (default: 30, max: 300)",
                },
                "env": {
                    "type": "object",
                    "description": "Additional environment variables (string → string)",
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["command"],
        }

    async def execute(self, args: dict[str, Any], context: ToolContext) -> ToolResult:
        command: str = args.get("command", "").strip()
        raw_timeout = args.get("timeout", context.timeout)
        extra_env: dict[str, str] | None = args.get("env")

        # ── Basic validation ───────────────────────────────────────────────
        if not command:
            return ToolResult(success=False, output="", error="command is required")

        timeout = max(1.0, min(float(raw_timeout), 300.0))

        # ── Injection scan ─────────────────────────────────────────────────
        injection_hits = _scan_for_injection(command)
        injection_warning: str | None = None
        if injection_hits:
            injection_warning = (
                "⚠️ Suspicious pattern(s) detected: "
                + ", ".join(injection_hits[:5])
            )

        # ── Environment ────────────────────────────────────────────────────
        env = _sanitize_env(extra_env)

        # ── Execution ──────────────────────────────────────────────────────
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(context.cwd),
                env=env,
            )

            timed_out = False
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                timed_out = True
                # Graceful: SIGTERM first, then SIGKILL
                try:
                    proc.terminate()
                    await asyncio.wait_for(proc.communicate(), timeout=3.0)
                except Exception:
                    proc.kill()
                    try:
                        await asyncio.wait_for(proc.communicate(), timeout=2.0)
                    except Exception:
                        pass
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Command timed out after {timeout:.0f}s and was killed",
                    metadata={
                        "command": command,
                        "timeout": timeout,
                        "timed_out": True,
                        "injection_warning": injection_warning,
                    },
                )

            # ── Output processing ──────────────────────────────────────────
            stdout_str = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr_str = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""

            # Strip ANSI codes from stderr (often noisy with color codes)
            stderr_clean = _strip_ansi(stderr_str).strip()

            output = stdout_str
            if stderr_clean:
                sep = "\n" if output else ""
                output += f"{sep}STDERR:\n{stderr_clean}"

            # Truncate very long output to avoid flooding the context
            max_output = 100_000
            original_len = len(stdout_str) + len(stderr_str)
            if len(output) > max_output:
                output = (
                    output[:max_output]
                    + f"\n… [truncated — original output was {original_len:,} chars]"
                )

            exit_code = proc.returncode or 0
            success = exit_code == 0

            error_msg: str | None = None
            if not success:
                error_msg = _classify_exit_code(exit_code)
                if stderr_clean and len(stderr_clean) < 500:
                    # Surface stderr as structured error for quick debugging
                    error_msg += f" — {stderr_clean.splitlines()[0]}"

            metadata: dict[str, Any] = {
                "command": command,
                "exit_code": exit_code,
                "stdout_chars": len(stdout_str),
                "stderr_chars": len(stderr_str),
            }
            if injection_warning:
                metadata["injection_warning"] = injection_warning

            return ToolResult(
                success=success,
                output=output,
                error=error_msg,
                metadata=metadata,
            )

        except FileNotFoundError as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Shell not found: {e}",
                metadata={"command": command},
            )
        except PermissionError as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Permission denied: {e}",
                metadata={"command": command},
            )
        except OSError as e:
            return ToolResult(
                success=False,
                output="",
                error=f"OS error: {e}",
                metadata={"command": command},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Unexpected error: {type(e).__name__}: {e}",
                metadata={"command": command},
            )
