"""
Tool permission hooks.

Ports: hooks/toolPermission/PermissionContext.ts,
       hooks/toolPermission/handlers/coordinatorHandler.ts,
       hooks/toolPermission/handlers/interactiveHandler.ts,
       hooks/toolPermission/handlers/swarmWorkerHandler.ts,
       hooks/toolPermission/permissionLogging.ts
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from .state_hooks import Signal, EventEmitter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Permission levels
# ---------------------------------------------------------------------------

class PermissionLevel(str, Enum):
    ALLOW     = "allow"
    DENY      = "deny"
    ASK       = "ask"           # Prompt the user
    ALLOW_ONCE = "allow_once"   # Allow this invocation only


@dataclass
class PermissionDecision:
    level: PermissionLevel
    reason: str = ""
    remember: bool = False      # If True, persist this decision


@dataclass
class ToolPermissionRequest:
    tool_name: str
    tool_input: dict
    tool_use_id: str
    session_id: str = ""
    risk_level: str = "low"     # "low" | "medium" | "high"
    description: str = ""


# ---------------------------------------------------------------------------
# Permission context
# ---------------------------------------------------------------------------

class PermissionContext:
    """
    Global permission context for tool execution.

    Ports: hooks/toolPermission/PermissionContext.ts
    """

    def __init__(self):
        self._rules: dict[str, PermissionLevel] = {}  # tool_name → decision
        self._emitter = EventEmitter()
        self.mode = Signal("default")   # "default" | "bypassPermissions" | "auto"

    def set_mode(self, mode: str) -> None:
        """Set permission mode: default, bypassPermissions, auto."""
        self.mode.set(mode)

    def add_rule(self, tool_name: str, level: PermissionLevel) -> None:
        """Add a persistent permission rule for a tool."""
        self._rules[tool_name] = level
        self._emitter.emit("rule_changed", tool_name, level)

    def remove_rule(self, tool_name: str) -> None:
        self._rules.pop(tool_name, None)

    def get_rule(self, tool_name: str) -> PermissionLevel | None:
        return self._rules.get(tool_name)

    def check(self, request: ToolPermissionRequest) -> PermissionDecision:
        """
        Check permission for a tool request.

        In bypass mode: always allow.
        In auto mode: allow low-risk tools, ask for high-risk.
        In default mode: respect rules, default to ask.
        """
        mode = self.mode.get()

        if mode == "bypassPermissions":
            return PermissionDecision(PermissionLevel.ALLOW, reason="bypass mode")

        # Check explicit rules
        rule = self.get_rule(request.tool_name)
        if rule is not None:
            return PermissionDecision(rule, reason="explicit rule")

        # Auto mode logic
        if mode == "auto":
            if request.risk_level == "high":
                return PermissionDecision(PermissionLevel.ASK, reason="high-risk tool in auto mode")
            return PermissionDecision(PermissionLevel.ALLOW, reason="auto mode")

        # Default: ask for anything destructive, allow reads
        safe_tools = {"bash", "read_file", "list_files", "glob", "grep", "web_search", "web_fetch"}
        if request.tool_name.lower() in safe_tools:
            return PermissionDecision(PermissionLevel.ALLOW, reason="safe tool")

        return PermissionDecision(PermissionLevel.ASK, reason="default policy")

    def on_rule_changed(self, handler: Callable) -> Callable[[], None]:
        return self._emitter.on("rule_changed", handler)


# ---------------------------------------------------------------------------
# Handler implementations
# ---------------------------------------------------------------------------

class InteractivePermissionHandler:
    """
    Interactive (TTY) permission handler — prompts the user.

    Ports: hooks/toolPermission/handlers/interactiveHandler.ts
    """

    def __init__(self, context: PermissionContext):
        self.context = context

    def handle(self, request: ToolPermissionRequest) -> PermissionDecision:
        """Prompt the user for permission interactively."""
        decision = self.context.check(request)

        if decision.level != PermissionLevel.ASK:
            _log_permission(request, decision)
            return decision

        # Prompt
        prompt = (
            f"\n  Tool: {request.tool_name}\n"
            f"  {request.description or 'Requesting tool access'}\n\n"
            f"  Allow? [y/n/a(lways)] "
        )

        try:
            response = input(prompt).strip().lower()
        except (EOFError, KeyboardInterrupt):
            decision = PermissionDecision(PermissionLevel.DENY, reason="user cancelled")
            _log_permission(request, decision)
            return decision

        if response in ("y", "yes"):
            decision = PermissionDecision(PermissionLevel.ALLOW_ONCE, reason="user approved")
        elif response in ("a", "always"):
            decision = PermissionDecision(PermissionLevel.ALLOW, reason="user approved (always)", remember=True)
            self.context.add_rule(request.tool_name, PermissionLevel.ALLOW)
        else:
            decision = PermissionDecision(PermissionLevel.DENY, reason="user denied")

        _log_permission(request, decision)
        return decision


class CoordinatorPermissionHandler:
    """
    Coordinator agent permission handler — escalates to coordinator.

    Ports: hooks/toolPermission/handlers/coordinatorHandler.ts
    """

    def __init__(self, context: PermissionContext, escalate: Callable | None = None):
        self.context = context
        self._escalate = escalate or (lambda req: PermissionDecision(PermissionLevel.ALLOW))

    def handle(self, request: ToolPermissionRequest) -> PermissionDecision:
        decision = self.context.check(request)
        if decision.level == PermissionLevel.ASK:
            decision = self._escalate(request)
        _log_permission(request, decision)
        return decision


class SwarmWorkerPermissionHandler:
    """
    Swarm worker permission handler — consult coordinator.

    Ports: hooks/toolPermission/handlers/swarmWorkerHandler.ts
    """

    def __init__(self, context: PermissionContext, coordinator_fn: Callable | None = None):
        self.context = context
        self._coordinator = coordinator_fn

    def handle(self, request: ToolPermissionRequest) -> PermissionDecision:
        decision = self.context.check(request)

        if decision.level == PermissionLevel.ASK and self._coordinator:
            try:
                decision = self._coordinator(request)
            except Exception as e:
                logger.warning(f"Coordinator permission check failed: {e}")
                decision = PermissionDecision(PermissionLevel.DENY, reason="coordinator unavailable")

        _log_permission(request, decision)
        return decision


# ---------------------------------------------------------------------------
# Permission logging
# ---------------------------------------------------------------------------

def _log_permission(request: ToolPermissionRequest, decision: PermissionDecision) -> None:
    """Log a permission decision."""
    level = decision.level
    if level == PermissionLevel.DENY:
        logger.warning(
            f"Permission DENIED: {request.tool_name} — {decision.reason}"
        )
    elif level == PermissionLevel.ASK:
        logger.info(f"Permission ASK: {request.tool_name}")
    else:
        logger.debug(
            f"Permission {level.value.upper()}: {request.tool_name} — {decision.reason}"
        )


# ---------------------------------------------------------------------------
# Global permission context
# ---------------------------------------------------------------------------

_global_context = PermissionContext()


def get_permission_context() -> PermissionContext:
    """Get the global permission context."""
    return _global_context


__all__ = [
    "PermissionLevel",
    "PermissionDecision",
    "ToolPermissionRequest",
    "PermissionContext",
    "InteractivePermissionHandler",
    "CoordinatorPermissionHandler",
    "SwarmWorkerPermissionHandler",
    "get_permission_context",
]
