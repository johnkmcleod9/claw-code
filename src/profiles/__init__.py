"""Model profiles — configuration and capabilities for each model."""
from .model_profile import ModelProfile
from .loader import load_profile, load_all_profiles

__all__ = ["ModelProfile", "load_profile", "load_all_profiles"]
