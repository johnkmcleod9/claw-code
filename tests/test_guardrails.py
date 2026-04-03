"""
Tests for profile improver guardrails.

Verifies that the self-improvement loop cannot regress critical parameters
below safe floors, above ceilings, or mutate immutable identity fields.
"""
import tempfile
from pathlib import Path

import pytest
import yaml

from src.router.improver import (
    GUARDRAIL_CEILINGS,
    GUARDRAIL_FLOORS,
    GUARDRAIL_IMMUTABLE,
    ImprovementPlan,
    PromptChange,
    _clamp_config,
    apply_improvement_plan,
)


# ---------------------------------------------------------------------------
# _clamp_config unit tests
# ---------------------------------------------------------------------------

class TestClampConfig:
    def test_value_within_bounds_passes_through(self):
        val, warning = _clamp_config("max_output_tokens", 16384, 16384)
        assert val == 16384
        assert warning is None

    def test_value_below_floor_clamped(self):
        val, warning = _clamp_config("max_output_tokens", 3072, 16384)
        assert val == GUARDRAIL_FLOORS["max_output_tokens"]
        assert warning is not None
        assert "floor" in warning.lower()

    def test_value_above_ceiling_clamped(self):
        val, warning = _clamp_config("optimal_temperature", 2.0, 0.7)
        assert val == GUARDRAIL_CEILINGS["optimal_temperature"]
        assert warning is not None
        assert "ceiling" in warning.lower()

    def test_context_window_floor(self):
        val, _ = _clamp_config("context_window", 1024, 128000)
        assert val == GUARDRAIL_FLOORS["context_window"]

    def test_unknown_field_passes_through(self):
        val, warning = _clamp_config("some_new_field", 42, 100)
        assert val == 42
        assert warning is None

    def test_preserves_int_type(self):
        val, _ = _clamp_config("max_output_tokens", 1000.0, 16384)
        assert isinstance(val, int)

    def test_exactly_at_floor_passes(self):
        floor = GUARDRAIL_FLOORS["max_output_tokens"]
        val, warning = _clamp_config("max_output_tokens", floor, floor)
        assert val == floor
        assert warning is None

    def test_exactly_at_ceiling_passes(self):
        ceiling = GUARDRAIL_CEILINGS["optimal_temperature"]
        val, warning = _clamp_config("optimal_temperature", ceiling, 0.7)
        assert val == ceiling
        assert warning is None


# ---------------------------------------------------------------------------
# apply_improvement_plan integration tests
# ---------------------------------------------------------------------------

def _make_profile_yaml(tmp_path: Path, **overrides) -> Path:
    """Create a minimal profile YAML for testing."""
    profile = {
        "name": "test-model",
        "provider": "openrouter",
        "model_id": "test/test-model",
        "context_window": 128000,
        "max_output_tokens": 16384,
        "supports_tool_calling": True,
        "optimal_temperature": 0.7,
        "optimal_top_p": 0.95,
        "system_prompt": "You are a helpful assistant.",
        "cost_per_million_input": 0.3,
        "cost_per_million_output": 1.1,
    }
    profile.update(overrides)
    path = tmp_path / "test-model.yaml"
    with open(path, "w") as f:
        yaml.dump(profile, f)
    return path


class TestApplyImprovementPlan:
    def test_max_tokens_regression_blocked(self, tmp_path):
        """The exact bug that broke MiniMax: analyst suggested max_tokens=3072."""
        profile_path = _make_profile_yaml(tmp_path, max_output_tokens=16384)
        plan = ImprovementPlan(
            model_name="test-model",
            current_quality=0.85,
            target_quality=0.90,
            failures=[],
            prompt_changes=[],
            config_changes={"max_tokens": 3072},
        )
        out = apply_improvement_plan(plan, profile_path)
        with open(out) as f:
            result = yaml.safe_load(f)
        assert result["max_output_tokens"] >= GUARDRAIL_FLOORS["max_output_tokens"]
        assert "_guardrail_warnings" in result

    def test_temperature_regression_blocked(self, tmp_path):
        profile_path = _make_profile_yaml(tmp_path)
        plan = ImprovementPlan(
            model_name="test-model",
            current_quality=0.85,
            target_quality=0.90,
            failures=[],
            prompt_changes=[],
            config_changes={"temperature": 2.5},
        )
        out = apply_improvement_plan(plan, profile_path)
        with open(out) as f:
            result = yaml.safe_load(f)
        assert result["optimal_temperature"] <= GUARDRAIL_CEILINGS["optimal_temperature"]

    def test_immutable_fields_blocked(self, tmp_path):
        """Analyst cannot rename the model or change provider/cost."""
        profile_path = _make_profile_yaml(tmp_path)
        plan = ImprovementPlan(
            model_name="test-model",
            current_quality=0.85,
            target_quality=0.90,
            failures=[],
            prompt_changes=[],
            config_changes={
                "name": "hacked-model",
                "provider": "evil-provider",
                "model_id": "evil/model",
                "cost_per_million_input": 0.0,
            },
        )
        out = apply_improvement_plan(plan, profile_path)
        with open(out) as f:
            result = yaml.safe_load(f)
        # All immutable fields should retain original values
        assert result["name"] == "test-model"
        assert result["provider"] == "openrouter"
        assert result["model_id"] == "test/test-model"
        assert result["cost_per_million_input"] == 0.3
        assert len(result["_guardrail_warnings"]) == 4

    def test_valid_changes_still_apply(self, tmp_path):
        """Guardrails don't block legitimate improvements."""
        profile_path = _make_profile_yaml(tmp_path, optimal_temperature=0.7)
        plan = ImprovementPlan(
            model_name="test-model",
            current_quality=0.80,
            target_quality=0.90,
            failures=[],
            prompt_changes=[
                PromptChange(
                    section="tool_usage",
                    action="add",
                    content="Always validate file paths before writing.",
                    rationale="Prevents tool errors",
                    priority=1,
                ),
            ],
            config_changes={"temperature": 0.3},
        )
        out = apply_improvement_plan(plan, profile_path)
        with open(out) as f:
            result = yaml.safe_load(f)
        assert result["optimal_temperature"] == 0.3
        assert "validate file paths" in result["system_prompt"]
        assert "_guardrail_warnings" not in result

    def test_prompt_changes_appended(self, tmp_path):
        profile_path = _make_profile_yaml(tmp_path)
        plan = ImprovementPlan(
            model_name="test-model",
            current_quality=0.80,
            target_quality=0.90,
            failures=[],
            prompt_changes=[
                PromptChange(section="constraints", action="emphasize",
                             content="Complete within 4 minutes.", rationale="timeout", priority=1),
                PromptChange(section="output_format", action="add",
                             content="Use markdown headers.", rationale="clarity", priority=2),
            ],
            config_changes={},
        )
        out = apply_improvement_plan(plan, profile_path)
        with open(out) as f:
            result = yaml.safe_load(f)
        assert "IMPORTANT" in result["system_prompt"]
        assert "markdown headers" in result["system_prompt"]

    def test_no_changes_produces_clean_copy(self, tmp_path):
        profile_path = _make_profile_yaml(tmp_path)
        plan = ImprovementPlan(
            model_name="test-model",
            current_quality=0.85,
            target_quality=0.90,
            failures=[],
            prompt_changes=[],
            config_changes={},
        )
        out = apply_improvement_plan(plan, profile_path)
        with open(out) as f:
            result = yaml.safe_load(f)
        assert "_guardrail_warnings" not in result
        assert result["max_output_tokens"] == 16384

    def test_max_output_tokens_key_also_guarded(self, tmp_path):
        """Analyst might use 'max_output_tokens' instead of 'max_tokens'."""
        profile_path = _make_profile_yaml(tmp_path, max_output_tokens=16384)
        plan = ImprovementPlan(
            model_name="test-model",
            current_quality=0.85,
            target_quality=0.90,
            failures=[],
            prompt_changes=[],
            config_changes={"max_output_tokens": 2048},
        )
        out = apply_improvement_plan(plan, profile_path)
        with open(out) as f:
            result = yaml.safe_load(f)
        assert result["max_output_tokens"] >= GUARDRAIL_FLOORS["max_output_tokens"]
