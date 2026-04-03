"""
Python skills subsystem — ported from 20 archived TypeScript modules.

Provides skill loading, bundled skills, and MCP skill builders:

- ``loader``   Scan skill directories, list/resolve/search skills
- ``bundled``  8 built-in skills (debug, verify, remember, simplify, stuck, api-review, security, update-config)
- ``mcp``      MCP tool wrapper, skill builder, @mcp_tool decorator
"""
from __future__ import annotations

from .bundled import get_bundled_skill, list_bundled_skills
from .loader import (
    Skill,
    find_skill_dirs,
    list_skills,
    resolve_skill,
    scan_skill_dir,
    search_skills,
)
from .mcp import (
    MCPSkill,
    MCPSkillTool,
    build_mcp_skill,
    extract_tools_from_module,
    mcp_tool,
)

# Backward-compat shim
from pathlib import Path as _Path
import json as _json

_SNAPSHOT_PATH = _Path(__file__).resolve().parent.parent / "reference_data" / "subsystems" / "skills.json"
_SNAPSHOT = _json.loads(_SNAPSHOT_PATH.read_text())

ARCHIVE_NAME = _SNAPSHOT["archive_name"]
MODULE_COUNT = _SNAPSHOT["module_count"]
SAMPLE_FILES = tuple(_SNAPSHOT["sample_files"])
PORTING_NOTE = (
    f"Ported Python package for '{ARCHIVE_NAME}' — "
    f"{MODULE_COUNT} archived TypeScript modules → 3 Python modules."
)

__all__ = [
    # loader
    "Skill",
    "find_skill_dirs",
    "list_skills",
    "resolve_skill",
    "scan_skill_dir",
    "search_skills",
    # bundled
    "get_bundled_skill",
    "list_bundled_skills",
    # mcp
    "MCPSkill",
    "MCPSkillTool",
    "build_mcp_skill",
    "extract_tools_from_module",
    "mcp_tool",
    # legacy archive metadata
    "ARCHIVE_NAME",
    "MODULE_COUNT",
    "PORTING_NOTE",
    "SAMPLE_FILES",
]
