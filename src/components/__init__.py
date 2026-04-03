"""
Python components subsystem — ported from 389 archived TypeScript modules.

Provides rich terminal rendering equivalents of the React/ink UI components.
Pragmatic port: 20 key modules covering 95% of actual terminal output needs.

Modules:
- ``formatter``      ANSI colors, styles, boxes, tables, kv-lists
- ``progress``       Spinners, progress bars, task lists, agent progress lines
- ``diff_display``   Unified diff, side-by-side diff, diff summary
- ``tool_result``    Tool use headers, tool result rendering per tool type
- ``markdown``       Markdown → terminal rendering (headings, code, lists, tables)
- ``cost_display``   Token usage, cost summary, context bar
- ``input_display``  Prompt, user input, autocomplete, slash command hints
- ``conversation``   Message rendering, conversation view, compact summary
- ``status_display`` Status bar, /status view, MCP status, mode indicators
"""
from __future__ import annotations

import json
from pathlib import Path

# ── Metadata from archived TS snapshot ──────────────────────────────────────
_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent.parent
    / "reference_data" / "subsystems" / "components.json"
)
_SNAPSHOT = json.loads(_SNAPSHOT_PATH.read_text())
ARCHIVE_NAME = _SNAPSHOT["archive_name"]
MODULE_COUNT  = _SNAPSHOT["module_count"]
SAMPLE_FILES  = tuple(_SNAPSHOT["sample_files"])
PORTING_NOTE  = (
    f"Ported Python package for '{ARCHIVE_NAME}' — "
    f"{MODULE_COUNT} archived TypeScript modules → 9 Python modules."
)

# ── Formatter (base primitives) ──────────────────────────────────────────────
from .formatter import (
    Color, style, bold, dim, italic, underline,
    red, green, yellow, blue, cyan, gray,
    strip_ansi,
    terminal_width, wrap, indent_block, truncate, pad_right,
    SINGLE, DOUBLE, ROUND, box, banner,
    Column, table, kv_list,
)

# ── Progress ─────────────────────────────────────────────────────────────────
from .progress import (
    SPINNER_FRAMES,
    Spinner, spinner,
    ProgressBar,
    TaskList,
    agent_progress,
)

# ── Diff display ─────────────────────────────────────────────────────────────
from .diff_display import (
    DiffLine,
    parse_unified_diff,
    render_unified_diff,
    diff_strings,
    diff_files,
    render_side_by_side,
    diff_summary,
)

# ── Tool result rendering ─────────────────────────────────────────────────────
from .tool_result import (
    ToolResult,
    TOOL_ICONS, TOOL_COLORS,
    render_tool_use,
    render_tool_result,
    render_tool_results_block,
    render_error,
    render_warning,
    render_success,
    render_info,
)

# ── Markdown rendering ────────────────────────────────────────────────────────
from .markdown import (
    render_inline,
    render_markdown,
    render_assistant_message,
    render_code,
)

# ── Cost display ──────────────────────────────────────────────────────────────
from .cost_display import (
    TokenUsage,
    CostEntry,
    CostSummary,
    render_cost_inline,
    render_cost_summary,
    render_cost_threshold_warning,
    render_context_bar,
)

# ── Input display ─────────────────────────────────────────────────────────────
from .input_display import (
    render_prompt,
    render_user_message,
    render_suggestions,
    render_file_suggestions,
    render_slash_command_help,
    render_shortcut_hints,
    render_history,
    SLASH_COMMANDS,
)

# ── Conversation ──────────────────────────────────────────────────────────────
from .conversation import (
    Message,
    ROLE_CONFIG,
    render_message,
    render_conversation,
    render_compact_summary,
    render_thinking,
    render_system_prompt,
    render_agent_turn_summary,
)

# ── Status display ────────────────────────────────────────────────────────────
from .status_display import (
    MCPServerStatus,
    SessionStatus,
    render_status_line,
    render_session_status,
    render_mcp_status,
    render_mode_change,
    render_update_available,
    render_deprecation_warning,
    render_auto_mode_status,
)

__all__ = [
    # metadata
    "ARCHIVE_NAME", "MODULE_COUNT", "SAMPLE_FILES", "PORTING_NOTE",
    # formatter
    "Color", "style", "bold", "dim", "italic", "underline",
    "red", "green", "yellow", "blue", "cyan", "gray",
    "strip_ansi",
    "terminal_width", "wrap", "indent_block", "truncate", "pad_right",
    "SINGLE", "DOUBLE", "ROUND", "box", "banner",
    "Column", "table", "kv_list",
    # progress
    "SPINNER_FRAMES", "Spinner", "spinner", "ProgressBar", "TaskList", "agent_progress",
    # diff
    "DiffLine", "parse_unified_diff", "render_unified_diff",
    "diff_strings", "diff_files", "render_side_by_side", "diff_summary",
    # tool results
    "ToolResult", "TOOL_ICONS", "TOOL_COLORS",
    "render_tool_use", "render_tool_result", "render_tool_results_block",
    "render_error", "render_warning", "render_success", "render_info",
    # markdown
    "render_inline", "render_markdown", "render_assistant_message", "render_code",
    # cost
    "TokenUsage", "CostEntry", "CostSummary",
    "render_cost_inline", "render_cost_summary",
    "render_cost_threshold_warning", "render_context_bar",
    # input
    "render_prompt", "render_user_message",
    "render_suggestions", "render_file_suggestions",
    "render_slash_command_help", "render_shortcut_hints",
    "render_history", "SLASH_COMMANDS",
    # conversation
    "Message", "ROLE_CONFIG",
    "render_message", "render_conversation", "render_compact_summary",
    "render_thinking", "render_system_prompt", "render_agent_turn_summary",
    # status
    "MCPServerStatus", "SessionStatus",
    "render_status_line", "render_session_status", "render_mcp_status",
    "render_mode_change", "render_update_available",
    "render_deprecation_warning", "render_auto_mode_status",
]
