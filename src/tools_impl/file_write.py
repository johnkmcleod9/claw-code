"""FileWrite tool — write content to a file, creating directories if needed."""
from __future__ import annotations

from pathlib import Path

from .base import Tool, ToolContext, ToolResult


class FileWriteTool(Tool):
    @property
    def name(self) -> str:
        return "file_write"

    @property
    def description(self) -> str:
        return "Write content to a file. Creates parent directories if they don't exist. Overwrites existing files."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to write",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
            },
            "required": ["path", "content"],
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        file_path = args.get("path", "")
        content = args.get("content", "")

        if not file_path:
            return ToolResult(success=False, output="", error="path is required")

        p = Path(file_path)
        if not p.is_absolute():
            p = context.cwd / p

        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")

            metadata = {
                "path": str(p),
                "size_bytes": p.stat().st_size,
                "lines": len(content.splitlines()),
            }

            return ToolResult(
                success=True,
                output=f"Wrote {metadata['size_bytes']} bytes to {p}",
                metadata=metadata,
            )

        except PermissionError:
            return ToolResult(success=False, output="", error=f"Permission denied: {p}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
