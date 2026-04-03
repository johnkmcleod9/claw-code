"""
NotebookEditTool — Edit Jupyter notebook cells.

Ported from rust/crates/tools/src/lib.rs execute_notebook_edit().
"""
from __future__ import annotations

import json
from pathlib import Path

from .base import Tool, ToolContext, ToolResult


class NotebookEditTool(Tool):
    @property
    def name(self) -> str:
        return "notebook_edit"

    @property
    def description(self) -> str:
        return (
            "Edit a Jupyter notebook (.ipynb) cell. Can insert, replace, or delete cells. "
            "Specify the notebook path, cell index, and the new cell content."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the .ipynb file",
                },
                "cell_index": {
                    "type": "integer",
                    "description": "0-based index of the cell to edit (-1 to append)",
                },
                "cell_type": {
                    "type": "string",
                    "enum": ["code", "markdown", "raw"],
                    "description": "Cell type (default: code)",
                },
                "source": {
                    "type": "string",
                    "description": "New cell content (omit to delete the cell)",
                },
                "action": {
                    "type": "string",
                    "enum": ["replace", "insert", "delete"],
                    "description": "Action to perform (default: replace)",
                },
            },
            "required": ["path", "cell_index"],
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        path_str = args.get("path", "")
        cell_index = args.get("cell_index", 0)
        cell_type = args.get("cell_type", "code")
        source = args.get("source", "")
        action = args.get("action", "replace")

        if not path_str:
            return ToolResult(success=False, output="", error="path is required")

        nb_path = (context.cwd / path_str).resolve()
        if not nb_path.exists():
            return ToolResult(success=False, output="", error=f"Notebook not found: {path_str}")

        try:
            nb = json.loads(nb_path.read_text())
        except json.JSONDecodeError as e:
            return ToolResult(success=False, output="", error=f"Invalid notebook JSON: {e}")

        cells = nb.get("cells", [])

        if action == "delete":
            if cell_index < 0 or cell_index >= len(cells):
                return ToolResult(success=False, output="", error=f"Cell index {cell_index} out of range (0-{len(cells)-1})")
            deleted = cells.pop(cell_index)
            nb_path.write_text(json.dumps(nb, indent=1) + "\n")
            return ToolResult(success=True, output=f"Deleted cell {cell_index} from {path_str}")

        new_cell = {
            "cell_type": cell_type,
            "source": source.split("\n") if isinstance(source, str) else source,
            "metadata": {},
        }
        if cell_type == "code":
            new_cell["outputs"] = []
            new_cell["execution_count"] = None

        if action == "insert" or cell_index == -1:
            if cell_index == -1:
                cells.append(new_cell)
            else:
                cells.insert(cell_index, new_cell)
            nb_path.write_text(json.dumps(nb, indent=1) + "\n")
            pos = len(cells) - 1 if cell_index == -1 else cell_index
            return ToolResult(success=True, output=f"Inserted {cell_type} cell at index {pos} in {path_str}")

        # Replace
        if cell_index < 0 or cell_index >= len(cells):
            return ToolResult(success=False, output="", error=f"Cell index {cell_index} out of range (0-{len(cells)-1})")

        cells[cell_index] = new_cell
        nb_path.write_text(json.dumps(nb, indent=1) + "\n")
        return ToolResult(success=True, output=f"Replaced cell {cell_index} with {cell_type} cell in {path_str}")
