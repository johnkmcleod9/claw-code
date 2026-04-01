"""FileEdit tool — find and replace exact text in files."""
from __future__ import annotations

from pathlib import Path

from .base import Tool, ToolContext, ToolResult


class FileEditTool(Tool):
    @property
    def name(self) -> str:
        return "file_edit"

    @property
    def description(self) -> str:
        return "Edit a file by replacing exact text. The old_text must match exactly (including whitespace)."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to edit",
                },
                "old_text": {
                    "type": "string",
                    "description": "Exact text to find and replace (must match exactly)",
                },
                "new_text": {
                    "type": "string",
                    "description": "New text to replace the old text with",
                },
            },
            "required": ["path", "old_text", "new_text"],
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        file_path = args.get("path", "")
        old_text = args.get("old_text", "")
        new_text = args.get("new_text", "")

        if not file_path:
            return ToolResult(success=False, output="", error="path is required")
        if not old_text:
            return ToolResult(success=False, output="", error="old_text is required")

        p = Path(file_path)
        if not p.is_absolute():
            p = context.cwd / p

        try:
            if not p.exists():
                return ToolResult(success=False, output="", error=f"File not found: {p}")

            content = p.read_text(encoding="utf-8")
            count = content.count(old_text)

            if count == 0:
                # Show a snippet of the file for debugging
                lines = content.splitlines()[:20]
                snippet = "\n".join(lines)
                return ToolResult(
                    success=False,
                    output=f"File preview (first 20 lines):\n{snippet}",
                    error=f"old_text not found in {p}",
                )

            if count > 1:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"old_text matches {count} times in {p}. Make the match more specific.",
                )

            new_content = content.replace(old_text, new_text, 1)
            p.write_text(new_content, encoding="utf-8")

            return ToolResult(
                success=True,
                output=f"Edited {p}: replaced 1 occurrence",
                metadata={"path": str(p), "replacements": 1},
            )

        except PermissionError:
            return ToolResult(success=False, output="", error=f"Permission denied: {p}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
