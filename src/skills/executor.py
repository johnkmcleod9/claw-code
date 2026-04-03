"""
Skill executor — runs skills in context.

Ports: skills/executeSkill.ts, skills/runSkill.ts, skills/skillPipeline.ts
Provides skill execution with context injection and result formatting.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .loader import Skill, resolve_skill
from .types import SkillResult


# ---------------------------------------------------------------------------
# Execution context
# ---------------------------------------------------------------------------

@dataclass
class ExecutionContext:
    """Context passed to a skill at execution time."""
    user_message: str = ""
    conversation_history: list[dict] = field(default_factory=list)
    cwd: Path = field(default_factory=Path.cwd)
    variables: dict[str, str] = field(default_factory=dict)
    max_output_tokens: int = 4096
    model: str = ""
    session_id: str = ""


# ---------------------------------------------------------------------------
# Skill executor
# ---------------------------------------------------------------------------

class SkillExecutor:
    """
    Executes skills with context injection and result handling.

    Ports: skills/executeSkill.ts
    """

    def __init__(self):
        self._handlers: dict[str, Callable[[ExecutionContext], str]] = {}

    def register(self, name: str, handler: Callable[[ExecutionContext], str]) -> None:
        """Register a built-in skill handler."""
        self._handlers[name] = handler

    def execute(self, skill: Skill, context: ExecutionContext) -> SkillResult:
        """
        Execute a skill with the given context.

        Resolution order:
        1. Registered Python handler (highest priority)
        2. Bundled skill (inline logic)
        3. Generic markdown skill (pass to LLM)
        """
        start = time.monotonic()
        name = skill.name

        # Try registered handler first
        if name in self._handlers:
            try:
                output = self._handlers[name](context)
                elapsed = (time.monotonic() - start) * 1000
                return SkillResult(
                    skill_name=name,
                    success=True,
                    output=output,
                    duration_ms=elapsed,
                )
            except Exception as e:
                elapsed = (time.monotonic() - start) * 1000
                return SkillResult(
                    skill_name=name,
                    success=False,
                    error=str(e),
                    duration_ms=elapsed,
                )

        # Generic skill execution — return content for LLM to process
        elapsed = (time.monotonic() - start) * 1000
        return SkillResult(
            skill_name=name,
            success=True,
            output=skill.content,
            duration_ms=elapsed,
            metadata={"source": skill.source},
        )


# ---------------------------------------------------------------------------
# Built-in skill handlers (bundled skills)
# ---------------------------------------------------------------------------

def _build_debug_skill(ctx: ExecutionContext) -> str:
    """Bundled /debug skill handler."""
    lines = [
        "## Debug Information",
        "",
        f"**Session:** `{ctx.session_id or 'N/A'}`",
        f"**Model:** {ctx.model or 'N/A'}",
        f"**CWD:** `{ctx.cwd}`",
        "",
        "**Recent history:**",
    ]
    for msg in ctx.conversation_history[-5:]:
        role = msg.get("role", "?")
        content = msg.get("content", "")
        if isinstance(content, list):
            content = "…".join(
                b.get("text", "") for b in content if b.get("type") == "text"
            )
        lines.append(f"- **{role}:** {str(content)[:100]}")
    return "\n".join(lines)


def _build_verify_skill(ctx: ExecutionContext) -> str:
    """Bundled /verify skill handler."""
    return (
        "## Verification Guide\n\n"
        "Run these checks on any code before marking complete:\n"
        "1. Syntax check: `python -m py_compile <file>`\n"
        "2. Type check: `mypy <file>` (if typed)\n"
        "3. Lint: `ruff check <file>`\n"
        "4. Tests: `pytest <file>`\n"
        "5. Import check: `python -c 'import <module>'`\n"
    )


def _build_remember_skill(ctx: ExecutionContext) -> str:
    """Bundled /remember skill handler."""
    facts: list[str] = []
    for msg in ctx.conversation_history:
        content = msg.get("content", "")
        if isinstance(content, str) and len(content) > 20:
            facts.append(content[:150])
    return (
        "## Key Points from This Session\n\n" +
        "\n".join(f"- {f}" for f in facts[-10:]) +
        "\n\n_Save these to memory with /memory._"
    )


def _build_simplify_skill(ctx: ExecutionContext) -> str:
    """Bundled /simplify skill handler."""
    return (
        "## Simplification Strategies\n\n"
        "When simplifying complex content:\n"
        "1. Replace jargon with plain language\n"
        "2. Use active voice\n"
        "3. Break long sentences into short ones\n"
        "4. Use concrete examples\n"
        "5. Add visual structure (headings, lists)\n"
        "6. Test readability — aim for Grade 8 level\n"
    )


def _build_stuck_skill(ctx: ExecutionContext) -> str:
    """Bundled /stuck skill handler."""
    return (
        "## When You're Stuck\n\n"
        "1. **Re-read the goal** — what's the actual objective?\n"
        "2. **Break it down** — smaller steps = easier wins\n"
        "3. **Rubber duck** — explain the problem aloud\n"
        "4. **Search** — docs, Stack Overflow, or just try\n"
        "5. **Ask for help** — I can assist with most things\n"
        "6. **Take a break** — context switching helps\n"
    )


def _build_security_skill(ctx: ExecutionContext) -> str:
    """Bundled /security skill handler."""
    return (
        "## Security Checklist\n\n"
        "- [ ] No hardcoded credentials or API keys\n"
        "- [ ] Environment variables for secrets\n"
        "- [ ] Input validation on all user inputs\n"
        "- [ ] SQL injection prevention (parameterized queries)\n"
        "- [ ] XSS prevention (escape output)\n"
        "- [ ] CSRF tokens on forms\n"
        "- [ ] HTTPS only for auth/cookies\n"
        "- [ ] Principle of least privilege\n"
        "- [ ] Secrets not in git history\n"
        "- [ ] Dependencies audited (`pip audit` / `npm audit`)\n"
    )


# ---------------------------------------------------------------------------
# Register built-in handlers
# ---------------------------------------------------------------------------

_executor = SkillExecutor()
_executor.register("debug",    _build_debug_skill)
_executor.register("verify",   _build_verify_skill)
_executor.register("remember", _build_remember_skill)
_executor.register("simplify", _build_simplify_skill)
_executor.register("stuck",    _build_stuck_skill)
_executor.register("security", _build_security_skill)


def execute_skill(skill: Skill, context: ExecutionContext) -> SkillResult:
    """Execute a skill using the global executor."""
    return _executor.execute(skill, context)


def execute_skill_by_name(
    name: str,
    context: ExecutionContext,
    cwd: Path | None = None,
) -> SkillResult | None:
    """Resolve a skill by name and execute it."""
    skill = resolve_skill(name, cwd=cwd)
    if not skill:
        return None
    return execute_skill(skill, context)


def format_skill_result(result: SkillResult) -> str:
    """Format a SkillResult as readable output."""
    if result.success:
        elapsed = f"({result.duration_ms/1000:.2f}s)"
        header = f"### Skill: {result.skill_name} {elapsed}"
        return f"{header}\n\n{result.output}"
    else:
        header = f"### Skill Error: {result.skill_name}"
        return f"{header}\n\n**Error:** {result.error}"


__all__ = [
    "ExecutionContext",
    "SkillExecutor",
    "execute_skill",
    "execute_skill_by_name",
    "format_skill_result",
]
