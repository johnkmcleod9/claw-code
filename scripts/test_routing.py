#!/usr/bin/env python3
"""Test routing decisions with the updated capability map."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.router.capability_map import CapabilityMap
from src.router.strategy import route_task, route_multi, RoutingStrategy

cap_map = CapabilityMap.load(Path("capability_map.json"))

print("=" * 70)
print("ROUTING DECISIONS — Updated Capability Map (2026-04-01)")
print("=" * 70)

for category in ["engineering", "business", "elearning"]:
    print(f"\n{'─' * 50}")
    print(f"Category: {category.upper()}")
    print(f"{'─' * 50}")
    
    for strategy in RoutingStrategy:
        decision = route_task(cap_map, category, strategy=strategy)
        if decision:
            print(
                f"  {strategy.value:10s} → {decision.model_name:15s} "
                f"(Q={decision.expected_quality:.2f}, "
                f"${decision.expected_cost:.4f}/task, "
                f"{decision.expected_time:.0f}s) "
                f"[fallback: {decision.fallback or 'none'}]"
            )

# Test budget-constrained routing
print(f"\n{'=' * 70}")
print("BUDGET-CONSTRAINED: 10 mixed tasks, $0.50 budget")
print(f"{'=' * 70}")

tasks = [
    {"category": "engineering", "priority": "high"},
    {"category": "engineering", "priority": "medium"},
    {"category": "engineering", "priority": "medium"},
    {"category": "business", "priority": "high"},
    {"category": "business", "priority": "medium"},
    {"category": "business", "priority": "low"},
    {"category": "elearning", "priority": "high"},
    {"category": "elearning", "priority": "medium"},
    {"category": "elearning", "priority": "low"},
    {"category": "engineering", "priority": "low"},
]

decisions = route_multi(cap_map, tasks, budget=0.50)
total_cost = 0
for d in decisions:
    total_cost += d.expected_cost
    print(f"  {d.category:12s} → {d.model_name:15s} (${d.expected_cost:.4f})")

print(f"\n  Total estimated cost: ${total_cost:.4f}")
