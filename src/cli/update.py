"""
CLI self-update and version check utilities.

Ports: cli/update.ts
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Any


@dataclass
class VersionInfo:
    current: str
    latest: str | None = None
    update_available: bool = False
    changelog_url: str = ""


def get_current_version() -> str:
    """Return the installed package version."""
    try:
        from importlib.metadata import version
        return version("claw-code")
    except Exception:
        return "0.0.0-dev"


def check_for_update(
    registry_url: str = "https://pypi.org/pypi/claw-code/json",
    timeout: float = 5.0,
) -> VersionInfo:
    """
    Fetch the latest version from PyPI and compare to the installed version.

    Ports: cli/update.ts checkForUpdate()
    """
    current = get_current_version()

    try:
        import urllib.request
        with urllib.request.urlopen(registry_url, timeout=timeout) as resp:
            data: dict[str, Any] = json.loads(resp.read())
        latest = data.get("info", {}).get("version", current)
        update_available = _version_gt(latest, current)
        return VersionInfo(
            current=current,
            latest=latest,
            update_available=update_available,
            changelog_url=f"https://github.com/anthropics/claw-code/releases/tag/{latest}",
        )
    except Exception:
        return VersionInfo(current=current)


def _version_gt(a: str, b: str) -> bool:
    """Return True if version a > b (simple numeric comparison)."""
    def parts(v: str) -> tuple[int, ...]:
        try:
            return tuple(int(x) for x in v.split(".")[:3])
        except ValueError:
            return (0,)

    return parts(a) > parts(b)


def perform_update() -> bool:
    """
    Attempt a pip self-upgrade.

    Returns True if successful.
    """
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "claw-code"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


__all__ = [
    "VersionInfo",
    "check_for_update",
    "get_current_version",
    "perform_update",
]
