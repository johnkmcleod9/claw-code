"""
Bridge configuration.

Ports: bridge/bridgeConfig.ts, bridge/envLessBridgeConfig.ts,
       bridge/pollConfig.ts, bridge/pollConfigDefaults.ts,
       bridge/bridgeEnabled.ts
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Poll defaults (bridge/pollConfigDefaults.ts)
# ---------------------------------------------------------------------------

DEFAULT_POLL_INTERVAL_MS = 1_000      # 1 second
DEFAULT_POLL_TIMEOUT_MS = 30_000      # 30 seconds
DEFAULT_RECONNECT_DELAY_MS = 2_000
DEFAULT_MAX_RECONNECT_ATTEMPTS = 10

# ---------------------------------------------------------------------------
# Bridge config (bridge/bridgeConfig.ts)
# ---------------------------------------------------------------------------

@dataclass
class BridgeConfig:
    """
    Configuration for the IDE bridge.

    The bridge connects the CLI to VS Code / Cursor / Zed extensions.
    """
    enabled: bool = False
    host: str = "localhost"
    port: int = 7777
    base_url: str = ""
    api_key: str = ""
    poll_interval_ms: int = DEFAULT_POLL_INTERVAL_MS
    poll_timeout_ms: int = DEFAULT_POLL_TIMEOUT_MS
    reconnect_delay_ms: int = DEFAULT_RECONNECT_DELAY_MS
    max_reconnect_attempts: int = DEFAULT_MAX_RECONNECT_ATTEMPTS
    debug: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.base_url:
            self.base_url = f"http://{self.host}:{self.port}"

    @property
    def ws_url(self) -> str:
        return self.base_url.replace("http://", "ws://").replace("https://", "wss://")

    @property
    def api_url(self) -> str:
        return self.base_url.rstrip("/") + "/api"


def load_bridge_config_from_env() -> BridgeConfig:
    """
    Build a BridgeConfig from environment variables.

    Ports: bridge/envLessBridgeConfig.ts (env-var driven variant)
    """
    enabled = os.environ.get("CLAW_BRIDGE_ENABLED", "").lower() in ("1", "true", "yes")
    host = os.environ.get("CLAW_BRIDGE_HOST", "localhost")
    port = int(os.environ.get("CLAW_BRIDGE_PORT", "7777"))
    api_key = os.environ.get("CLAW_BRIDGE_API_KEY", "")
    debug = os.environ.get("CLAW_BRIDGE_DEBUG", "").lower() in ("1", "true")
    base_url = os.environ.get("CLAW_BRIDGE_URL", "")
    return BridgeConfig(
        enabled=enabled,
        host=host,
        port=port,
        base_url=base_url,
        api_key=api_key,
        debug=debug,
    )


def is_bridge_enabled(config: BridgeConfig | None = None) -> bool:
    """Return True if the bridge is configured and enabled."""
    cfg = config or load_bridge_config_from_env()
    return cfg.enabled


__all__ = [
    "BridgeConfig",
    "DEFAULT_MAX_RECONNECT_ATTEMPTS",
    "DEFAULT_POLL_INTERVAL_MS",
    "DEFAULT_POLL_TIMEOUT_MS",
    "DEFAULT_RECONNECT_DELAY_MS",
    "is_bridge_enabled",
    "load_bridge_config_from_env",
]
