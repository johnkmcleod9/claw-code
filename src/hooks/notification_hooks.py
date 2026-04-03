"""
Notification hooks for status messages and alerts.

Ports: hooks/notifs/useStartupNotification.ts,
       hooks/notifs/useRateLimitWarningNotification.tsx,
       hooks/notifs/useModelMigrationNotifications.tsx,
       hooks/notifs/useMcpConnectivityStatus.tsx,
       hooks/notifs/useNpmDeprecationNotification.tsx,
       hooks/notifs/usePluginAutoupdateNotification.tsx,
       hooks/notifs/useSettingsErrors.tsx,
       hooks/notifs/useIDEStatusIndicator.tsx
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable

from .state_hooks import Signal, EventEmitter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Notification data model
# ---------------------------------------------------------------------------

class NotificationLevel(str, Enum):
    INFO    = "info"
    WARNING = "warning"
    ERROR   = "error"
    SUCCESS = "success"


@dataclass
class Notification:
    id: str
    level: NotificationLevel
    title: str
    message: str = ""
    action_label: str = ""
    action_fn: Callable | None = None
    auto_dismiss_s: float | None = None
    created_at: datetime = field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# Notification manager
# ---------------------------------------------------------------------------

class NotificationManager:
    """
    Central notification manager — collects and dispatches notifications.

    Python equivalent of the various useNotif hooks combined.
    """

    def __init__(self):
        self._notifications: list[Notification] = []
        self._emitter = EventEmitter()
        self._id_counter = 0

    def _next_id(self) -> str:
        self._id_counter += 1
        return f"notif-{self._id_counter}"

    def push(self, notif: Notification) -> str:
        """Add a notification. Returns its ID."""
        self._notifications.append(notif)
        self._emitter.emit("added", notif)
        logger.debug(f"Notification: [{notif.level.value}] {notif.title}")
        return notif.id

    def info(self, title: str, message: str = "", **kwargs) -> str:
        return self.push(Notification(
            id=self._next_id(),
            level=NotificationLevel.INFO,
            title=title,
            message=message,
            **kwargs,
        ))

    def warning(self, title: str, message: str = "", **kwargs) -> str:
        return self.push(Notification(
            id=self._next_id(),
            level=NotificationLevel.WARNING,
            title=title,
            message=message,
            **kwargs,
        ))

    def error(self, title: str, message: str = "", **kwargs) -> str:
        return self.push(Notification(
            id=self._next_id(),
            level=NotificationLevel.ERROR,
            title=title,
            message=message,
            **kwargs,
        ))

    def success(self, title: str, message: str = "", **kwargs) -> str:
        return self.push(Notification(
            id=self._next_id(),
            level=NotificationLevel.SUCCESS,
            title=title,
            message=message,
            **kwargs,
        ))

    def dismiss(self, notif_id: str) -> None:
        before = len(self._notifications)
        self._notifications = [n for n in self._notifications if n.id != notif_id]
        if len(self._notifications) < before:
            self._emitter.emit("dismissed", notif_id)

    def clear(self) -> None:
        self._notifications.clear()
        self._emitter.emit("cleared")

    def all(self) -> list[Notification]:
        return list(self._notifications)

    def on_added(self, handler: Callable[[Notification], None]) -> Callable[[], None]:
        return self._emitter.on("added", handler)

    def on_dismissed(self, handler: Callable[[str], None]) -> Callable[[], None]:
        return self._emitter.on("dismissed", handler)


# ---------------------------------------------------------------------------
# Specific notification hooks (ported as functions on the manager)
# ---------------------------------------------------------------------------

def notify_startup(
    manager: NotificationManager,
    version: str,
    model: str,
    mcp_error: str | None = None,
) -> None:
    """
    Send startup notifications.

    Ports: hooks/notifs/useStartupNotification.ts
    """
    if mcp_error:
        manager.warning(
            "MCP connection issue",
            message=mcp_error,
        )


def notify_rate_limit(
    manager: NotificationManager,
    retry_after_s: float,
    model: str = "",
) -> None:
    """
    Notify user of rate limit.

    Ports: hooks/notifs/useRateLimitWarningNotification.tsx
    """
    model_str = f" ({model})" if model else ""
    manager.warning(
        f"Rate limit hit{model_str}",
        message=f"Retrying in {retry_after_s:.0f}s…",
    )


def notify_model_migration(
    manager: NotificationManager,
    old_model: str,
    new_model: str,
) -> None:
    """
    Notify user of model migration.

    Ports: hooks/notifs/useModelMigrationNotifications.tsx
    """
    manager.info(
        "Model updated",
        message=f"{old_model} → {new_model}",
    )


def notify_mcp_connectivity(
    manager: NotificationManager,
    server_name: str,
    connected: bool,
    error: str = "",
) -> None:
    """
    Notify of MCP server connectivity change.

    Ports: hooks/notifs/useMcpConnectivityStatus.tsx
    """
    if connected:
        manager.success(f"MCP connected: {server_name}")
    else:
        manager.warning(
            f"MCP disconnected: {server_name}",
            message=error,
        )


def notify_settings_error(
    manager: NotificationManager,
    setting: str,
    error: str,
) -> None:
    """
    Notify of settings validation error.

    Ports: hooks/notifs/useSettingsErrors.tsx
    """
    manager.error(
        f"Settings error: {setting}",
        message=error,
    )


def notify_plugin_update(
    manager: NotificationManager,
    plugin: str,
    old_version: str,
    new_version: str,
) -> None:
    """
    Notify of plugin auto-update.

    Ports: hooks/notifs/usePluginAutoupdateNotification.tsx
    """
    manager.info(
        f"Plugin updated: {plugin}",
        message=f"{old_version} → {new_version}",
    )


# ---------------------------------------------------------------------------
# Global notification manager
# ---------------------------------------------------------------------------

_global_notifications = NotificationManager()


def get_notifications() -> NotificationManager:
    return _global_notifications


__all__ = [
    "NotificationLevel",
    "Notification",
    "NotificationManager",
    "notify_startup",
    "notify_rate_limit",
    "notify_model_migration",
    "notify_mcp_connectivity",
    "notify_settings_error",
    "notify_plugin_update",
    "get_notifications",
]
