"""
Routing strategies — decide which model handles a task.

Strategies:
- cheapest: lowest cost that meets quality threshold
- fastest: fastest model that meets quality threshold
- quality: highest quality regardless of cost
- balanced: quality × completion / cost (best bang for buck)
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .capability_map import CapabilityMap, ModelCapability


class RoutingStrategy(str, Enum):
    CHEAPEST = "cheapest"
    FASTEST = "fastest"
    QUALITY = "quality"
    BALANCED = "balanced"


# Per-category minimum quality overrides.
# Categories where output quality matters more than cost
# (e.g. client deliverables) get a higher floor.
CATEGORY_MIN_QUALITY: dict[str, float] = {
    "elearning": 0.80,   # Client-facing content needs higher bar
    "business": 0.80,    # Proposals, analyses — quality matters
    "engineering": 0.70,  # Code that passes tests is fine
}


@dataclass
class RoutingDecision:
    """Result of a routing decision."""
    model_name: str
    strategy: RoutingStrategy
    category: str
    expected_quality: float
    expected_time: float
    expected_cost: float
    reason: str
    fallback: str | None = None
    profile_name: str | None = None  # None = use default model profile


def route_task(
    cap_map: CapabilityMap,
    category: str,
    strategy: RoutingStrategy = RoutingStrategy.BALANCED,
    min_quality: float = 0.7,
    max_cost: float | None = None,
    max_time: float | None = None,
) -> RoutingDecision | None:
    """
    Route a task to the best model based on strategy and constraints.

    Args:
        cap_map: Capability map with benchmark data
        category: Task category (engineering, business, elearning)
        strategy: Routing strategy to use
        min_quality: Minimum quality threshold
        max_cost: Maximum cost per task (USD)
        max_time: Maximum time per task (seconds)

    Returns:
        RoutingDecision or None if no model meets constraints
    """
    # Apply category-specific quality floor if it's higher than the caller's threshold
    effective_min = max(min_quality, CATEGORY_MIN_QUALITY.get(category, 0.0))
    candidates = cap_map.models_for_category(category, effective_min)

    # Apply hard constraints
    if max_cost is not None:
        candidates = [m for m in candidates if m.cost_for(category) <= max_cost]
    if max_time is not None:
        candidates = [m for m in candidates if m.speed_for(category) <= max_time]

    if not candidates:
        return None

    if strategy == RoutingStrategy.CHEAPEST:
        selected = min(candidates, key=lambda m: m.cost_for(category))
        reason = f"Cheapest model meeting quality threshold {min_quality}"

    elif strategy == RoutingStrategy.FASTEST:
        selected = min(candidates, key=lambda m: m.speed_for(category))
        reason = f"Fastest model meeting quality threshold {min_quality}"

    elif strategy == RoutingStrategy.QUALITY:
        selected = max(candidates, key=lambda m: m.quality_for(category))
        reason = f"Highest quality model for {category}"

    elif strategy == RoutingStrategy.BALANCED:
        # Score = (quality^2 × completion_rate) / (cost + 0.001)
        # Squaring quality makes the formula prefer higher-quality models
        # when the quality gap is significant (e.g. 0.88 vs 0.76),
        # while still favoring cheap models when quality is close.
        def score(m: ModelCapability) -> float:
            cat = m.categories.get(category)
            if not cat:
                return 0.0
            quality = cat.avg_quality
            completion = cat.completion_rate
            cost = cat.avg_cost_usd + 0.001  # avoid div by zero
            return (quality ** 2 * completion) / cost

        selected = max(candidates, key=score)
        s = score(selected)
        reason = f"Best balanced score ({s:.1f}) for {category}"
    else:
        return None

    # Find fallback (next best model by quality)
    fallback_name = None
    remaining = [m for m in candidates if m.model_name != selected.model_name]
    if remaining:
        fallback = max(remaining, key=lambda m: m.quality_for(category))
        fallback_name = fallback.model_name

    cat_data = selected.categories.get(category)

    # Determine which profile to use for this model + category
    from src.profiles.loader import find_profile_for_category
    from pathlib import Path
    profile_dir = Path(__file__).parent.parent.parent / "profiles"
    category_profile_path = profile_dir / f"{selected.model_name}_{category}.yaml"
    # If a category-specific profile file exists, use it
    profile_name = f"{selected.model_name}_{category}" if category_profile_path.exists() else None

    return RoutingDecision(
        model_name=selected.model_name,
        strategy=strategy,
        category=category,
        expected_quality=selected.quality_for(category),
        expected_time=selected.speed_for(category),
        expected_cost=selected.cost_for(category),
        reason=reason,
        fallback=fallback_name,
        profile_name=profile_name,
    )


def route_multi(
    cap_map: CapabilityMap,
    tasks: list[dict],
    strategy: RoutingStrategy = RoutingStrategy.BALANCED,
    min_quality: float = 0.7,
    budget: float | None = None,
) -> list[RoutingDecision]:
    """
    Route multiple tasks, optionally within a total budget.

    Each task dict should have at minimum: {"category": "engineering"}
    Optionally: {"task_id": "eng-001", "priority": "high"}

    If budget is set, routes greedily — highest priority tasks get
    best models, lower priority get cheapest capable.
    """
    decisions: list[RoutingDecision] = []
    remaining_budget = budget

    # Sort by priority (high first)
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    sorted_tasks = sorted(
        tasks,
        key=lambda t: priority_order.get(t.get("priority", "medium"), 2),
    )

    for task in sorted_tasks:
        category = task.get("category", "general")

        # If budget constrained, adjust strategy for lower priority tasks
        task_strategy = strategy
        if remaining_budget is not None and remaining_budget < 0.01:
            task_strategy = RoutingStrategy.CHEAPEST

        max_cost = remaining_budget if remaining_budget is not None else None
        decision = route_task(
            cap_map, category, task_strategy, min_quality, max_cost=max_cost
        )

        if decision:
            if remaining_budget is not None:
                remaining_budget -= decision.expected_cost
            decisions.append(decision)

    return decisions
