"""
Skill telemetry — usage tracking and analytics.

Ports: skills/skillTelemetry.ts, skills/usageTracker.ts

Records which skills were matched/executed, execution times, and hit rates.
Data stays local (no external reporting).
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SkillUsageRecord:
    skill_name: str
    match_count: int = 0
    exec_count: int = 0
    error_count: int = 0
    total_duration_ms: float = 0.0
    last_used: float = 0.0

    @property
    def avg_duration_ms(self) -> float:
        if self.exec_count == 0:
            return 0.0
        return self.total_duration_ms / self.exec_count

    @property
    def error_rate(self) -> float:
        if self.exec_count == 0:
            return 0.0
        return self.error_count / self.exec_count


class SkillTelemetry:
    """
    In-memory usage tracker for skills.

    Persists data to a JSON file (optional) for cross-session analytics.
    """

    def __init__(self, persist_path: Path | None = None) -> None:
        self._records: dict[str, SkillUsageRecord] = {}
        self.persist_path = persist_path
        if persist_path and persist_path.exists():
            self._load()

    # ── Recording ─────────────────────────────────────────────────────────

    def record_match(self, skill_name: str) -> None:
        rec = self._get_or_create(skill_name)
        rec.match_count += 1
        rec.last_used = time.time()

    def record_execution(
        self,
        skill_name: str,
        duration_ms: float,
        success: bool,
    ) -> None:
        rec = self._get_or_create(skill_name)
        rec.exec_count += 1
        rec.total_duration_ms += duration_ms
        rec.last_used = time.time()
        if not success:
            rec.error_count += 1

    def _get_or_create(self, name: str) -> SkillUsageRecord:
        if name not in self._records:
            self._records[name] = SkillUsageRecord(skill_name=name)
        return self._records[name]

    # ── Reporting ─────────────────────────────────────────────────────────

    def top_skills(self, n: int = 10, by: str = "exec_count") -> list[SkillUsageRecord]:
        """Return top-N skills sorted by the given metric."""
        records = list(self._records.values())
        records.sort(key=lambda r: getattr(r, by, 0), reverse=True)
        return records[:n]

    def get(self, skill_name: str) -> SkillUsageRecord | None:
        return self._records.get(skill_name)

    def summary(self) -> dict:
        total_execs = sum(r.exec_count for r in self._records.values())
        total_errors = sum(r.error_count for r in self._records.values())
        return {
            "unique_skills": len(self._records),
            "total_executions": total_execs,
            "total_errors": total_errors,
            "error_rate": total_errors / total_execs if total_execs else 0.0,
            "top_skills": [
                {"name": r.skill_name, "execs": r.exec_count}
                for r in self.top_skills(5)
            ],
        }

    # ── Persistence ───────────────────────────────────────────────────────

    def save(self) -> bool:
        if not self.persist_path:
            return False
        try:
            data = {
                name: {
                    "match_count": r.match_count,
                    "exec_count": r.exec_count,
                    "error_count": r.error_count,
                    "total_duration_ms": r.total_duration_ms,
                    "last_used": r.last_used,
                }
                for name, r in self._records.items()
            }
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            self.persist_path.write_text(json.dumps(data, indent=2))
            return True
        except OSError:
            return False

    def _load(self) -> None:
        try:
            raw = json.loads(self.persist_path.read_text())  # type: ignore[union-attr]
            for name, vals in raw.items():
                self._records[name] = SkillUsageRecord(
                    skill_name=name,
                    match_count=vals.get("match_count", 0),
                    exec_count=vals.get("exec_count", 0),
                    error_count=vals.get("error_count", 0),
                    total_duration_ms=vals.get("total_duration_ms", 0.0),
                    last_used=vals.get("last_used", 0.0),
                )
        except (OSError, json.JSONDecodeError, KeyError):
            pass


__all__ = [
    "SkillUsageRecord",
    "SkillTelemetry",
]
