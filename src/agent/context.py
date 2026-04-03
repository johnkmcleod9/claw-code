"""
Build system prompt from profile, tools, and workspace context.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from src.profiles.model_profile import ModelProfile
from src.tools_impl.base import Tool


def _get_git_info(cwd: Path) -> str | None:
    """Get current git branch and status."""
    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=str(cwd), timeout=5,
        )
        if branch.returncode != 0:
            return None
        return f"Git branch: {branch.stdout.strip()}"
    except Exception:
        return None


def _load_project_context(cwd: Path) -> list[tuple[str, str]]:
    """Load project context files (CLAUDE.md, AGENTS.md, etc.) from cwd and parents."""
    context_filenames = [
        "CLAUDE.md",
        "AGENTS.md",
        ".claude/settings.md",
        ".github/copilot-instructions.md",
    ]
    found: list[tuple[str, str]] = []
    max_content = 5_000  # Max chars per context file

    # Check cwd and up to 3 parent directories
    check_dirs = [cwd]
    p = cwd
    for _ in range(3):
        p = p.parent
        if p == p.parent:
            break
        check_dirs.append(p)

    seen_names: set[str] = set()
    for d in check_dirs:
        for filename in context_filenames:
            filepath = d / filename
            if filepath.exists() and filename not in seen_names:
                seen_names.add(filename)
                try:
                    content = filepath.read_text()
                    if len(content) > max_content:
                        content = content[:max_content] + "\n... (truncated)"
                    found.append((filename, content))
                except Exception:
                    pass

    return found


def _get_file_tree(cwd: Path, max_depth: int = 2, max_files: int = 50) -> str:
    """Get a simple file tree of the working directory."""
    lines: list[str] = []
    count = 0

    def walk(p: Path, depth: int, prefix: str = ""):
        nonlocal count
        if depth > max_depth or count > max_files:
            return
        try:
            entries = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name))
        except PermissionError:
            return

        for entry in entries:
            if entry.name.startswith(".") and entry.name not in {".env"}:
                continue
            if entry.name in {"__pycache__", "node_modules", ".git", "venv", ".venv"}:
                continue
            count += 1
            if count > max_files:
                lines.append(f"{prefix}... (truncated)")
                return
            if entry.is_dir():
                lines.append(f"{prefix}{entry.name}/")
                walk(entry, depth + 1, prefix + "  ")
            else:
                lines.append(f"{prefix}{entry.name}")

    walk(cwd, 0)
    return "\n".join(lines)


def build_system_prompt(
    profile: ModelProfile,
    tools: list[Tool],
    cwd: Path | None = None,
) -> str:
    """Build the system prompt for the agent."""
    cwd = cwd or Path.cwd()
    parts: list[str] = []

    # Core identity
    parts.append(
        "You are an autonomous coding agent. You complete tasks by using your tools — "
        "reading files, writing/editing code, and running commands.\n\n"
        "CRITICAL RULES:\n"
        "1. You MUST use tools to produce output. Thinking about code is not enough — "
        "you must call file_write or file_edit to create or modify files.\n"
        "2. After reading a file, your NEXT action should be a tool call (file_edit, "
        "file_write, or bash) — not just a text explanation.\n"
        "3. For bug fixes: read the file, identify the bug, then call file_edit with "
        "the exact old_text and new_text to fix it.\n"
        "4. For new code: call file_write with the complete file content.\n"
        "5. Always verify your changes (run tests, check syntax) using the bash tool.\n"
        "6. When done, briefly summarize what you changed."
    )

    # Model-specific style hints
    if profile.system_prompt_style == "chain_of_thought":
        parts.append(
            "Think through each step before acting. Explain your reasoning briefly, "
            "then use the appropriate tool."
        )
    elif profile.system_prompt_style == "example_heavy":
        parts.append(
            "Follow tool schemas precisely. When in doubt, read the file first before editing."
        )

    # Workspace context
    parts.append(f"\n## Workspace\nWorking directory: {cwd}")
    git_info = _get_git_info(cwd)
    if git_info:
        parts.append(git_info)

    # Auto-load project context files (like Claude Code's CLAUDE.md)
    context_files = _load_project_context(cwd)
    if context_files:
        parts.append("\n## Project Context")
        for name, content in context_files:
            parts.append(f"\n### {name}\n{content}")

    tree = _get_file_tree(cwd)
    if tree:
        parts.append(f"\nFile tree:\n{tree}")

    # Tool descriptions
    if tools:
        parts.append("\n## Available Tools")
        for tool in tools:
            params = tool.parameters.get("properties", {})
            param_list = ", ".join(
                f"{k} ({'required' if k in tool.parameters.get('required', []) else 'optional'})"
                for k in params
            )
            parts.append(f"- **{tool.name}**: {tool.description}\n  Parameters: {param_list}")

    # Profile-specific system prompt (set by improver / self-improving loop)
    if profile.system_prompt:
        parts.append(f"\n## Model-Specific Instructions\n{profile.system_prompt}")

    # Guidelines
    parts.append(
        "\n## Guidelines\n"
        "- Read files before editing to understand context\n"
        "- ALWAYS produce file changes using file_edit or file_write tools — never just describe changes in text\n"
        "- After reading files, immediately make edits in the SAME turn using tool calls\n"
        "- Verify your changes work by running tests with the bash tool\n"
        "- If a tool call fails, read the error and try a different approach\n"
        "- When done, summarize what you changed and verify it works"
    )

    return "\n\n".join(parts)
