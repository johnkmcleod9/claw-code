"""
Python skills subsystem — ported from 20 archived TypeScript modules.

Provides full skill loading, discovery, matching, execution pipeline,
caching, registry, validation, rendering, and lifecycle management:

Modules:
- ``types``         Core type definitions (SkillMatch, SkillResult, SkillEvent, ...)
- ``loader``        Scan skill directories, list/resolve/search skills
- ``bundled``       8 built-in skills (debug, verify, remember, simplify, stuck, ...)
- ``mcp``           MCP tool wrapper, skill builder, @mcp_tool decorator
- ``discovery``     Skill index builder, incremental refresh, inode tracking
- ``matcher``       Token-based skill matcher with scoring
- ``executor``      Skill execution pipeline, pre/post hooks
- ``cache``         LRU + persistent skill cache
- ``pipeline``      End-to-end orchestration: match → load → execute → inject
- ``registry``      Session-scoped skill registry (thread-safe)
- ``validator``     Structure/security validation for skill files
- ``renderer``      Terminal-friendly formatters for skills and matches
- ``watcher``       Polling-based skill directory watcher
- ``installer``     Install/uninstall/backup skill files
- ``context``       System-prompt injection planning
- ``events``        Publish/subscribe event bus for skill lifecycle events
- ``permissions``   Policy-based skill access control (allowlist/blocklist)
- ``telemetry``     Usage tracking and analytics
- ``remote``        Fetch skills from HTTP registries
- ``composer``      Combine skills into named compositions
- ``template``      ``{{variable}}`` substitution in skill content
- ``cli_commands``  /skills CLI command handlers
- ``error_handler`` Skill-specific exceptions and recovery strategies
"""
from __future__ import annotations

from pathlib import Path as _Path
import json as _json

# ── Archive metadata ──────────────────────────────────────────────────────
_SNAPSHOT_PATH = _Path(__file__).resolve().parent.parent / "reference_data" / "subsystems" / "skills.json"
_SNAPSHOT = _json.loads(_SNAPSHOT_PATH.read_text())

ARCHIVE_NAME = _SNAPSHOT["archive_name"]
MODULE_COUNT = _SNAPSHOT["module_count"]
SAMPLE_FILES = tuple(_SNAPSHOT["sample_files"])
PORTING_NOTE = (
    f"Ported Python package for '{ARCHIVE_NAME}' — "
    f"{MODULE_COUNT} archived TypeScript modules → 20 Python modules."
)

# ── Types ─────────────────────────────────────────────────────────────────
from .types import (
    SkillSource,
    SkillStatus,
    SkillMatch,
    SkillResult,
    SkillEvent,
)

# ── Loader ────────────────────────────────────────────────────────────────
from .loader import (
    Skill,
    find_skill_dirs,
    scan_skill_dir,
    list_skills,
    resolve_skill,
    search_skills,
)

# ── Bundled ───────────────────────────────────────────────────────────────
from .bundled import get_bundled_skill, list_bundled_skills

# ── MCP ───────────────────────────────────────────────────────────────────
from .mcp import (
    MCPSkill,
    MCPSkillTool,
    build_mcp_skill,
    extract_tools_from_module,
    mcp_tool,
)

# ── Discovery ─────────────────────────────────────────────────────────────
from .discovery import (
    SkillIndex,
    SkillIndexEntry,
    build_skill_index,
    refresh_skill_index,
    iter_skills_from_index,
)

# ── Matcher ───────────────────────────────────────────────────────────────
from .matcher import (
    match_skills,
    best_skill_match,
    rank_skills_for_intent,
)

# ── Executor ──────────────────────────────────────────────────────────────
from .executor import (
    SkillExecutionContext,
    execute_skill,
    run_skill_by_name,
    inject_skill_into_system_prompt,
    register_pre_hook,
    register_post_hook,
)

# ── Cache ─────────────────────────────────────────────────────────────────
from .cache import (
    CacheEntry,
    SkillCache,
    PersistentSkillCache,
    get_default_cache,
    reset_default_cache,
)

# ── Pipeline ──────────────────────────────────────────────────────────────
from .pipeline import (
    PipelineRequest,
    PipelineResponse,
    SkillPipeline,
    run_skill_pipeline,
)

# ── Registry ──────────────────────────────────────────────────────────────
from .registry import (
    SkillRegistry,
    RegistryStats,
    get_default_registry,
    reset_default_registry,
)

# ── Validator ─────────────────────────────────────────────────────────────
from .validator import (
    ValidationResult,
    validate_skill,
    validate_skill_file,
    validate_skills_dir,
)

# ── Renderer ──────────────────────────────────────────────────────────────
from .renderer import (
    format_skill_one_line,
    format_skill_detail,
    format_skill_list,
    format_skill_matches,
    format_injection_block,
)

# ── Watcher ───────────────────────────────────────────────────────────────
from .watcher import SkillWatcher

# ── Installer ─────────────────────────────────────────────────────────────
from .installer import (
    InstallResult,
    install_skill,
    uninstall_skill,
    list_installed_skills,
    backup_skill,
)

# ── Context injection ─────────────────────────────────────────────────────
from .context import (
    InjectionPlan,
    plan_injection,
    build_injection_block,
    inject_skills_into_system,
)

# ── Events ────────────────────────────────────────────────────────────────
from .events import (
    SkillEventBus,
    get_event_bus,
    emit_skill_event,
)

# ── Permissions ───────────────────────────────────────────────────────────
from .permissions import (
    SkillPermission,
    SkillPolicy,
    SkillGuard,
)

# ── Telemetry ─────────────────────────────────────────────────────────────
from .telemetry import (
    SkillUsageRecord,
    SkillTelemetry,
)

# ── Remote ────────────────────────────────────────────────────────────────
from .remote import (
    RemoteSkillDescriptor,
    RemoteSkillProvider,
)

# ── Composer ──────────────────────────────────────────────────────────────
from .composer import (
    SkillComposition,
    SkillComposer,
    default_composer,
)

# ── Template ──────────────────────────────────────────────────────────────
from .template import (
    TemplateResult,
    render_skill_template,
    extract_template_variables,
    render_template_string,
)

# ── CLI commands ──────────────────────────────────────────────────────────
from .cli_commands import dispatch_skill_command

# ── Error handling ────────────────────────────────────────────────────────
from .error_handler import (
    SkillError,
    SkillNotFoundError,
    SkillLoadError,
    SkillValidationError,
    SkillExecutionError,
    SkillPermissionError,
    SkillTimeoutError,
    suggest_recovery,
    format_skill_error,
)

__all__ = [
    # archive metadata
    "ARCHIVE_NAME", "MODULE_COUNT", "SAMPLE_FILES", "PORTING_NOTE",
    # types
    "SkillSource", "SkillStatus", "SkillMatch", "SkillResult", "SkillEvent",
    # loader
    "Skill", "find_skill_dirs", "scan_skill_dir", "list_skills", "resolve_skill", "search_skills",
    # bundled
    "get_bundled_skill", "list_bundled_skills",
    # mcp
    "MCPSkill", "MCPSkillTool", "build_mcp_skill", "extract_tools_from_module", "mcp_tool",
    # discovery
    "SkillIndex", "SkillIndexEntry", "build_skill_index", "refresh_skill_index", "iter_skills_from_index",
    # matcher
    "match_skills", "best_skill_match", "rank_skills_for_intent",
    # executor
    "SkillExecutionContext", "execute_skill", "run_skill_by_name",
    "inject_skill_into_system_prompt", "register_pre_hook", "register_post_hook",
    # cache
    "CacheEntry", "SkillCache", "PersistentSkillCache", "get_default_cache", "reset_default_cache",
    # pipeline
    "PipelineRequest", "PipelineResponse", "SkillPipeline", "run_skill_pipeline",
    # registry
    "SkillRegistry", "RegistryStats", "get_default_registry", "reset_default_registry",
    # validator
    "ValidationResult", "validate_skill", "validate_skill_file", "validate_skills_dir",
    # renderer
    "format_skill_one_line", "format_skill_detail", "format_skill_list",
    "format_skill_matches", "format_injection_block",
    # watcher
    "SkillWatcher",
    # installer
    "InstallResult", "install_skill", "uninstall_skill", "list_installed_skills", "backup_skill",
    # context
    "InjectionPlan", "plan_injection", "build_injection_block", "inject_skills_into_system",
    # events
    "SkillEventBus", "get_event_bus", "emit_skill_event",
    # permissions
    "SkillPermission", "SkillPolicy", "SkillGuard",
    # telemetry
    "SkillUsageRecord", "SkillTelemetry",
    # remote
    "RemoteSkillDescriptor", "RemoteSkillProvider",
    # composer
    "SkillComposition", "SkillComposer", "default_composer",
    # template
    "TemplateResult", "render_skill_template", "extract_template_variables", "render_template_string",
    # cli_commands
    "dispatch_skill_command",
    # error_handler
    "SkillError", "SkillNotFoundError", "SkillLoadError", "SkillValidationError",
    "SkillExecutionError", "SkillPermissionError", "SkillTimeoutError",
    "suggest_recovery", "format_skill_error",
]
