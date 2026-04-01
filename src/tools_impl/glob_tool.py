"""Glob tool — find files matching glob patterns."""
from __future__ import annotations

from pathlib import Path

from .base import Tool, ToolContext, ToolResult


class GlobTool(Tool):
    @property
    def name(self) -> str:
        return "glob"

    @property
    def description(self) -> str:
        return "Find files matching a glob pattern. Returns list of matching file paths."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g., '**/*.py', 'src/**/*.ts')",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (default: cwd)",
                },
            },
            "required": ["pattern"],
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        pattern = args.get("pattern", "")
        search_path = args.get("path", ".")

        if not pattern:
            return ToolResult(success=False, output="", error="pattern is required")

        p = Path(search_path)
        if not p.is_absolute():
            p = context.cwd / p

        if not p.exists():
            return ToolResult(success=False, output="", error=f"Path not found: {p}")

        try:
            matches = sorted(p.glob(pattern))
            # Filter to files only
            files = [f for f in matches if f.is_file()]

            max_results = 1000
            result_lines: list[str] = []
            for f in files[:max_results]:
                try:
                    rel = f.relative_to(context.cwd) if f.is_relative_to(context.cwd) else f
                    result_lines.append(str(rel))
                except ValueError:
                    result_lines.append(str(f))

            if not result_lines:
                return ToolResult(
                    success=True,
                    output="No files matched the pattern",
                    metadata={"matches": 0},
                )

            output = "\n".join(result_lines)
            if len(files) > max_results:
                output += f"\n... ({len(files)} total, showing first {max_results})"

            return ToolResult(
                success=True,
                output=output,
                metadata={"matches": len(files)},
            )

        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
