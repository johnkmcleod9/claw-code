# Claw Code → Claude Code Parity Plan

## Goal
Port all Claude Code CLI tools and capabilities from the Rust reference implementation
to working Python, making Claw Code a fully functional multi-model alternative.

## Source of Truth
- Tool specs & implementations: `rust/crates/tools/src/lib.rs` (3,500 lines)
- Tool manifest: `src/reference_data/tools_snapshot.json` (184 modules, 43 tools)
- Skill system: `src/reference_data/subsystems/skills.json`

## Status Key
- ✅ Done (working Python)
- 🔨 In progress
- ⬜ Not started

---

## Phase 1: Core Tool Parity (Today)
Tools that make the agent immediately more capable.

| Tool | Status | Notes |
|------|--------|-------|
| bash | ✅ | Working |
| file_read | ✅ | Working |
| file_write | ✅ | Working |
| file_edit | ✅ | Working |
| glob | ✅ | Working |
| grep | ✅ | Working |
| **web_search** | ⬜ | Port from Rust — scrapes Google, extracts hits |
| **web_fetch** | ⬜ | Port from Rust — fetches URL, extracts readable text |
| **todo_write** | ⬜ | Session task list (pending/in_progress/completed) |
| **notebook_edit** | ⬜ | Jupyter notebook cell editing |

## Phase 2: Skills & Context System
What makes Claude Code *smart* about projects.

| Feature | Status | Notes |
|---------|--------|-------|
| **Skill loader** | ⬜ | Load .md skills from skills/ dir, inject into system prompt |
| **CLAUDE.md support** | ⬜ | Auto-load project context files (CLAUDE.md, AGENTS.md) |
| **Memory/remember** | ⬜ | Persistent memory across sessions |
| **Config tool** | ⬜ | Read/write config from within agent |

## Phase 3: Agent Teams (Multi-Agent)
The killer feature — spawn sub-agents for parallel work.

| Tool | Status | Notes |
|------|--------|-------|
| **Agent (spawn)** | ⬜ | Launch sub-agent with own model/prompt/tools |
| **Task create/get/list/update/stop/output** | ⬜ | Task management for sub-agents |
| **Team create/delete** | ⬜ | Named agent teams |
| **SendMessage** | ⬜ | Inter-agent messaging |

## Phase 4: Developer Experience
| Feature | Status | Notes |
|---------|--------|-------|
| **ToolSearch** | ⬜ | Search available tools by keyword |
| **Plan mode** | ⬜ | Think before acting (no tool execution) |
| **Worktree mode** | ⬜ | Git worktree isolation |
| **Brief tool** | ⬜ | Summarize long outputs |
| **REPL tool** | ⬜ | In-process Python/Node REPL |
| **LSP tool** | ⬜ | Language server protocol integration |
| **Sleep tool** | ⬜ | Pause execution |

## Phase 5: MCP Integration
| Feature | Status | Notes |
|---------|--------|-------|
| **MCP client** | ⬜ | Connect to MCP servers (stdio + HTTP) |
| **ListMcpResources** | ⬜ | Discover MCP server capabilities |
| **ReadMcpResource** | ⬜ | Read from MCP resources |
| **McpAuth** | ⬜ | OAuth for MCP servers |

---

## Implementation Order (optimized for impact)
1. web_search + web_fetch (immediate capability boost)
2. todo_write (session task tracking)
3. Skill loader + CLAUDE.md (project awareness)
4. Agent spawn + task tools (multi-agent)
5. MCP client (ecosystem integration)
6. Everything else (plan mode, LSP, worktree, etc.)
