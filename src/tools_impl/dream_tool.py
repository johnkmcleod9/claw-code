"""
Dream Mode — continuous background reasoning and idea development.

Inspired by Claude Code's unreleased Dream Mode feature (discovered in March 2026 source leak).
Runs the agent in a background loop, thinking through problems, iterating on ideas,
and writing results to a dream journal. User can check in anytime.

Key differences from normal agent mode:
- Runs autonomously in the background
- Writes thoughts/ideas to a dream journal file
- Can be given a seed topic or left to free-associate from project context
- Stops after a configurable number of iterations or on user interrupt
- Low-cost: uses cheap models by default for extended thinking
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from .base import Tool, ToolContext, ToolResult

DREAM_DIR = Path.home() / ".claw-code" / "dreams"
DREAM_STATE_FILE = DREAM_DIR / "state.json"

# Track running dream process
_dream_process: asyncio.subprocess.Process | None = None
_dream_active: bool = False


def _dream_journal_path(topic: str = "") -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    slug = topic.lower().replace(" ", "-")[:30] if topic else "freeform"
    return DREAM_DIR / f"dream-{timestamp}-{slug}.md"


def _load_dream_state() -> dict:
    if DREAM_STATE_FILE.exists():
        try:
            return json.loads(DREAM_STATE_FILE.read_text())
        except Exception:
            pass
    return {"active": False}


def _save_dream_state(state: dict):
    DREAM_DIR.mkdir(parents=True, exist_ok=True)
    DREAM_STATE_FILE.write_text(json.dumps(state, indent=2))


class DreamTool(Tool):
    """Start, stop, or check dream mode — background reasoning."""

    @property
    def name(self) -> str:
        return "dream"

    @property
    def description(self) -> str:
        return (
            "Dream mode: continuous background reasoning and idea development. "
            "The agent thinks through a topic in the background, writing insights to a dream journal. "
            "Actions: start (begin dreaming), stop (end session), status (check progress), "
            "read (view dream journal)."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["start", "stop", "status", "read", "list"],
                    "description": "start/stop/status/read/list dream sessions",
                },
                "topic": {
                    "type": "string",
                    "description": "Seed topic or problem to think about (for start)",
                },
                "context": {
                    "type": "string",
                    "description": "Additional context to feed the dream (files, ideas, constraints)",
                },
                "iterations": {
                    "type": "integer",
                    "description": "Max thinking iterations (default: 10, max: 50)",
                },
                "model": {
                    "type": "string",
                    "description": "Model to use for dreaming (default: cheapest available)",
                },
                "dream_file": {
                    "type": "string",
                    "description": "Specific dream journal to read (for 'read' action)",
                },
            },
            "required": ["action"],
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        action = args.get("action", "status")

        if action == "start":
            return await self._start_dream(args, context)
        elif action == "stop":
            return await self._stop_dream()
        elif action == "status":
            return self._dream_status()
        elif action == "read":
            return self._read_dream(args)
        elif action == "list":
            return self._list_dreams()
        else:
            return ToolResult(success=False, output="", error=f"Unknown action: {action}")

    async def _start_dream(self, args: dict, context: ToolContext) -> ToolResult:
        global _dream_process, _dream_active

        state = _load_dream_state()
        if state.get("active"):
            return ToolResult(
                success=False, output="",
                error="Dream already active. Use action='stop' first.",
            )

        topic = args.get("topic", "")
        extra_context = args.get("context", "")
        iterations = min(args.get("iterations", 10), 50)
        model = args.get("model", "")

        if not topic:
            return ToolResult(
                success=False, output="",
                error="topic is required — what should I dream about?",
            )

        journal_path = _dream_journal_path(topic)
        DREAM_DIR.mkdir(parents=True, exist_ok=True)

        # Write initial journal header
        journal_path.write_text(
            f"# Dream Journal: {topic}\n"
            f"*Started: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n"
            f"*Model: {model or 'default'}*\n"
            f"*Max iterations: {iterations}*\n\n"
            f"## Seed Context\n{extra_context or '(none)'}\n\n"
            f"---\n\n"
        )

        # Build the dream agent prompt
        dream_prompt = f"""You are in Dream Mode — continuous background reasoning.

## Your Task
Think deeply about: {topic}

{f"## Additional Context{chr(10)}{extra_context}" if extra_context else ""}

## Instructions
You will iterate {iterations} times. Each iteration:
1. Read the dream journal to see your previous thoughts
2. Think deeper — find connections, challenge assumptions, explore alternatives
3. Write your new insights to the journal
4. Each iteration should BUILD on previous ones, not repeat them

## Rules
- Be creative and exploratory — this is dreaming, not executing
- Make unexpected connections between ideas
- Question your own assumptions
- Propose concrete next steps when ideas mature
- Write in a stream-of-consciousness style with clear headers
- Each iteration should be 100-300 words

## Working Directory
{context.cwd}

## Dream Journal
{journal_path}
"""

        # Build the iteration script
        dream_script = f"""
import sys, asyncio, os
sys.path.insert(0, '{context.cwd}')
os.chdir('{context.cwd}')

from pathlib import Path

journal = Path('{journal_path}')
iterations = {iterations}
topic = '''{topic}'''

async def dream_iteration(i, journal_path):
    # Read current journal
    content = journal_path.read_text()

    prompt = f'''You are in Dream Mode, iteration {{i+1}}/{iterations}.
Topic: {topic}

Previous thoughts:
{{content[-3000:]}}

Write your next iteration of thinking. Build on what came before.
Find new angles, challenge assumptions, make connections.
Start with "## Iteration {{i+1}}" and write 100-300 words.
End with a "**Next direction:**" line suggesting where to go next.'''

    # Use the agent's own API to think
    from src.api.client import create_client
    from src.api.models import get_model_config

    model_name = '{model}' or None
    config = get_model_config(model_name) if model_name else get_model_config()
    client = create_client(config)

    response = await client.chat([
        {{"role": "user", "content": prompt}}
    ])

    # Append to journal
    with open(journal_path, 'a') as f:
        f.write(response.content + '\\n\\n')

    return response.content

async def main():
    for i in range(iterations):
        try:
            result = await dream_iteration(i, journal)
            # Brief pause between iterations
            await asyncio.sleep(2)
        except Exception as e:
            with open(journal, 'a') as f:
                f.write(f'\\n## Error at iteration {{i+1}}\\n{{e}}\\n\\n')
            break

    # Write completion marker
    with open(journal, 'a') as f:
        f.write(f'\\n---\\n*Dream completed at {datetime.now().strftime("%Y-%m-%d %H:%M")}*\\n')

asyncio.run(main())
"""

        # Launch as background process
        _dream_process = await asyncio.create_subprocess_exec(
            sys.executable, "-c", dream_script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(context.cwd),
        )

        _dream_active = True
        _save_dream_state({
            "active": True,
            "topic": topic,
            "journal": str(journal_path),
            "pid": _dream_process.pid,
            "iterations": iterations,
            "model": model,
            "started_at": time.time(),
        })

        return ToolResult(
            success=True,
            output=(
                f"💭 **Dream mode activated**\n\n"
                f"- **Topic:** {topic}\n"
                f"- **Iterations:** {iterations}\n"
                f"- **Model:** {model or 'default'}\n"
                f"- **Journal:** `{journal_path}`\n"
                f"- **PID:** {_dream_process.pid}\n\n"
                f"The agent is now thinking in the background. "
                f"Use `dream status` to check progress or `dream read` to view insights."
            ),
            metadata={"journal": str(journal_path), "pid": _dream_process.pid},
        )

    async def _stop_dream(self) -> ToolResult:
        global _dream_process, _dream_active

        state = _load_dream_state()

        if _dream_process and _dream_process.returncode is None:
            _dream_process.terminate()
            try:
                await asyncio.wait_for(_dream_process.communicate(), timeout=5)
            except asyncio.TimeoutError:
                _dream_process.kill()

        _dream_active = False
        journal = state.get("journal", "")

        _save_dream_state({"active": False})

        if journal and Path(journal).exists():
            content = Path(journal).read_text()
            line_count = content.count("\n")
            return ToolResult(
                success=True,
                output=(
                    f"💭 **Dream mode stopped**\n\n"
                    f"Journal: `{journal}` ({line_count} lines)\n"
                    f"Use `dream read` to review the full journal."
                ),
            )

        return ToolResult(success=True, output="💭 Dream mode stopped.")

    def _dream_status(self) -> ToolResult:
        state = _load_dream_state()

        if not state.get("active"):
            return ToolResult(success=True, output="💭 Dream mode is not active.")

        elapsed = time.time() - state.get("started_at", time.time())
        mins = int(elapsed / 60)

        journal = state.get("journal", "")
        iteration_count = 0
        if journal and Path(journal).exists():
            content = Path(journal).read_text()
            iteration_count = content.count("## Iteration")

        return ToolResult(
            success=True,
            output=(
                f"💭 **Dream mode active** ({mins}m elapsed)\n\n"
                f"- **Topic:** {state.get('topic', '?')}\n"
                f"- **Iterations:** {iteration_count}/{state.get('iterations', '?')}\n"
                f"- **Model:** {state.get('model', 'default')}\n"
                f"- **Journal:** `{journal}`\n"
            ),
        )

    def _read_dream(self, args: dict) -> ToolResult:
        dream_file = args.get("dream_file", "")

        if not dream_file:
            # Read the active or most recent dream
            state = _load_dream_state()
            dream_file = state.get("journal", "")

            if not dream_file:
                # Find most recent
                DREAM_DIR.mkdir(parents=True, exist_ok=True)
                journals = sorted(DREAM_DIR.glob("dream-*.md"), reverse=True)
                if journals:
                    dream_file = str(journals[0])

        if not dream_file or not Path(dream_file).exists():
            return ToolResult(success=True, output="No dream journals found.")

        content = Path(dream_file).read_text()
        if len(content) > 10_000:
            content = content[-10_000:]
            content = "... (truncated, showing last 10K chars)\n\n" + content

        return ToolResult(success=True, output=content)

    def _list_dreams(self) -> ToolResult:
        DREAM_DIR.mkdir(parents=True, exist_ok=True)
        journals = sorted(DREAM_DIR.glob("dream-*.md"), reverse=True)

        if not journals:
            return ToolResult(success=True, output="No dream journals yet.")

        lines = ["## 💭 Dream Journals\n"]
        for j in journals[:20]:
            size = j.stat().st_size
            # Read first line for topic
            first_line = j.read_text().split("\n")[0].replace("# Dream Journal: ", "")
            lines.append(f"- **{j.name}** ({size:,} bytes) — {first_line}")

        return ToolResult(success=True, output="\n".join(lines))
