"""
Core evaluation types — TaskSpec and TaskResult.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class TaskSpec:
    """Specification for a benchmark task."""

    id: str                                    # e.g., "eng-001-bugfix-python"
    category: str                              # "engineering" | "elearning" | "business" | "document"
    name: str                                  # Human-readable name
    description: str                           # What the task asks the model to do
    prompt: str                                # The exact prompt to send to the model
    seed_files: dict[str, str]                 # filename -> content (files to create before running)
    expected_outputs: dict[str, str] | None    # filename -> expected content (for automated checks)
    scoring_rubric: str                        # Markdown rubric for LLM-judge evaluation
    max_turns: int = 15
    timeout_seconds: float = 120.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> TaskSpec:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class TaskResult:
    """Result of running a task against a model."""

    task_id: str
    model: str
    completed: bool
    tool_calls_made: int
    tool_call_success_rate: float
    turns_used: int
    tokens_input: int
    tokens_output: int
    cost_usd: float
    time_seconds: float
    quality_score: float = 0.0                 # 0.0-1.0, from evaluator
    skill_adherence: float = 0.0               # 0.0-1.0
    failure_analysis: str | None = None
    output_files: dict[str, str] = field(default_factory=dict)
    raw_transcript: list[dict] = field(default_factory=list)
    judge_explanation: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def from_dict(cls, data: dict) -> TaskResult:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_json(cls, text: str) -> TaskResult:
        return cls.from_dict(json.loads(text))
