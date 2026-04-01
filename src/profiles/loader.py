"""
Load ModelProfile instances from YAML files.
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime

import yaml

from .model_profile import ModelProfile


def load_profile(path: str | Path) -> ModelProfile:
    """Load a single ModelProfile from a YAML file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    # Handle last_calibration datetime
    if "last_calibration" in data and isinstance(data["last_calibration"], str):
        data["last_calibration"] = datetime.fromisoformat(data["last_calibration"])

    return ModelProfile(**data)


def load_all_profiles(directory: str | Path | None = None) -> dict[str, ModelProfile]:
    """Load all YAML profiles from a directory. Returns dict keyed by profile name."""
    if directory is None:
        # Default: profiles/ directory at project root
        directory = Path(__file__).parent.parent.parent / "profiles"

    directory = Path(directory)
    if not directory.exists():
        return {}

    profiles: dict[str, ModelProfile] = {}
    for yaml_file in sorted(directory.glob("*.yaml")):
        try:
            profile = load_profile(yaml_file)
            # Key by filename stem (e.g. qwen-local, qwen-local_eng) to avoid
            # collisions when multiple files share the same `name:` field.
            stem = yaml_file.stem
            profiles[stem] = profile
        except Exception as e:
            print(f"Warning: Failed to load profile {yaml_file}: {e}")

    return profiles


def find_profile(name: str, directory: str | Path | None = None) -> ModelProfile | None:
    """Find a profile by name (checks profiles/ directory)."""
    profiles = load_all_profiles(directory)
    return profiles.get(name)


def find_profile_for_category(
    model_name: str,
    category: str,
    directory: str | Path | None = None,
) -> ModelProfile | None:
    """
    Find the right profile for a model + category combination.

    Tries modelname_category.yaml first (e.g. qwen-local_eng.yaml),
    then falls back to modelname.yaml.

    This enables per-category profile variants — e.g. an engineering-tuned
    profile for coding tasks and a baseline profile for writing tasks.
    """
    if directory is None:
        directory = Path(__file__).parent.parent.parent / "profiles"
    directory = Path(directory)

    # Try category-specific profile first
    category_profile_path = directory / f"{model_name}_{category}.yaml"
    if category_profile_path.exists():
        return load_profile(category_profile_path)

    # Fall back to generic profile
    return find_profile(model_name, directory)
