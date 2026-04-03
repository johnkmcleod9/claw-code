"""
ConfigTool — Read and write Claw Code configuration from within the agent.

Ported from rust/crates/tools/src/lib.rs execute_config().
"""
from __future__ import annotations

import json
from pathlib import Path

from .base import Tool, ToolContext, ToolResult

CONFIG_PATH = Path.home() / ".claw-code" / "config.json"

SUPPORTED_SETTINGS = {
    "default_model": {"type": "string", "description": "Default model to use"},
    "approval_mode": {"type": "boolean", "description": "Require approval for tool calls"},
    "max_turns": {"type": "integer", "description": "Maximum agent turns per interaction"},
}


class ConfigTool(Tool):
    @property
    def name(self) -> str:
        return "config"

    @property
    def description(self) -> str:
        return (
            "Read or write Claw Code configuration settings. "
            "Use without value to read, with value to set. "
            "Settings: default_model, approval_mode, max_turns."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "setting": {
                    "type": "string",
                    "description": "Setting name to read or write",
                },
                "value": {
                    "type": "string",
                    "description": "New value to set (omit to read current value)",
                },
            },
            "required": ["setting"],
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        setting = args.get("setting", "").strip()
        value = args.get("value")

        if not setting:
            return ToolResult(success=False, output="", error="setting is required")

        if setting == "list":
            lines = ["Available settings:\n"]
            for name, spec in SUPPORTED_SETTINGS.items():
                lines.append(f"- **{name}** ({spec['type']}): {spec['description']}")
            return ToolResult(success=True, output="\n".join(lines))

        if setting not in SUPPORTED_SETTINGS:
            return ToolResult(
                success=False, output="",
                error=f"Unknown setting: {setting}. Available: {', '.join(SUPPORTED_SETTINGS)}",
            )

        # Read config
        config = {}
        if CONFIG_PATH.exists():
            try:
                config = json.loads(CONFIG_PATH.read_text())
            except Exception:
                pass

        if value is None:
            # Read mode
            current = config.get(setting, "(not set)")
            return ToolResult(
                success=True,
                output=f"{setting} = {json.dumps(current)}",
            )

        # Write mode
        spec = SUPPORTED_SETTINGS[setting]
        previous = config.get(setting)

        # Type coercion
        if spec["type"] == "boolean":
            value = value.lower() in ("true", "1", "yes", "on")
        elif spec["type"] == "integer":
            try:
                value = int(value)
            except ValueError:
                return ToolResult(success=False, output="", error=f"Invalid integer: {value}")

        config[setting] = value
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(config, indent=2))

        return ToolResult(
            success=True,
            output=f"✅ {setting}: {json.dumps(previous)} → {json.dumps(value)}",
        )
