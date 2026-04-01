"""
Capability Map — stores benchmark results and model strengths per task category.

Built from eval results, updated by the self-improving loop.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TaskScore:
    """Score for a specific task."""
    task_id: str
    quality: float
    adherence: float
    avg_time_seconds: float
    avg_cost_usd: float
    completion_rate: float  # 0.0 - 1.0
    tool_success_rate: float
    samples: int = 1

    @property
    def effective_quality(self) -> float:
        """Quality weighted by completion rate."""
        return self.quality * self.completion_rate


@dataclass
class CategoryScore:
    """Aggregated score for a task category (engineering, business, elearning)."""
    category: str
    avg_quality: float
    avg_adherence: float
    avg_time_seconds: float
    avg_cost_usd: float
    completion_rate: float
    task_scores: dict[str, TaskScore] = field(default_factory=dict)


@dataclass
class ModelCapability:
    """Full capability profile for a model, built from benchmark data."""
    model_name: str
    provider: str
    cost_per_million_input: float
    cost_per_million_output: float
    categories: dict[str, CategoryScore] = field(default_factory=dict)

    @property
    def overall_quality(self) -> float:
        if not self.categories:
            return 0.0
        return sum(c.avg_quality for c in self.categories.values()) / len(self.categories)

    @property
    def overall_speed(self) -> float:
        """Average seconds per task across all categories."""
        if not self.categories:
            return float("inf")
        return sum(c.avg_time_seconds for c in self.categories.values()) / len(self.categories)

    @property
    def overall_completion(self) -> float:
        if not self.categories:
            return 0.0
        return sum(c.completion_rate for c in self.categories.values()) / len(self.categories)

    def quality_for(self, category: str) -> float:
        """Get quality score for a specific category, or overall if not found."""
        if category in self.categories:
            return self.categories[category].avg_quality
        return self.overall_quality

    def speed_for(self, category: str) -> float:
        if category in self.categories:
            return self.categories[category].avg_time_seconds
        return self.overall_speed

    def cost_for(self, category: str) -> float:
        if category in self.categories:
            return self.categories[category].avg_cost_usd
        return 0.0

    def can_handle(self, category: str, min_quality: float = 0.7) -> bool:
        """Check if model meets minimum quality threshold for a category."""
        return self.quality_for(category) >= min_quality


class CapabilityMap:
    """
    Registry of model capabilities, built from benchmark results.

    Supports:
    - Loading from eval result directories
    - Manual capability registration
    - Querying best model for a task category
    - Persistence to/from JSON
    """

    def __init__(self) -> None:
        self.models: dict[str, ModelCapability] = {}

    def register(self, capability: ModelCapability) -> None:
        """Register or update a model's capabilities."""
        self.models[capability.model_name] = capability

    def get(self, model_name: str) -> ModelCapability | None:
        return self.models.get(model_name)

    def models_for_category(
        self, category: str, min_quality: float = 0.7
    ) -> list[ModelCapability]:
        """Get all models that meet minimum quality for a category, sorted by quality."""
        capable = [
            m for m in self.models.values()
            if m.can_handle(category, min_quality)
        ]
        return sorted(capable, key=lambda m: m.quality_for(category), reverse=True)

    def cheapest_capable(
        self, category: str, min_quality: float = 0.7
    ) -> ModelCapability | None:
        """Find the cheapest model that meets quality threshold."""
        capable = self.models_for_category(category, min_quality)
        if not capable:
            return None
        return min(capable, key=lambda m: m.cost_for(category))

    def fastest_capable(
        self, category: str, min_quality: float = 0.7
    ) -> ModelCapability | None:
        """Find the fastest model that meets quality threshold."""
        capable = self.models_for_category(category, min_quality)
        if not capable:
            return None
        return min(capable, key=lambda m: m.speed_for(category))

    def best_quality(self, category: str) -> ModelCapability | None:
        """Find the highest quality model for a category."""
        if not self.models:
            return None
        return max(
            self.models.values(),
            key=lambda m: m.quality_for(category),
        )

    @classmethod
    def from_eval_results(cls, results_dir: Path) -> "CapabilityMap":
        """
        Build capability map from eval result directories.

        Expected structure:
            results_dir/
                REPORT.md
                model-name/
                    task-id.json
        """
        cap_map = cls()

        for model_dir in results_dir.iterdir():
            if not model_dir.is_dir():
                continue

            model_name = model_dir.name
            task_scores: dict[str, dict[str, TaskScore]] = {}  # category -> task_id -> score

            for result_file in model_dir.glob("*.json"):
                try:
                    data = json.loads(result_file.read_text())
                except (json.JSONDecodeError, OSError):
                    continue

                task_id = data.get("task_id", result_file.stem)
                # Infer category from task_id prefix
                category = _infer_category(task_id)

                completed = data.get("completed", False)
                quality = data.get("quality_score", 0.0) if completed else 0.0
                adherence = data.get("skill_adherence", 0.0) if completed else 0.0

                # Calculate tool success rate — handle None/missing gracefully
                succeeded = data.get("tool_calls_succeeded")
                made = data.get("tool_calls_made", 0)
                if succeeded is not None and made > 0:
                    tool_success = succeeded / made
                elif made > 0:
                    # tool_calls_succeeded not tracked — assume success if task completed
                    tool_success = 1.0 if completed else 0.0
                else:
                    tool_success = 1.0  # no tools called = no failures

                score = TaskScore(
                    task_id=task_id,
                    quality=quality,
                    adherence=adherence,
                    avg_time_seconds=data.get("time_seconds", 0.0),
                    avg_cost_usd=data.get("cost_usd", 0.0),
                    completion_rate=1.0 if completed else 0.0,
                    tool_success_rate=tool_success,
                )

                if category not in task_scores:
                    task_scores[category] = {}
                task_scores[category][task_id] = score

            # Aggregate into CategoryScores
            categories: dict[str, CategoryScore] = {}
            for cat, scores in task_scores.items():
                score_list = list(scores.values())
                n = len(score_list)
                categories[cat] = CategoryScore(
                    category=cat,
                    avg_quality=sum(s.quality for s in score_list) / n,
                    avg_adherence=sum(s.adherence for s in score_list) / n,
                    avg_time_seconds=sum(s.avg_time_seconds for s in score_list) / n,
                    avg_cost_usd=sum(s.avg_cost_usd for s in score_list) / n,
                    completion_rate=sum(s.completion_rate for s in score_list) / n,
                    task_scores=scores,
                )

            cap = ModelCapability(
                model_name=model_name,
                provider="openrouter",  # default, could be overridden
                cost_per_million_input=0.0,
                cost_per_million_output=0.0,
                categories=categories,
            )
            cap_map.register(cap)

        return cap_map

    def save(self, path: Path) -> None:
        """Persist capability map to JSON."""
        data: dict[str, Any] = {}
        for name, model in self.models.items():
            model_data: dict[str, Any] = {
                "provider": model.provider,
                "cost_per_million_input": model.cost_per_million_input,
                "cost_per_million_output": model.cost_per_million_output,
                "categories": {},
            }
            for cat_name, cat in model.categories.items():
                cat_data: dict[str, Any] = {
                    "avg_quality": cat.avg_quality,
                    "avg_adherence": cat.avg_adherence,
                    "avg_time_seconds": cat.avg_time_seconds,
                    "avg_cost_usd": cat.avg_cost_usd,
                    "completion_rate": cat.completion_rate,
                    "tasks": {
                        tid: {
                            "quality": ts.quality,
                            "adherence": ts.adherence,
                            "time": ts.avg_time_seconds,
                            "cost": ts.avg_cost_usd,
                            "completion": ts.completion_rate,
                            "tool_success": ts.tool_success_rate,
                        }
                        for tid, ts in cat.task_scores.items()
                    },
                }
                model_data["categories"][cat_name] = cat_data
            data[name] = model_data

        path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, path: Path) -> "CapabilityMap":
        """Load capability map from JSON."""
        data = json.loads(path.read_text())
        cap_map = cls()

        for model_name, model_data in data.items():
            categories: dict[str, CategoryScore] = {}
            for cat_name, cat_data in model_data.get("categories", {}).items():
                task_scores: dict[str, TaskScore] = {}
                for tid, tdata in cat_data.get("tasks", {}).items():
                    task_scores[tid] = TaskScore(
                        task_id=tid,
                        quality=tdata["quality"],
                        adherence=tdata["adherence"],
                        avg_time_seconds=tdata["time"],
                        avg_cost_usd=tdata["cost"],
                        completion_rate=tdata["completion"],
                        tool_success_rate=tdata["tool_success"],
                    )
                categories[cat_name] = CategoryScore(
                    category=cat_name,
                    avg_quality=cat_data["avg_quality"],
                    avg_adherence=cat_data["avg_adherence"],
                    avg_time_seconds=cat_data["avg_time_seconds"],
                    avg_cost_usd=cat_data["avg_cost_usd"],
                    completion_rate=cat_data["completion_rate"],
                    task_scores=task_scores,
                )

            cap = ModelCapability(
                model_name=model_name,
                provider=model_data.get("provider", "openrouter"),
                cost_per_million_input=model_data.get("cost_per_million_input", 0.0),
                cost_per_million_output=model_data.get("cost_per_million_output", 0.0),
                categories=categories,
            )
            cap_map.register(cap)

        return cap_map


def _infer_category(task_id: str) -> str:
    """Infer task category from task ID prefix."""
    prefix = task_id.split("-")[0].lower()
    category_map = {
        "eng": "engineering",
        "biz": "business",
        "el": "elearning",
    }
    return category_map.get(prefix, "general")
