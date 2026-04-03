# Claw Code — Claude Code Parity Tracker

## Current: 26 tools (vs Claude Code's ~25 active tools)

### ✅ Complete — All Core Capabilities

| Capability | Claude Code | Claw Code | Notes |
|-----------|------------|-----------|-------|
| File read/write/edit | ✅ | ✅ | Full parity |
| Bash/shell execution | ✅ | ✅ | With approval gates |
| Grep + glob search | ✅ | ✅ | Full parity |
| Web search | ✅ | ✅ | DuckDuckGo + Google fallback |
| Web fetch (URL → text) | ✅ | ✅ | HTML-to-markdown extraction |
| Todo/task tracking | ✅ | ✅ | Session + file persistence |
| Skills (.md loading) | ✅ | ✅ | Project + global dirs |
| CLAUDE.md / AGENTS.md | ✅ | ✅ | Auto-loads from project root |
| Sub-agent spawning | ✅ | ✅ | Background process + task get |
| Task management | ✅ | ✅ | list/get/monitor |
| MCP integration | ✅ | ✅ | stdio + HTTP transports |
| MCP resource listing | ✅ | ✅ | Full parity |
| REPL (Python/JS/shell) | �� | ✅ | + Ruby |
| Notebook editing | ✅ | ✅ | Jupyter .ipynb |
| Plan mode (read-only) | ✅ | ✅ | Blocks write tools |
| Git worktree isolation | ✅ | ✅ | Create/merge/discard |
| Config read/write | ✅ | ✅ | From within agent |
| Ask user questions | ✅ | ✅ | Interactive prompt |
| Tool search | ✅ | ✅ | Search by keyword |
| Sleep/pause | ✅ | ✅ | Async sleep |
| Streaming output | ✅ | ✅ | Full parity |
| Context compaction | ✅ | ✅ | Token-based |
| Cost tracking | ❌ | ✅ | **We're ahead** |
| Multi-model support | ❌ | ✅ | **9 models, hot-swap** |
| Approval gates (Y/n/a) | ✅ | ✅ | Full parity |

### ⬜ Not Ported (low priority / platform-specific)

| Feature | Reason |
|---------|--------|
| LSP (Language Server) | Complex; bash + grep covers most use cases |
| PowerShell | macOS/Linux focused |
| Structured Output | Niche use case |
| Remote Trigger | Server-specific |
| Cron Scheduling | OS-level, not agent concern |
| SendMessage (Slack etc.) | Platform-specific integration |

### 🚀 Where We're Ahead of Claude Code

1. **Multi-model**: 9 models via OpenRouter + local LM Studio (Claude Code: Claude only)
2. **Cost tracking**: Per-turn and per-session cost reporting
3. **Model hot-swap**: `/model deepseek` mid-conversation
4. **Price optimization**: Use cheap models ($0.14/M) for iteration, quality models for final pass
5. **MCP config compatibility**: Reads Claude's .claude/mcp.json format
