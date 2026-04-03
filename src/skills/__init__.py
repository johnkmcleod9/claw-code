"""
Python skills subsystem — ported from 20 archived TypeScript modules.

Provides full skill loading, matching, and execution pipeline:
- ``loader``     Skill directory scanning, listing, resolution, search
- ``bundled``    8 built-in skills (debug, verify, remember, simplify, stuck, api-review, security, update-config)
- ``mcp``        MCP tool wrapper, skill builder, @mcp_tool decorator
- ``cache``      TTL + LRU skill caching
- ``discovery``  Incremental skill index with mtime-based change detection
- ``types``      SkillMatch, SkillResult, SkillEvent, SkillSource, SkillStatus
- ``executor``   Skill execution with context injection and result formatting
- ``matcher``    Relevance scoring, auto-suggestion, skill injection
"""
from __future__ import annotations

import json
from pathlib import Path as _Path

# ── Metadata from archived TS snapshot ───────────────────────────────────────
_SNAPSHOT_PATH = _Path(__file__).resolve().parent.parent / "reference_data" / "subsystems" / "skills.json"
_SNAPSHOT = json.loads(_SNAPSHOT_PATH.read_text())
ARCHIVE_NAME = _SNAPSHOT["archive_name"]
MODULE_COUNT = _SNAPSHOT["module_count"]
SAMPLE_FILES = tuple(_SNAPSHOT["sample_files"])
PORTING_NOTE = (
    f"Ported Python package for '{ARCHIVE_NAME}' — "
    f"{MODULE_COUNT} archived TypeScript modules → 8 Python modules "
    f"(loader, bundled, mcp, cache, discovery, types, executor, matcher)."
)

# ── Loader ────────────────────────────────────────────────────────────────────
from .loader import (
    Skill,
    find_skill_dirs,
    list_skills,
    resolve_skill,
    scan_skill_dir,
    search_skills,
)

# ── Bundled ───────────────────────────────────────────────────────────────────
from .bundled import (
    get_bundled_skill,
    list_bundled_skills,
)

# ── MCP ───────────────────────────────────────────────────────────────────────
from .mcp import (
    MCPSkill,
    MCPSkillTool,
    build_mcp_skill,
    extract_tools_from_module,
    mcp_tool,
)

# ── Types ─────────────────────────────────────────────────────────────────────
from .types import (
    SkillSource,
    SkillStatus,
    SkillMatch,
    SkillResult,
    SkillEvent,
)

# ── Cache ─────────────────────────────────────────────────────────────────────
from .cache import CacheEntry

# ── Discovery ─────────────────────────────────────────────────────────────────
from .discovery import SkillIndex, SkillIndexEntry

# ── Executor ──────────────────────────────────────────────────────────────────
from .executor import (
    ExecutionContext,
    SkillExecutor,
    execute_skill,
    execute_skill_by_name,
    format_skill_result,
)

# ── Matcher ───────────────────────────────────────────────────────────────────
from .matcher import (
    ScoredSkillMatch,
    SkillMatcher,
    suggest_skills,
    auto_inject_skills,
    match_skills,
)

__all__ = [
    # metadata
    "ARCHIVE_NAME", "MODULE_COUNT", "PORTING_NOTE", "SAMPLE_FILES",
    # loader
    "Skill",
    "find_skill_dirs", "list_skills", "resolve_skill",
    "scan_skill_dir", "search_skills",
    # bundled
    "get_bundled_skill", "list_bundled_skills",
    # mcp
    "MCPSkill", "MCPSkillTool", "build_mcp_skill",
    "extract_tools_from_module", "mcp_tool",
    # types
    "SkillSource", "SkillStatus", "SkillMatch", "SkillResult", "SkillEvent",
    # cache
    "CacheEntry",
    # discovery
    "SkillIndex", "SkillIndexEntry",
    # executor
    "ExecutionContext", "SkillExecutor",
    "execute_skill", "execute_skill_by_name", "format_skill_result",
    # matcher
    "ScoredSkillMatch", "SkillMatcher",
    "suggest_skills", "auto_inject_skills", "match_skills",
]
