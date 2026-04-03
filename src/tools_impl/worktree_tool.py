"""
Worktree tools — git worktree isolation for safe experimentation.

EnterWorktreeTool: Create a git worktree and switch agent's working directory
ExitWorktreeTool: Return to original directory, optionally clean up worktree
"""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from .base import Tool, ToolContext, ToolResult

# Track active worktree
_original_cwd: Path | None = None
_worktree_path: Path | None = None
_worktree_branch: str | None = None


async def _run_git(cmd: str, cwd: Path) -> tuple[bool, str]:
    """Run a git command and return (success, output)."""
    proc = await asyncio.create_subprocess_shell(
        f"git {cmd}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cwd),
    )
    stdout, stderr = await proc.communicate()
    output = stdout.decode().strip()
    if proc.returncode != 0:
        output = stderr.decode().strip() or output
    return proc.returncode == 0, output


class EnterWorktreeTool(Tool):
    @property
    def name(self) -> str:
        return "enter_worktree"

    @property
    def description(self) -> str:
        return (
            "Create a git worktree for isolated experimentation. "
            "Changes happen in a separate branch/directory, leaving the main working "
            "tree untouched. Good for risky changes, testing approaches, or parallel work."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "branch": {
                    "type": "string",
                    "description": "Branch name for the worktree (auto-generated if omitted)",
                },
                "base": {
                    "type": "string",
                    "description": "Base branch/commit to start from (default: HEAD)",
                },
            },
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        global _original_cwd, _worktree_path, _worktree_branch

        if _worktree_path is not None:
            return ToolResult(
                success=False, output="",
                error=f"Already in worktree at {_worktree_path}. Exit first.",
            )

        # Check we're in a git repo
        ok, _ = await _run_git("rev-parse --git-dir", context.cwd)
        if not ok:
            return ToolResult(success=False, output="", error="Not in a git repository")

        branch = args.get("branch", "")
        base = args.get("base", "HEAD")

        if not branch:
            import time
            branch = f"claw-worktree-{int(time.time())}"

        # Create worktree in temp directory
        wt_path = Path(tempfile.mkdtemp(prefix="claw-wt-"))
        ok, output = await _run_git(f"worktree add -b {branch} {wt_path} {base}", context.cwd)

        if not ok:
            return ToolResult(success=False, output="", error=f"Failed to create worktree: {output}")

        _original_cwd = context.cwd
        _worktree_path = wt_path
        _worktree_branch = branch

        return ToolResult(
            success=True,
            output=(
                f"🌿 **Worktree created**\n"
                f"- Branch: `{branch}`\n"
                f"- Path: `{wt_path}`\n"
                f"- Base: `{base}`\n\n"
                f"You're now working in the isolated worktree. "
                f"Changes here won't affect the main tree.\n"
                f"Call `exit_worktree` when done."
            ),
            metadata={"worktree_path": str(wt_path), "branch": branch},
        )


class ExitWorktreeTool(Tool):
    @property
    def name(self) -> str:
        return "exit_worktree"

    @property
    def description(self) -> str:
        return (
            "Exit the current git worktree and return to the original directory. "
            "Optionally merge changes back or clean up the worktree."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["keep", "merge", "discard"],
                    "description": "keep = leave worktree, merge = merge to original branch, discard = delete",
                },
            },
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        global _original_cwd, _worktree_path, _worktree_branch

        if _worktree_path is None or _original_cwd is None:
            return ToolResult(success=False, output="", error="Not in a worktree")

        action = args.get("action", "keep")
        wt_path = _worktree_path
        branch = _worktree_branch
        orig = _original_cwd

        result_lines = [f"🌿 **Exiting worktree** (`{branch}`)"]

        if action == "merge":
            # Commit any changes in worktree
            await _run_git("add -A", wt_path)
            ok, _ = await _run_git('diff --cached --quiet', wt_path)
            if not ok:
                await _run_git(f'commit -m "worktree: {branch} changes"', wt_path)

            # Merge into original branch
            ok, output = await _run_git(f"merge {branch}", orig)
            if ok:
                result_lines.append(f"✅ Merged `{branch}` into current branch")
            else:
                result_lines.append(f"⚠️ Merge conflict: {output}")

        if action == "discard":
            # Remove worktree and branch
            await _run_git(f"worktree remove --force {wt_path}", orig)
            await _run_git(f"branch -D {branch}", orig)
            result_lines.append(f"🗑️ Worktree and branch `{branch}` deleted")
        elif action == "keep":
            result_lines.append(f"📁 Worktree kept at `{wt_path}` on branch `{branch}`")
        else:
            # Clean up worktree but keep branch
            await _run_git(f"worktree remove --force {wt_path}", orig)
            result_lines.append(f"Branch `{branch}` preserved, worktree cleaned up")

        # Reset state
        _original_cwd = None
        _worktree_path = None
        _worktree_branch = None

        result_lines.append(f"\nBack to: `{orig}`")

        return ToolResult(success=True, output="\n".join(result_lines))
