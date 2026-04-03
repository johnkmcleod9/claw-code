"""
MCPTool — Connect to Model Context Protocol servers.

Supports both stdio and HTTP (streamable) MCP servers.
Discovers tools from MCP servers and makes them available to the agent.
Config: ~/.claw-code/mcp.json or project-local .mcp.json
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

import httpx

from .base import Tool, ToolContext, ToolResult

MCP_CONFIG_PATHS = [
    Path.home() / ".claw-code" / "mcp.json",
    Path(".mcp.json"),
    Path(".claude" / Path("mcp.json")),
]

# Cache for discovered MCP tools
_mcp_servers: dict[str, dict] = {}
_mcp_tools_cache: dict[str, list[dict]] = {}


def _load_mcp_config(cwd: Path) -> dict:
    """Load MCP server configurations."""
    configs = {}
    # Check all config paths
    for config_path in MCP_CONFIG_PATHS:
        if not config_path.is_absolute():
            config_path = cwd / config_path
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text())
                servers = data.get("mcpServers", data.get("servers", {}))
                configs.update(servers)
            except Exception:
                pass
    return configs


async def _call_stdio_server(command: str, args: list[str], method: str,
                              params: dict | None = None, env: dict | None = None,
                              timeout: float = 30.0) -> dict:
    """Call an MCP server via stdio (JSON-RPC over stdin/stdout)."""
    request = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": method,
    }
    if params:
        request["params"] = params

    full_env = {**os.environ, **(env or {})}

    proc = await asyncio.create_subprocess_exec(
        command, *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=full_env,
    )

    # Send initialize first, then the actual request
    init_request = {
        "jsonrpc": "2.0",
        "id": "init-1",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "claw-code", "version": "0.1.0"},
        },
    }

    messages = json.dumps(init_request) + "\n" + json.dumps(request) + "\n"

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(messages.encode()),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        raise TimeoutError(f"MCP server timed out after {timeout}s")

    # Parse responses (one per line)
    responses = []
    for line in stdout.decode().strip().split("\n"):
        line = line.strip()
        if line:
            try:
                responses.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    # Return the last non-init response
    for resp in reversed(responses):
        if resp.get("id") != "init-1":
            return resp

    if responses:
        return responses[-1]
    raise RuntimeError(f"No valid response from MCP server. stderr: {stderr.decode()[:500]}")


async def _call_http_server(url: str, method: str, params: dict | None = None,
                             headers: dict | None = None, timeout: float = 30.0) -> dict:
    """Call an MCP server via HTTP."""
    request = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": method,
    }
    if params:
        request["params"] = params

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            url,
            json=request,
            headers={"Content-Type": "application/json", **(headers or {})},
        )
        resp.raise_for_status()
        return resp.json()


async def _discover_tools(server_name: str, server_config: dict, cwd: Path) -> list[dict]:
    """Discover tools from an MCP server."""
    if server_name in _mcp_tools_cache:
        return _mcp_tools_cache[server_name]

    transport = server_config.get("transport", "stdio")
    tools = []

    try:
        if transport == "stdio":
            command = server_config.get("command", "")
            args = server_config.get("args", [])
            env = server_config.get("env", {})
            result = await _call_stdio_server(command, args, "tools/list", env=env)
        elif transport in ("http", "sse"):
            url = server_config.get("url", "")
            headers = server_config.get("headers", {})
            result = await _call_http_server(url, "tools/list", headers=headers)
        else:
            return []

        if "result" in result:
            tools = result["result"].get("tools", [])
    except Exception as e:
        tools = [{"name": f"_error_{server_name}", "description": f"Failed to discover: {e}"}]

    _mcp_tools_cache[server_name] = tools
    return tools


async def _call_tool(server_name: str, server_config: dict, tool_name: str,
                      arguments: dict) -> dict:
    """Call a tool on an MCP server."""
    transport = server_config.get("transport", "stdio")
    params = {"name": tool_name, "arguments": arguments}

    if transport == "stdio":
        command = server_config.get("command", "")
        args = server_config.get("args", [])
        env = server_config.get("env", {})
        return await _call_stdio_server(command, args, "tools/call", params=params, env=env)
    elif transport in ("http", "sse"):
        url = server_config.get("url", "")
        headers = server_config.get("headers", {})
        return await _call_http_server(url, "tools/call", params=params, headers=headers)
    else:
        raise ValueError(f"Unsupported transport: {transport}")


class MCPTool(Tool):
    """Call tools on MCP servers."""

    @property
    def name(self) -> str:
        return "mcp"

    @property
    def description(self) -> str:
        return (
            "Call a tool on a connected MCP (Model Context Protocol) server. "
            "Use action='list' to discover available servers and tools. "
            "Use action='call' with server, tool, and arguments to execute."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "call"],
                    "description": "list = discover servers/tools, call = execute a tool",
                },
                "server": {
                    "type": "string",
                    "description": "Server name (from mcp.json config)",
                },
                "tool": {
                    "type": "string",
                    "description": "Tool name to call",
                },
                "arguments": {
                    "type": "object",
                    "description": "Arguments to pass to the tool",
                },
            },
            "required": ["action"],
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        action = args.get("action", "list")
        configs = _load_mcp_config(context.cwd)

        if action == "list":
            if not configs:
                return ToolResult(
                    success=True,
                    output=(
                        "No MCP servers configured.\n\n"
                        "Create ~/.claw-code/mcp.json or .mcp.json with:\n"
                        '```json\n{\n  "mcpServers": {\n    "my-server": {\n'
                        '      "transport": "stdio",\n      "command": "npx",\n'
                        '      "args": ["-y", "@my/mcp-server"]\n    }\n  }\n}\n```'
                    ),
                )

            lines = ["## MCP Servers\n"]
            for name, config in configs.items():
                transport = config.get("transport", "stdio")
                lines.append(f"### {name} ({transport})")

                try:
                    tools = await _discover_tools(name, config, context.cwd)
                    for tool in tools:
                        tool_name = tool.get("name", "unknown")
                        tool_desc = tool.get("description", "")[:80]
                        lines.append(f"  - **{tool_name}**: {tool_desc}")
                    if not tools:
                        lines.append("  *(no tools discovered)*")
                except Exception as e:
                    lines.append(f"  ⚠️ Error: {e}")
                lines.append("")

            return ToolResult(success=True, output="\n".join(lines))

        elif action == "call":
            server_name = args.get("server", "")
            tool_name = args.get("tool", "")
            arguments = args.get("arguments", {})

            if not server_name:
                return ToolResult(success=False, output="", error="server is required for action='call'")
            if not tool_name:
                return ToolResult(success=False, output="", error="tool is required for action='call'")
            if server_name not in configs:
                return ToolResult(
                    success=False, output="",
                    error=f"Unknown server: {server_name}. Available: {', '.join(configs)}",
                )

            try:
                result = await _call_tool(server_name, configs[server_name], tool_name, arguments)

                if "error" in result:
                    error = result["error"]
                    msg = error.get("message", str(error)) if isinstance(error, dict) else str(error)
                    return ToolResult(success=False, output="", error=f"MCP error: {msg}")

                output = result.get("result", {})
                # Extract content from MCP response format
                if isinstance(output, dict) and "content" in output:
                    content_parts = output["content"]
                    text_parts = []
                    for part in content_parts:
                        if isinstance(part, dict):
                            if part.get("type") == "text":
                                text_parts.append(part.get("text", ""))
                            else:
                                text_parts.append(json.dumps(part))
                        else:
                            text_parts.append(str(part))
                    return ToolResult(success=True, output="\n".join(text_parts))
                else:
                    return ToolResult(
                        success=True,
                        output=json.dumps(output, indent=2) if isinstance(output, (dict, list)) else str(output),
                    )

            except Exception as e:
                return ToolResult(success=False, output="", error=f"MCP call failed: {e}")

        return ToolResult(success=False, output="", error=f"Unknown action: {action}")


class ListMcpResourcesTool(Tool):
    """List resources from MCP servers."""

    @property
    def name(self) -> str:
        return "mcp_resources"

    @property
    def description(self) -> str:
        return "List available resources from MCP servers (files, data, etc.)"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "server": {
                    "type": "string",
                    "description": "Server name to query (omit for all servers)",
                },
            },
        }

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        configs = _load_mcp_config(context.cwd)
        server_filter = args.get("server")

        if not configs:
            return ToolResult(success=True, output="No MCP servers configured.")

        lines = ["## MCP Resources\n"]
        for name, config in configs.items():
            if server_filter and name != server_filter:
                continue

            transport = config.get("transport", "stdio")
            try:
                if transport == "stdio":
                    result = await _call_stdio_server(
                        config.get("command", ""), config.get("args", []),
                        "resources/list", env=config.get("env", {}),
                    )
                else:
                    result = await _call_http_server(
                        config.get("url", ""), "resources/list",
                        headers=config.get("headers", {}),
                    )

                resources = result.get("result", {}).get("resources", [])
                lines.append(f"### {name}")
                for res in resources:
                    lines.append(f"  - **{res.get('name', 'unknown')}**: {res.get('description', '')}")
                    lines.append(f"    URI: {res.get('uri', '')}")
                if not resources:
                    lines.append("  *(no resources)*")
            except Exception as e:
                lines.append(f"### {name}\n  ⚠️ Error: {e}")
            lines.append("")

        return ToolResult(success=True, output="\n".join(lines))
