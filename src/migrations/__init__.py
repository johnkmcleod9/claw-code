"""
Configuration and settings migration framework.

Ports: migrations/*.ts — 11 migration scripts

Migration naming convention (from TS source):
- migrateAutoUpdatesToSettings
- migrateBypassPermissionsAcceptedToSettings
- migrateEnableAllProjectMcpServersToSettings
- migrateFennecToOpus
- migrateLegacyOpusToCurrent
- migrateOpusToOpus1m
- migrateReplBridgeEnabledToRemoteControlAtStartup
- migrateSonnet1mToSonnet45
- migrateSonnet45ToSonnet46
- resetAutoModeOptInForDefaultOffer
- resetProToOpusDefault
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Migration record
# ---------------------------------------------------------------------------

@dataclass
class Migration:
    """A single migration step."""
    id: str
    description: str
    from_version: str
    to_version: str
    applied_at: float | None = None
    rolled_back_at: float | None = None

    @property
    def is_applied(self) -> bool:
        return self.applied_at is not None

    @property
    def is_rolled_back(self) -> bool:
        return self.rolled_back_at is not None


# ---------------------------------------------------------------------------
# Migration runner
# ---------------------------------------------------------------------------

MIGRATION_LOG_PATH = Path.home() / ".claw" / "migrations.json"


class MigrationRunner:
    """
    Runs sequential configuration migrations with rollback support.

    Ports: migration framework (conceptual)
    """

    def __init__(self, config_dir: Path | None = None) -> None:
        self._config_dir = config_dir or (Path.home() / ".claw")
        self._applied: list[Migration] = self._load_log()
        self._migration_fn: dict[str, callable] = {}

    def _load_log(self) -> list[Migration]:
        if not MIGRATION_LOG_PATH.exists():
            return []
        try:
            raw = json.loads(MIGRATION_LOG_PATH.read_text())
            return [Migration(**m) for m in raw]
        except Exception:
            return []

    def _save_log(self) -> None:
        MIGRATION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        MIGRATION_LOG_PATH.write_text(
            json.dumps([m.__dict__ for m in self._applied], indent=2)
        )

    def register(self, migration_id: str, fn: callable, description: str = "") -> None:
        """Register a named migration function."""
        self._migration_fn[migration_id] = fn

    def is_applied(self, migration_id: str) -> bool:
        return any(m.id == migration_id for m in self._applied)

    def apply(self, migration_id: str) -> bool:
        """
        Run a migration if not yet applied.

        Returns True if applied (or already applied), False on failure.
        """
        if self.is_applied(migration_id):
            return True

        fn = self._migration_fn.get(migration_id)
        if fn is None:
            return False

        try:
            fn()
            import time
            migration = Migration(
                id=migration_id,
                description=getattr(fn, "__doc__", "") or migration_id,
                from_version="",
                to_version="",
                applied_at=time.time(),
            )
            self._applied.append(migration)
            self._save_log()
            return True
        except Exception:
            return False

    def apply_all(self) -> int:
        """Apply all registered migrations that are not yet applied."""
        count = 0
        for mid in self._migration_fn:
            if self.apply(mid):
                count += 1
        return count

    def rollback(self, migration_id: str) -> bool:
        """Remove a migration from the log (does not undo the changes)."""
        before = len(self._applied)
        self._applied = [m for m in self._applied if m.id != migration_id]
        if len(self._applied) < before:
            self._save_log()
            return True
        return False

    def list_applied(self) -> list[Migration]:
        return list(self._applied)


# ---------------------------------------------------------------------------
# Concrete migrations (representative examples)
# ---------------------------------------------------------------------------

def _backup(path: Path) -> None:
    if path.exists():
        shutil.copy2(path, path.with_suffix(".bak"))


def migrate_repl_bridge_enabled_to_remote() -> None:
    """
    Migrate repl.bridge.enabled → remote.controlAtStartup.

    Ports: migrateReplBridgeEnabledToRemoteControlAtStartup.ts
    """
    config_path = Path.home() / ".claw" / "config.json"
    if not config_path.exists():
        return

    _backup(config_path)
    config = json.loads(config_path.read_text())

    repl = config.get("repl", {})
    if repl.get("bridge", {}).get("enabled"):
        config.setdefault("remote", {})["controlAtStartup"] = True
        del repl["bridge"]["enabled"]
        config["repl"] = repl

    config_path.write_text(json.dumps(config, indent=2))


def migrate_bypass_permissions_to_settings() -> None:
    """
    Migrate bypassPermissionsAccepted → settings.permissions.bypassAccepted.

    Ports: migrateBypassPermissionsAcceptedToSettings.ts
    """
    config_path = Path.home() / ".claw" / "config.json"
    if not config_path.exists():
        return

    _backup(config_path)
    config = json.loads(config_path.read_text())

    bp = config.pop("bypassPermissionsAccepted", None)
    if bp is not None:
        config.setdefault("settings", {}).setdefault("permissions", {})["bypassAccepted"] = bp

    config_path.write_text(json.dumps(config, indent=2))


def migrate_auto_updates_to_settings() -> None:
    """
    Migrate autoUpdates → settings.autoUpdate.

    Ports: migrateAutoUpdatesToSettings.ts
    """
    config_path = Path.home() / ".claw" / "config.json"
    if not config_path.exists():
        return

    _backup(config_path)
    config = json.loads(config_path.read_text())

    au = config.pop("autoUpdates", None)
    if au is not None:
        config.setdefault("settings", {})["autoUpdate"] = au

    config_path.write_text(json.dumps(config, indent=2))


# ---------------------------------------------------------------------------
# Module-level runner with pre-registered migrations
# ---------------------------------------------------------------------------

_runner: MigrationRunner | None = None


def get_runner() -> MigrationRunner:
    global _runner
    if _runner is None:
        _runner = MigrationRunner()
        _runner.register("migrateReplBridgeEnabledToRemoteControlAtStartup",
                         migrate_repl_bridge_enabled_to_remote)
        _runner.register("migrateBypassPermissionsAcceptedToSettings",
                         migrate_bypass_permissions_to_settings)
        _runner.register("migrateAutoUpdatesToSettings",
                         migrate_auto_updates_to_settings)
    return _runner


def run_all_migrations() -> int:
    return get_runner().apply_all()


__all__ = [
    "Migration",
    "MigrationRunner",
    "get_runner",
    "migrate_auto_updates_to_settings",
    "migrate_bypass_permissions_to_settings",
    "migrate_repl_bridge_enabled_to_remote",
    "run_all_migrations",
]
