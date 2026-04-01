"""FileRead tool — read file contents with optional line range."""
from __future__ import annotations

from pathlib import Path

from .base import Tool, ToolContext, ToolResult


class FileReadTool(Tool):
    @property
    def name(self) -> str:
        return "file_read"

    @property
    def description(self) -> str:
        return "Read the contents of a file. Supports optional offset and limit for partial reads."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read (relative to working directory or absolute)",
                },
                "offset": {
                    "type": "integer",
                    "description": "Line number to start reading from (1-indexed). Default: 1",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of lines to read. Default: all",
                },
            },
            "required": ["path"],
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        file_path = args.get("path", "")
        offset = args.get("offset", 1)
        limit = args.get("limit")

        if not file_path:
            return ToolResult(success=False, output="", error="path is required")

        # Resolve path
        p = Path(file_path)
        if not p.is_absolute():
            p = context.cwd / p

        try:
            if not p.exists():
                return ToolResult(success=False, output="", error=f"File not found: {p}")

            if not p.is_file():
                return ToolResult(success=False, output="", error=f"Not a file: {p}")

            text = p.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines(keepends=True)

            # Apply offset (1-indexed)
            start = max(0, (offset or 1) - 1)
            if limit:
                end = start + limit
                lines = lines[start:end]
            else:
                lines = lines[start:]

            content = "".join(lines)

            metadata = {
                "path": str(p),
                "total_lines": len(text.splitlines()),
                "returned_lines": len(lines),
                "size_bytes": p.stat().st_size,
            }

            return ToolResult(success=True, output=content, metadata=metadata)

        except PermissionError:
            return ToolResult(success=False, output="", error=f"Permission denied: {p}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
