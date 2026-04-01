"""
ModelProfile — dataclass capturing model capabilities and optimal settings.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ModelProfile:
    """Complete profile for a model including capabilities, costs, and tuning."""

    # Identity
    name: str                                    # e.g., "minimax-m2.7"
    provider: str                                # "openrouter" | "anthropic" | "lmstudio"
    model_id: str                                # "minimax/minimax-m2.7"

    # Capabilities
    context_window: int = 128_000
    max_output_tokens: int = 8_192
    supports_tool_calling: bool = True
    supports_structured_output: bool = False
    supports_streaming: bool = True
    tool_call_format: str = "native"             # "native" | "xml" | "json_block"

    # Sampling defaults
    optimal_temperature: float = 0.7
    optimal_top_p: float = 0.95

    # Prompt style
    system_prompt_style: str = "direct"          # "direct" | "example_heavy" | "chain_of_thought"
    prompt_template: str | None = None           # Path to model-specific system prompt
    system_prompt: str = ""                      # Inline system prompt (set by improver)

    # Cost (per million tokens)
    cost_per_million_input: float = 0.0
    cost_per_million_output: float = 0.0

    # Qualitative
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)

    # Self-improvement fields (evolved over time)
    evolved_settings: dict = field(default_factory=dict)
    skill_adherence_scores: dict = field(default_factory=dict)
    last_calibration: datetime | None = None

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD for a given token count."""
        return (
            (input_tokens / 1_000_000) * self.cost_per_million_input
            + (output_tokens / 1_000_000) * self.cost_per_million_output
        )
