"""
CLI command handlers.

Ports: cli/handlers/agents.ts, cli/handlers/auth.ts,
       cli/handlers/autoMode.ts, cli/handlers/mcp.tsx,
       cli/handlers/plugins.ts, cli/handlers/util.tsx
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Handler base
# ---------------------------------------------------------------------------

@dataclass
class HandlerResult:
    """Uniform result type returned from all CLI handlers."""
    success: bool
    message: str = ""
    data: Any = None
    exit_code: int = 0

    @classmethod
    def ok(cls, message: str = "", data: Any = None) -> "HandlerResult":
        return cls(success=True, message=message, data=data)

    @classmethod
    def fail(cls, message: str, exit_code: int = 1) -> "HandlerResult":
        return cls(success=False, message=message, exit_code=exit_code)


Handler = Callable[..., HandlerResult]


# ---------------------------------------------------------------------------
# Auth handler (cli/handlers/auth.ts)
# ---------------------------------------------------------------------------

def handle_auth_login(provider: str, token: str | None = None) -> HandlerResult:
    """
    Persist an API credential for *provider*.

    In the full implementation this launches a browser OAuth flow;
    here we accept an explicit token for non-interactive / scripted use.
    """
    if not provider:
        return HandlerResult.fail("--provider is required")

    env_key = f"CLAW_{provider.upper()}_TOKEN"
    if token:
        os.environ[env_key] = token
        return HandlerResult.ok(f"Token for {provider} set (in-process only)")

    existing = os.environ.get(env_key)
    if existing:
        return HandlerResult.ok(f"Already authenticated with {provider}")

    return HandlerResult.fail(
        f"No token found for {provider}. "
        f"Set {env_key} env var or pass --token."
    )


def handle_auth_logout(provider: str) -> HandlerResult:
    env_key = f"CLAW_{provider.upper()}_TOKEN"
    if env_key in os.environ:
        del os.environ[env_key]
        return HandlerResult.ok(f"Logged out from {provider}")
    return HandlerResult.ok(f"Was not logged in to {provider}")


def handle_auth_status() -> HandlerResult:
    """List all CLAW_*_TOKEN env vars that are currently set."""
    tokens = {
        k: "***"
        for k in os.environ
        if k.startswith("CLAW_") and k.endswith("_TOKEN")
    }
    if tokens:
        providers = [k.replace("CLAW_", "").replace("_TOKEN", "").lower() for k in tokens]
        return HandlerResult.ok(
            f"Authenticated providers: {', '.join(providers)}",
            data={"providers": providers},
        )
    return HandlerResult.ok("No providers authenticated", data={"providers": []})


# ---------------------------------------------------------------------------
# Auto-mode handler (cli/handlers/autoMode.ts)
# ---------------------------------------------------------------------------

def handle_auto_mode(
    enabled: bool,
    approval_mode: str = "on",
    write_ok: bool = False,
) -> HandlerResult:
    """
    Toggle auto/non-interactive mode.

    Ports: cli/handlers/autoMode.ts
    """
    try:
        from src.state import AppStateStore, ApprovalMode

        store = AppStateStore.get_instance()
        mode = ApprovalMode.OFF if enabled else ApprovalMode.ON
        store.set_approval_mode(mode)
        label = "auto (no approvals)" if enabled else "interactive (approvals on)"
        return HandlerResult.ok(f"Approval mode set to {label}")
    except ImportError:
        return HandlerResult.fail("State subsystem unavailable")


# ---------------------------------------------------------------------------
# MCP handler (cli/handlers/mcp.tsx)
# ---------------------------------------------------------------------------

@dataclass
class MCPServerEntry:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


def handle_mcp_list(servers: list[MCPServerEntry]) -> HandlerResult:
    if not servers:
        return HandlerResult.ok("No MCP servers configured", data=[])
    lines = [f"  • {s.name}: {s.command} {' '.join(s.args)}" for s in servers]
    return HandlerResult.ok("\n".join(["MCP servers:"] + lines), data=[s.name for s in servers])


def handle_mcp_add(
    name: str,
    command: str,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> HandlerResult:
    """Register a new MCP server (in-memory; persist via config in production)."""
    if not name or not command:
        return HandlerResult.fail("--name and --command are required")
    entry = MCPServerEntry(name=name, command=command, args=args or [], env=env or {})
    return HandlerResult.ok(f"MCP server {name!r} registered", data=entry)


# ---------------------------------------------------------------------------
# Plugins handler (cli/handlers/plugins.ts)
# ---------------------------------------------------------------------------

def handle_plugins_list(plugin_dir: str | None = None) -> HandlerResult:
    import os
    from pathlib import Path

    search_dirs = [Path(plugin_dir)] if plugin_dir else [
        Path.home() / ".claw" / "plugins",
        Path("/etc/claw/plugins"),
    ]
    found: list[str] = []
    for d in search_dirs:
        if d.is_dir():
            found.extend(str(p) for p in d.glob("*.py"))
    if found:
        return HandlerResult.ok(f"Found {len(found)} plugin(s)", data=found)
    return HandlerResult.ok("No plugins found", data=[])


# ---------------------------------------------------------------------------
# Utility handler (cli/handlers/util.tsx)
# ---------------------------------------------------------------------------

def handle_version() -> HandlerResult:
    try:
        from importlib.metadata import version
        v = version("claw-code")
    except Exception:
        v = "dev"
    return HandlerResult.ok(f"claw-code {v}", data={"version": v})


def handle_doctor() -> HandlerResult:
    """Basic environment check — ports util doctor command."""
    checks: list[dict[str, Any]] = []

    # Python version
    import sys
    py = sys.version_info
    checks.append({
        "name": "Python version",
        "ok": py >= (3, 10),
        "detail": f"{py.major}.{py.minor}.{py.micro}",
    })

    # Required env vars
    for var in ["ANTHROPIC_API_KEY"]:
        checks.append({
            "name": f"Env: {var}",
            "ok": bool(os.environ.get(var)),
            "detail": "set" if os.environ.get(var) else "missing",
        })

    all_ok = all(c["ok"] for c in checks)
    summary = "All checks passed" if all_ok else "Some checks failed"
    return HandlerResult(success=all_ok, message=summary, data=checks)


# ---------------------------------------------------------------------------
# Agents handler (cli/handlers/agents.ts)
# ---------------------------------------------------------------------------

def handle_agents_list() -> HandlerResult:
    """List running agent sessions (stub; real impl uses session store)."""
    try:
        from src.session_store import list_sessions
        sessions = list_sessions()
        return HandlerResult.ok(f"{len(sessions)} active session(s)", data=sessions)
    except (ImportError, Exception) as e:
        return HandlerResult.ok("Session store unavailable", data=[])


__all__ = [
    "HandlerResult",
    "MCPServerEntry",
    "handle_agents_list",
    "handle_auth_login",
    "handle_auth_logout",
    "handle_auth_status",
    "handle_auto_mode",
    "handle_doctor",
    "handle_mcp_add",
    "handle_mcp_list",
    "handle_plugins_list",
    "handle_version",
]
