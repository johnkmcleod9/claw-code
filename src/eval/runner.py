"""
Task execution engine — runs a TaskSpec against a model and collects metrics.
"""
from __future__ import annotations

import asyncio
import shutil
import tempfile
import time
import traceback
from pathlib import Path

from src.agent.loop import AgentLoop
from src.profiles.model_profile import ModelProfile
from src.providers import get_provider
from src.providers.base import Message
from src.tools_impl.registry import ToolRegistry

from .models import TaskSpec, TaskResult


async def run_task(
    task: TaskSpec,
    profile: ModelProfile,
    registry: ToolRegistry,
    *,
    stream: bool = False,
) -> TaskResult:
    """
    Execute a single benchmark task against a model.

    1. Creates a temp working directory
    2. Writes seed files
    3. Runs the agent loop with the task prompt
    4. Collects output files, metrics, and transcript
    5. Cleans up
    """
    tmpdir = Path(tempfile.mkdtemp(prefix=f"eval_{task.id}_"))

    try:
        # Write seed files
        for filename, content in task.seed_files.items():
            filepath = tmpdir / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content)

        # Initialize provider and agent
        provider = get_provider(profile.provider, model_id=profile.model_id)
        agent = AgentLoop(
            provider=provider,
            profile=profile,
            registry=registry,
            workdir=tmpdir,
            max_turns=task.max_turns,
            stream=stream,
        )

        # Run with timeout
        start = time.time()
        try:
            final_response = await asyncio.wait_for(
                agent.run(task.prompt),
                timeout=task.timeout_seconds,
            )
            completed = True
            failure_analysis = None
        except asyncio.TimeoutError:
            completed = False
            final_response = ""
            failure_analysis = f"Timeout after {task.timeout_seconds}s"
        except Exception as e:
            completed = False
            final_response = ""
            failure_analysis = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

        elapsed = time.time() - start

        # Collect output files (everything not in seed_files, or changed)
        output_files = _collect_outputs(tmpdir, task.seed_files)

        # Build transcript from agent messages
        raw_transcript = _serialize_messages(agent.messages)

        # Compute tool call success rate
        stats = agent.stats
        tc_rate = (
            stats.tool_calls_succeeded / stats.tool_calls_made
            if stats.tool_calls_made > 0
            else 1.0
        )

        return TaskResult(
            task_id=task.id,
            model=profile.name,
            completed=completed,
            tool_calls_made=stats.tool_calls_made,
            tool_call_success_rate=tc_rate,
            turns_used=stats.turns,
            tokens_input=stats.total_input_tokens,
            tokens_output=stats.total_output_tokens,
            cost_usd=stats.total_cost_usd,
            time_seconds=elapsed,
            failure_analysis=failure_analysis,
            output_files=output_files,
            raw_transcript=raw_transcript,
        )

    finally:
        # Cleanup temp directory
        shutil.rmtree(tmpdir, ignore_errors=True)


def _collect_outputs(workdir: Path, seed_files: dict[str, str]) -> dict[str, str]:
    """Collect files that were created or modified by the agent."""
    outputs: dict[str, str] = {}
    for path in workdir.rglob("*"):
        if path.is_file():
            relpath = str(path.relative_to(workdir))
            try:
                content = path.read_text(errors="replace")
            except Exception:
                continue

            # Include if new or changed from seed
            if relpath not in seed_files or content != seed_files[relpath]:
                outputs[relpath] = content

    return outputs


def _serialize_messages(messages: list[Message]) -> list[dict]:
    """Convert Message objects to serializable dicts."""
    result = []
    for msg in messages:
        entry: dict = {"role": msg.role}
        if isinstance(msg.content, str):
            entry["content"] = msg.content
        elif isinstance(msg.content, list):
            entry["content"] = msg.content
        if msg.tool_calls:
            entry["tool_calls"] = [
                {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                for tc in msg.tool_calls
            ]
        if msg.tool_call_id:
            entry["tool_call_id"] = msg.tool_call_id
        if msg.name:
            entry["name"] = msg.name
        result.append(entry)
    return result
