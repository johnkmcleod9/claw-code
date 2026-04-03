"""
Remote skill provider — fetch skills from a remote registry or URL.

Ports: skills/remoteSkills.ts, skills/skillFetcher.ts

Supports:
- HTTP GET of a raw .md skill file
- JSON registry endpoint returning a list of skill descriptors
- In-memory caching of fetched content
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from .loader import Skill
from .validator import validate_skill


@dataclass
class RemoteSkillDescriptor:
    """Metadata returned by a remote skill registry."""
    name: str
    description: str
    url: str
    version: str = "0.0.0"
    tags: list[str] = field(default_factory=list)


class RemoteSkillProvider:
    """
    Fetches skills from HTTP endpoints with simple TTL caching.

    Args:
        registry_url: URL to a JSON registry listing available skills.
        ttl_s: Cache TTL in seconds.
        timeout_s: HTTP request timeout.
    """

    def __init__(
        self,
        registry_url: str | None = None,
        ttl_s: float = 600.0,
        timeout_s: float = 10.0,
    ) -> None:
        self.registry_url = registry_url
        self.ttl_s = ttl_s
        self.timeout_s = timeout_s
        self._cache: dict[str, tuple[float, str]] = {}   # url → (fetched_at, content)
        self._registry_cache: tuple[float, list[RemoteSkillDescriptor]] | None = None

    def fetch_skill_content(self, url: str) -> str | None:
        """
        Fetch raw .md content from a URL (with TTL cache).

        Returns None on error.
        """
        cached = self._cache.get(url)
        if cached and (time.time() - cached[0]) < self.ttl_s:
            return cached[1]

        try:
            req = urllib.request.Request(
                url,
                headers={"Accept": "text/plain, text/markdown, */*"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                content = resp.read().decode("utf-8", errors="replace")
            self._cache[url] = (time.time(), content)
            return content
        except (urllib.error.URLError, OSError):
            return None

    def fetch_skill(self, descriptor: RemoteSkillDescriptor) -> Skill | None:
        """
        Fetch and build a Skill from a RemoteSkillDescriptor.

        Returns None if fetch or validation fails.
        """
        content = self.fetch_skill_content(descriptor.url)
        if not content:
            return None

        skill = Skill(
            name=descriptor.name,
            description=descriptor.description,
            content=content,
            source="remote",
            path=descriptor.url,
            tags=descriptor.tags,
        )

        vr = validate_skill(skill)
        if not vr.valid:
            return None

        return skill

    def list_remote_skills(self) -> list[RemoteSkillDescriptor]:
        """
        Fetch the skill registry and return descriptors.

        Returns empty list if no registry_url or on error.
        """
        if not self.registry_url:
            return []

        if self._registry_cache:
            fetched_at, descriptors = self._registry_cache
            if time.time() - fetched_at < self.ttl_s:
                return descriptors

        try:
            with urllib.request.urlopen(self.registry_url, timeout=self.timeout_s) as resp:
                raw = json.loads(resp.read().decode())
        except (urllib.error.URLError, json.JSONDecodeError, OSError):
            return []

        descriptors = []
        for item in raw.get("skills", raw if isinstance(raw, list) else []):
            try:
                descriptors.append(RemoteSkillDescriptor(
                    name=item["name"],
                    description=item.get("description", ""),
                    url=item["url"],
                    version=item.get("version", "0.0.0"),
                    tags=item.get("tags", []),
                ))
            except (KeyError, TypeError):
                continue

        self._registry_cache = (time.time(), descriptors)
        return descriptors

    def fetch_all(self) -> list[Skill]:
        """Fetch all skills from the remote registry."""
        skills: list[Skill] = []
        for desc in self.list_remote_skills():
            skill = self.fetch_skill(desc)
            if skill:
                skills.append(skill)
        return skills


__all__ = [
    "RemoteSkillDescriptor",
    "RemoteSkillProvider",
]
