"""
Evaluation engine for the Adaptive Harness.

Provides task execution, LLM-based judging, and benchmark suite management.
"""
from .models import TaskSpec, TaskResult
from .runner import run_task
from .judge import judge_result, JudgeResult
from .suite import BenchmarkSuite, run_suite, generate_capability_matrix, generate_report

__all__ = [
    "TaskSpec",
    "TaskResult",
    "run_task",
    "judge_result",
    "JudgeResult",
    "BenchmarkSuite",
    "run_suite",
    "generate_capability_matrix",
    "generate_report",
]
