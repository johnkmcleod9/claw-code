"""Grep tool — regex search across files in a directory."""
from __future__ import annotations

import re
from pathlib import Path

from .base import Tool, ToolContext, ToolResult


class GrepTool(Tool):
    @property
    def name(self) -> str:
        return "grep"

    @property
    def description(self) -> str:
        return "Search for a regex pattern across files in a directory. Returns matching lines with file paths and line numbers."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for",
                },
                "path": {
                    "type": "string",
                    "description": "Directory or file to search in (default: cwd)",
                },
                "include": {
                    "type": "string",
                    "description": "Glob pattern for files to include (e.g., '*.py')",
                },
            },
            "required": ["pattern"],
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        pattern_str = args.get("pattern", "")
        search_path = args.get("path", ".")
        include = args.get("include")

        if not pattern_str:
            return ToolResult(success=False, output="", error="pattern is required")

        try:
            pattern = re.compile(pattern_str)
        except re.error as e:
            return ToolResult(success=False, output="", error=f"Invalid regex: {e}")

        p = Path(search_path)
        if not p.is_absolute():
            p = context.cwd / p

        if not p.exists():
            return ToolResult(success=False, output="", error=f"Path not found: {p}")

        matches: list[str] = []
        max_matches = 500
        files_searched = 0

        try:
            if p.is_file():
                files = [p]
            else:
                glob_pattern = include or "**/*"
                files = sorted(p.glob(glob_pattern))

            for fp in files:
                if not fp.is_file():
                    continue
                # Skip binary files
                if fp.suffix in {".pyc", ".so", ".dll", ".exe", ".bin", ".png", ".jpg", ".gif", ".zip", ".tar", ".gz"}:
                    continue
                files_searched += 1
                try:
                    text = fp.read_text(encoding="utf-8", errors="ignore")
                    for i, line in enumerate(text.splitlines(), 1):
                        if pattern.search(line):
                            rel = fp.relative_to(context.cwd) if fp.is_relative_to(context.cwd) else fp
                            matches.append(f"{rel}:{i}: {line.rstrip()}")
                            if len(matches) >= max_matches:
                                break
                except (PermissionError, OSError):
                    continue
                if len(matches) >= max_matches:
                    break

            if not matches:
                return ToolResult(
                    success=True,
                    output=f"No matches found ({files_searched} files searched)",
                    metadata={"matches": 0, "files_searched": files_searched},
                )

            output = "\n".join(matches)
            if len(matches) >= max_matches:
                output += f"\n... (truncated at {max_matches} matches)"

            return ToolResult(
                success=True,
                output=output,
                metadata={"matches": len(matches), "files_searched": files_searched},
            )

        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
