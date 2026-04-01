"""
Task Router — picks the best model for each task based on capability profiles,
cost constraints, and quality targets.
"""
from .capability_map import CapabilityMap, ModelCapability
from .strategy import RoutingStrategy, route_task
from .cascade import CascadeRunner

__all__ = [
    "CapabilityMap",
    "ModelCapability",
    "RoutingStrategy",
    "route_task",
    "CascadeRunner",
]
