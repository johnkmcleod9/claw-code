"""
Skill execution pipeline.

Ports: skills/executeSkill.ts, skills/skillRunner.ts

Handles markdown skill context injection and MCP tool dispatch.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from .loader import Skill, resolve_skill
from .mcp import MCPSkill, MCPSkillTool
from .types import SkillEvent, SkillResult


_pre_hooks:  list[Callable] = []
_post_hooks: list[Callable] = []


def register_pre_hook(fn: Callable) -> None:
    _pre_hooks.append(fn)


def register_post_hook(fn: Callable) -> None:
    _post_hooks.append(fn)


@dataclass
class SkillExecutionContext:
    skill: Skill
    inputs: dict[str, Any] = field(default_factory=dict)
    user_query: str = ""
    inject_into_system: bool = True
    tool_name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


async def execute_skill(
    ctx: "SkillExecutionContext",
    mcp_skill: MCPSkill | None = None,
) -> SkillResult:
    t0 = time.monotonic()
    for hook in _pre_hooks:
        try:
            hook(ctx)
        except Exception:
            pass

    try:
        if mcp_skill is not None:
            result = await _run_mcp_skill(ctx, mcp_skill)
        else:
            result = _run_markdown_skill(ctx)
    except Exception as exc:
        result = SkillResult(skill_name=ctx.skill.name, success=False, error=str(exc))

    result.duration_ms = (time.monotonic() - t0) * 1000

    for hook in _post_hooks:
        try:
            hook(ctx, result)
        except Exception:
            pass

    return result


def _run_markdown_skill(ctx: "SkillExecutionContext") -> SkillResult:
    return SkillResult(
        skill_name=ctx.skill.name,
        success=True,
        output=ctx.skill.content,
        metadata={"injected": ctx.inject_into_system, "source": ctx.skill.source},
    )


async def _run_mcp_skill(ctx: "SkillExecutionContext", mcp_skill: MCPSkill) -> SkillResult:
    tool_name = ctx.tool_name or (mcp_skill.tools[0].name if mcp_skill.tools else "")
    tool: MCPSkillTool | None = next(
        (t for t in mcp_skill.tools if t.name == tool_name), None
    )
    if tool is None:
        return SkillResult(
            skill_name=ctx.skill.name,
            success=False,
            error=f"Tool '{tool_name}' not found in MCP skill '{mcp_skill.name}'",
        )
    try:
        if asyncio.iscoroutinefunction(tool.handler):
            output = await tool.handler(**ctx.inputs)
        else:
            output = tool.handler(**ctx.inputs)
    except TypeError as exc:
        return SkillResult(skill_name=ctx.skill.name, success=False, error=str(exc))

    return SkillResult(
        skill_name=ctx.skill.name,
        success=True,
        output=output,
        metadata={"tool": tool_name},
    )


async def run_skill_by_name(
    name: str,
    inputs: dict[str, Any] | None = None,
    user_query: str = "",
    cwd=None,
) -> SkillResult:
    skill = resolve_skill(name, cwd=cwd)
    if skill is None:
        return SkillResult(skill_name=name, success=False, error=f"Skill '{name}' not found")
    ctx = SkillExecutionContext(skill=skill, inputs=inputs or {}, user_query=user_query)
    return await execute_skill(ctx)


def inject_skill_into_system_prompt(skill: Skill, existing_system: str = "") -> str:
    block = f'<skill name="{skill.name}">\n{skill.content.strip()}\n</skill>'
    if existing_system:
        return block + "\n\n" + existing_system
    return block


__all__ = [
    "SkillExecutionContext",
    "execute_skill",
    "run_skill_by_name",
    "inject_skill_into_system_prompt",
    "register_pre_hook",
    "register_post_hook",
]
