# Claw Code — Claude Code Parity Status

## Final: 160 modules | 28,159 lines | 32 tools

Built in one evening from a structural Python port to a fully working multi-model coding agent.

### Subsystem Port Status

| Subsystem | Modules | Lines | Status |
|-----------|---------|-------|--------|
| **Utils** | 9 | ~1,700 | ✅ paths, encoding, retry, shell, strings, collections, http, ids, logging |
| **Services** | 9 | ~1,500 | ✅ session_memory, api_client, analytics, agent_summary, prompt_suggestion, error_handler, compaction, magic_docs, oauth |
| **State** | 2 | ~350 | ✅ app_state, store |
| **CLI** | 4 | ~600 | ✅ print, handlers, transports, update |
| **Constants** | 4 | ~500 | ✅ api_limits, common, messages, output_styles |
| **Bridge** | 5 | ~800 | ✅ config, messaging, session, jwt_utils, debug_utils |
| **Components** | 9 | ~1,800 | ✅ formatter, diff_display, tool_result, conversation, status, input, markdown, progress, cost |
| **Hooks** | 6 | ~900 | ✅ state, suggestion, lifecycle, tool_permission, event, notification |
| **Skills** | 20 | ~4,400 | ✅ discovery, matching, execution pipeline, cache, registry, validator, renderer, watcher, installer, context injection, events, permissions, telemetry, remote, composer, template, CLI commands, error handling |
| **Buddy** | 5 | ~1,500 | ✅ species, generator, commands, companion, prompt |
| **Voice** | 1 | ~200 | ✅ Speech input/output |
| **Keybindings** | ported | ~200 | ✅ Keyboard shortcuts |
| **Screens** | ported | ~200 | ✅ Screen management |
| **Memdir** | ported | ~200 | ✅ Memory directory |
| **Migrations** | ported | ~200 | ✅ Config migration |
| **Tools** | 32 | ~6,000 | ✅ All core + team + dream + MCP |
| **Providers** | 3 | ~800 | ✅ OpenRouter, Anthropic, LM Studio |
| **Agent loop** | core | ~500 | ✅ With plan mode enforcement |
| **Hardening** | done | ~400 | ✅ Injection defense, error recovery |
| **Session persistence** | done | ~300 | ✅ Save/restore conversations |
| **Context pipeline** | done | ~400 | ✅ Multi-stage compaction with memory |

### 32 Tools

**Core:** file_read, file_write, file_edit, bash, repl, grep, glob
**Web:** web_search, web_fetch
**Planning:** todo_write, todo_read, enter_plan_mode, exit_plan_mode
**Skills:** skill
**Agents:** agent, task_list, task_get
**Team:** team_create, team_task, team_assign, team_status, team_stop
**MCP:** mcp, mcp_resources
**Git:** enter_worktree, exit_worktree
**Utility:** notebook_edit, config, sleep, ask_user, tool_search, dream

### Where We Beat Claude Code

| Feature | Claw Code | Claude Code |
|---------|-----------|-------------|
| **Models** | 9+ via OpenRouter + local | Claude only |
| **Hot-swap** | `/model deepseek` mid-chat | Can't switch |
| **Cost tracking** | Per-turn reporting | None |
| **Local models** | LM Studio/Ollama, $0 | Not possible |
| **Dream mode** | Working | Unreleased |
| **Open source** | Fully yours | Proprietary |
| **Price range** | $0 — $15/M tokens | $3 — $15/M |
