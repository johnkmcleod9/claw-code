"""
Shell execution helpers.

Ports: utils/Shell.ts, utils/ShellCommand.ts
"""
from __future__ import annotations

import asyncio
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ShellResult:
    """Result from running a shell command."""
    command: str
    returncode: int
    stdout: str
    stderr: str
    success: bool = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "success", self.returncode == 0)

    @property
    def output(self) -> str:
        """Combined stdout + stderr."""
        parts = [s for s in (self.stdout, self.stderr) if s.strip()]
        return "\n".join(parts)

    def check(self) -> "ShellResult":
        """Raise RuntimeError if the command failed."""
        if not self.success:
            raise RuntimeError(
                f"Command failed (exit {self.returncode}): {self.command}\n{self.stderr or self.stdout}"
            )
        return self


def run(
    command: str | list[str],
    *,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
    input: str | None = None,
    capture: bool = True,
    shell: bool | None = None,
) -> ShellResult:
    """
    Run a shell command synchronously.

    Args:
        command: Command string or list of args.
        cwd: Working directory.
        env: Environment variables (merged with current env if not None).
        timeout: Timeout in seconds.
        input: Text to pass on stdin.
        capture: If True, capture stdout/stderr; otherwise inherit.
        shell: Force shell mode. Default: True for str commands.
    """
    use_shell = shell if shell is not None else isinstance(command, str)
    cmd_str = command if isinstance(command, str) else shlex.join(command)

    merged_env = None
    if env is not None:
        merged_env = {**os.environ, **env}

    kwargs: dict = {
        "cwd": str(cwd) if cwd else None,
        "env": merged_env,
        "timeout": timeout,
        "shell": use_shell,
    }
    if capture:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
        kwargs["text"] = True
    if input is not None:
        kwargs["input"] = input
        if not capture:
            kwargs["stdin"] = subprocess.PIPE

    try:
        result = subprocess.run(command, **kwargs)
        return ShellResult(
            command=cmd_str,
            returncode=result.returncode,
            stdout=result.stdout or "" if capture else "",
            stderr=result.stderr or "" if capture else "",
        )
    except subprocess.TimeoutExpired:
        return ShellResult(
            command=cmd_str,
            returncode=-1,
            stdout="",
            stderr=f"Command timed out after {timeout}s",
        )
    except FileNotFoundError as exc:
        return ShellResult(
            command=cmd_str,
            returncode=127,
            stdout="",
            stderr=str(exc),
        )


async def run_async(
    command: str | list[str],
    *,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
    input: str | None = None,
) -> ShellResult:
    """
    Run a shell command asynchronously.

    Streams stdout/stderr back as strings.
    """
    use_shell = isinstance(command, str)
    cmd_str = command if isinstance(command, str) else shlex.join(command)

    merged_env = None
    if env is not None:
        merged_env = {**os.environ, **env}

    input_bytes = input.encode() if input else None

    if use_shell:
        proc = await asyncio.create_subprocess_shell(
            command,  # type: ignore[arg-type]
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd) if cwd else None,
            env=merged_env,
        )
    else:
        args = command if isinstance(command, list) else shlex.split(command)
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd) if cwd else None,
            env=merged_env,
        )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(input_bytes),
            timeout=timeout,
        )
        return ShellResult(
            command=cmd_str,
            returncode=proc.returncode or 0,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return ShellResult(
            command=cmd_str,
            returncode=-1,
            stdout="",
            stderr=f"Command timed out after {timeout}s",
        )


def which(name: str) -> str | None:
    """Return the full path of *name* if found on PATH, else None."""
    return shutil.which(name)


def require_command(name: str) -> str:
    """Return full path of *name*, raising RuntimeError if not found."""
    path = which(name)
    if path is None:
        raise RuntimeError(f"Required command not found: {name}")
    return path


def quote(arg: str) -> str:
    """Shell-escape a single argument."""
    return shlex.quote(arg)


def join_args(args: list[str]) -> str:
    """Join a list of arguments into a safely-quoted shell command string."""
    return shlex.join(args)


def split_command(command: str) -> list[str]:
    """Split a shell command string into a list of arguments."""
    return shlex.split(command)


def git_root(path: str | Path | None = None) -> Path | None:
    """Return the git repository root for *path*, or None."""
    result = run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=path or Path.cwd(),
        capture=True,
    )
    if result.success:
        return Path(result.stdout.strip())
    return None


__all__ = [
    "ShellResult",
    "run",
    "run_async",
    "which",
    "require_command",
    "quote",
    "join_args",
    "split_command",
    "git_root",
]
