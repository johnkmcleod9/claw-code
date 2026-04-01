# Pathwise Adaptive Harness — Implementation Plan

**Project:** Self-improving, model-agnostic coding agent harness adapted from Claude Code architecture
**Origin:** Claude Code source leak (Mar 31, 2026) → claw-code clean-room Python rewrite
**Goal:** Build a harness that adapts itself to maximize the effectiveness of cheaper/open-source models (MiniMax M2.7, Mercury 2, Qwen 3.5) for Pathwise's work

---

## The Big Idea

The Claude Code leak revealed the architecture of a world-class agent harness: ~40 tools, permission gating, multi-agent orchestration, persistent memory, query engine with streaming and compaction. But it's Claude-only.

The insight from shareAI-lab's analysis: **the agent is the model, the harness is the vehicle.** A great harness gives any capable model the right tools, context, and workflow to punch above its weight.

MiniMax proved this internally — they had M2.7 run 100+ autonomous iterations to evolve its own harness, discovering optimal sampling parameters, workflow guidelines, and tool implementations. **The harness itself becomes the competitive advantage, not just the model.**

### What Does "Harness Quality" Actually Buy You?

Based on the Claude Code architecture and MiniMax's published results:

| Harness Feature | Impact on Smaller Models |
|---|---|
| **Structured tool definitions** | Models with weaker instruction-following can still reliably call tools when schemas are tight and well-documented |
| **Context management (compaction)** | Critical for models with smaller context windows — auto-summarize to keep relevant info in view |
| **Permission gating** | Prevents catastrophic failures that smaller models are more prone to |
| **Multi-step scaffolding** | Breaks complex tasks into steps small enough for weaker reasoners |
| **Persistent memory** | Compensates for smaller context windows by persisting decisions across sessions |
| **Domain-specific skills** | Pre-built workflows reduce the reasoning burden — model follows rails instead of inventing |
| **Evaluation + retry loops** | Catch failures and re-prompt with targeted feedback |
| **Prompt engineering per model** | Each model responds differently to instruction style, examples, chain-of-thought |

MiniMax's data point: M2.7 maintains **97% skill adherence** when working with 40+ complex skills. The harness makes the model reliable, not just capable.

---

## Architecture Overview (from claw-code analysis)

### What We Have (claw-code Python rewrite)
```
src/
├── query_engine.py    — Turn loop, streaming, compaction, budget tracking
├── runtime.py         — Prompt routing, session bootstrap, tool/command matching
├── tools.py           — Tool registry, permission filtering, execution
├── commands.py        — Command registry and execution
├── models.py          — Core data models (PortingModule, UsageSummary, etc.)
├── permissions.py     — Tool permission gating
├── context.py         — Workspace context building
├── session_store.py   — Session persistence
├── transcript.py      — Conversation transcript management
├── setup.py           — Environment detection and startup
└── reference_data/    — Snapshots of Claude Code's 40 tools and 50+ commands
```

### What's Missing (needs building)
1. **Actual LLM API integration** — claw-code is a structural port, not a working runtime yet
2. **Provider abstraction layer** — swap models via config
3. **Tool execution engine** — tools are mirrored but don't execute
4. **Model-specific prompt profiles** — tuned system prompts per model
5. **Self-improvement loop** — the meta-harness layer
6. **Domain skills** — Pathwise-specific workflows

---

## Phase 1: Foundation — Working Multi-Model Runtime (Week 1-2)

### 1.1 Provider Abstraction Layer
Build an LLM provider interface that routes to any model via OpenRouter (or direct API).

```python
# providers/base.py
class LLMProvider(Protocol):
    async def complete(self, messages: list[Message], tools: list[ToolDef], 
                       config: ModelConfig) -> CompletionResult: ...
    async def stream(self, messages: list[Message], tools: list[ToolDef],
                     config: ModelConfig) -> AsyncIterator[StreamEvent]: ...

# providers/openrouter.py — covers MiniMax, Mercury, Qwen, etc.
# providers/anthropic.py — direct Anthropic API for Claude
# providers/lmstudio.py — local models (Qwen, Nemotron)
```

### 1.2 Model Profiles
Each model gets a config that captures its capabilities and optimal settings.

```python
@dataclass
class ModelProfile:
    name: str                          # e.g., "minimax-m2.7"
    provider: str                      # "openrouter" | "anthropic" | "lmstudio"
    model_id: str                      # "minimax/minimax-m2.7"
    context_window: int                # 205000
    max_output_tokens: int             # 16384
    supports_tool_calling: bool        # True
    supports_structured_output: bool   # True
    supports_streaming: bool           # True
    tool_call_format: str              # "native" | "xml" | "json_block"
    optimal_temperature: float         # 0.7
    optimal_top_p: float               # 0.95
    system_prompt_style: str           # "direct" | "example_heavy" | "chain_of_thought"
    cost_per_million_input: float      # 0.30
    cost_per_million_output: float     # 1.10
    strengths: list[str]               # ["coding", "structured_output", "long_context"]
    weaknesses: list[str]              # ["spatial_reasoning", "math"]
    prompt_template: str               # Path to model-specific system prompt
    
    # Self-improvement fields (evolved over time)
    evolved_settings: dict             # Learned optimal parameters
    skill_adherence_scores: dict       # Per-skill success rates
    last_calibration: datetime         # When last evaluated
```

### 1.3 Tool Execution Engine
Make the 40 mirrored tools actually work. Priority order:

| Priority | Tool | Why |
|---|---|---|
| P0 | FileRead, FileWrite, FileEdit | Core file operations |
| P0 | BashTool | Shell execution with sandboxing |
| P0 | Grep, Glob | Code search |
| P1 | WebFetch | Research and documentation |
| P1 | AgentTool (sub-agents) | Multi-agent orchestration |
| P1 | LSP integration | Code intelligence |
| P2 | MCP bridge | External tool servers |
| P2 | Git operations | Version control |
| P3 | Browser, Screenshot | Visual tasks |

### 1.4 Strip Anthropic-Specific Code
Remove: anti-distillation, client attestation, undercover mode, GrowthBook feature flags, Bun-specific Zig hooks.

**Deliverable:** A working CLI that can run the same coding task against Claude, MiniMax, Mercury, and Qwen, using the same tool set.

---

## Phase 2: Evaluation & Calibration Framework (Week 2-3)

### 2.1 Task Benchmark Suite
Build a test suite of representative tasks across Pathwise domains:

**Software Engineering Tasks:**
- Single-file bug fix (Python/JS)
- Multi-file refactor
- Write tests for existing code
- Create new module from spec
- Git operations (branch, commit, PR)

**Pathwise eLearning Tasks:**
- Generate Rise 360 storyboard from design doc
- Create Twine branching scenario from learning objectives
- Write SCORM package metadata
- Review course content against accessibility checklist
- Generate assessment items from content

**Business Operations Tasks:**
- Draft proposal from template + requirements
- Create financial summary from spreadsheet data
- Write marketing copy from brief
- Generate meeting notes from transcript
- Research competitor and produce analysis

**Document Tasks:**
- Create branded .docx from outline
- Build .pptx presentation
- Populate .xlsx with formulas
- PDF form filling and extraction

### 2.2 Evaluation Scoring
For each task + model combination:

```python
@dataclass
class TaskResult:
    model: str
    task_id: str
    completed: bool
    tool_calls_made: int
    tool_call_success_rate: float
    turns_used: int
    tokens_consumed: int
    cost_usd: float
    time_seconds: float
    quality_score: float          # 0-1, judged by evaluator model
    skill_adherence: float        # Did it follow the prescribed workflow?
    failure_analysis: str | None  # Why did it fail, if it did?
```

### 2.3 Calibration Runs
Run each model through the full benchmark suite. Build a capability matrix:

```
Model          | Code Fix | Refactor | Storyboard | Proposal | Doc Gen | Cost/task
---------------|----------|----------|------------|----------|---------|----------
Claude Opus    | 0.95     | 0.88     | 0.92       | 0.90     | 0.93    | $0.85
Claude Sonnet  | 0.92     | 0.85     | 0.88       | 0.87     | 0.90    | $0.25
MiniMax M2.7   | 0.87     | 0.78     | ???        | ???      | 0.85    | $0.05
Mercury 2      | 0.82     | 0.70     | ???        | ???      | ???     | $0.02
Qwen 3.5 local | 0.75     | 0.60     | ???        | ???      | 0.70    | $0.00
```

**Deliverable:** A capability matrix that tells us which model to route each task type to.

---

## Phase 3: The Self-Improvement Loop (Week 3-4)

This is the meta-harness — the part that makes the system evolve.

### 3.1 Architecture

```
┌─────────────────────────────────────────────┐
│              Meta-Harness Controller         │
│  (Opus/Sonnet — the "Architect")            │
├─────────────────────────────────────────────┤
│                                             │
│  1. Run task → Worker model (Mercury/MiniMax)│
│  2. Evaluate result → Architect scores it    │
│  3. If failure:                              │
│     a. Architect analyzes failure trajectory │
│     b. Generates improved prompt/tool config │
│     c. Writes changes to model profile       │
│  4. Re-run task with evolved profile         │
│  5. Compare before/after scores              │
│  6. Keep improvement or revert               │
│  7. Repeat                                   │
│                                             │
│  Loop runs N iterations per task type        │
│  Best profiles get persisted                 │
└─────────────────────────────────────────────┘
```

### 3.2 What Can the Self-Improvement Loop Evolve?

Drawing from MiniMax's published approach:

1. **Sampling parameters** — Temperature, top_p, frequency penalty, presence penalty. MiniMax found optimal combinations through systematic search.

2. **System prompt wording** — Different models respond to different instruction styles. The loop discovers what works.

3. **Tool descriptions** — How tools are described to the model matters enormously. Tighter schemas, better examples, explicit constraints.

4. **Workflow scaffolding** — Adding intermediate steps. E.g., "Before editing a file, always read it first and summarize what you see." Some models need this; others don't.

5. **Error recovery patterns** — "When you get error X, try approach Y." Built from observed failure patterns.

6. **Skill templates** — Pre-built multi-step workflows for common tasks. The loop discovers which steps to add/remove per model.

7. **Context management** — Optimal compaction thresholds, what to keep in context vs. persist to memory.

### 3.3 Safety Rails

- **Architect model is always Opus/Sonnet** — the evaluator should be stronger than the worker
- **Changes are versioned** — every profile evolution is a git commit
- **Regression testing** — evolved profiles must pass existing benchmarks, not just the new task
- **Human review gate** — significant profile changes get flagged for John to review
- **Cost caps** — self-improvement runs have token budgets

---

## Phase 4: Pathwise Domain Specialization (Week 4-6)

### 4.1 eLearning Skills

Build harness skills (like OpenClaw skills) that encode Pathwise's domain expertise:

| Skill | What It Encodes |
|---|---|
| **rise-storyboard** | Screen types, block specifications, narrative patterns, Rise 360 constraints |
| **action-mapping** | Cathy Moore's methodology, decision-to-action workflows |
| **accessibility-audit** | WCAG 2.1 AA checklist, remediation patterns |
| **content-audit** | Source material cataloging, gap analysis templates |
| **assessment-design** | Item writing rules, Bloom's taxonomy mapping |
| **scorm-packaging** | Metadata standards, LMS integration specs |

These skills act as **domain rails** that constrain the model's output space. A smaller model following a well-designed skill can match or exceed a larger model working from general knowledge.

### 4.2 Business Operations Skills

| Skill | What It Encodes |
|---|---|
| **proposal-writer** | Pathwise templates, brand voice, pricing structures |
| **financial-report** | Standard formats, KPI calculations, data sources |
| **marketing-brief** | Campaign templates, audience profiles, channel specs |
| **meeting-facilitator** | Agenda templates, note-taking format, action item extraction |
| **client-research** | Research workflow, competitive analysis template |

### 4.3 How Skills Amplify Smaller Models

The key insight: **a skill narrows the solution space.** Instead of asking a model to "write a storyboard" (infinite possibilities), you give it:
- A template with specific fields to fill
- Examples of good output
- Constraints on format and content
- Validation rules to check against

This is why MiniMax reports 97% skill adherence — well-structured skills turn open-ended generation into structured completion, which is exactly where smaller models shine.

**Real example from our stack:** Our Rise storyboard skill already encodes screen types, Rise block specs, and narrative patterns. Running it through Mercury would cost ~$0.02/storyboard vs ~$0.85 through Opus. If the harness can get Mercury to 80% quality with the skill, and we use Opus only for the final quality check, that's a massive cost reduction.

---

## Phase 5: Integration with OpenClaw (Week 6-8)

### 5.1 Harness as ACP Runtime
Package the evolved harness as an ACP-compatible agent that OpenClaw can spawn:

```yaml
# Agent config for the adaptive harness
agent:
  name: "pathwise-harness"
  runtime: "acp"
  model_selection: "auto"  # Routes to cheapest capable model
  fallback_chain:
    - "mercury"      # Try cheapest first
    - "minimax"      # Fall back to mid-tier
    - "sonnet"       # Fall back to premium
  skills_dir: "./skills/"
  profiles_dir: "./profiles/"
```

### 5.2 Task Router
Integrate with our existing Best-of-N pipeline:

```
User request → Task classifier → Model selector → Harness execution
                                       ↓
                              Capability matrix lookup
                              (from Phase 2 calibration)
                                       ↓
                              Route to cheapest model
                              that meets quality threshold
```

### 5.3 Continuous Improvement
Set up a cron-driven calibration loop:
- Weekly: Re-run benchmark suite against all models
- Monthly: Full self-improvement iteration
- On-demand: When a new model is added or updated

---

## How Adaptable Is a Great Harness?

### The Evidence

1. **MiniMax M2.7** — Built its own research harness, ran 100+ self-improvement iterations, handles 30-50% of their ML workflow autonomously. Their M2.5 (previous gen) matches Opus 4.5 on SWE-Bench when given the right harness.

2. **Claude Code itself** — The leaked architecture shows that Claude's "magic" is substantially harness engineering. The 46K-line query engine, the 40 tools, the compaction system — these are what make Claude Code effective, not just Claude being smart.

3. **OpenClaw's skill system** — We already see this. Saphira with the Rise storyboard skill produces better storyboards than Opus without it. The skill IS the harness.

### Practical Limits

**Where smaller models still struggle:**
- Novel architectural decisions (no skill to follow)
- Tasks requiring very long reasoning chains (>20 steps)
- Ambiguous requirements needing human-like judgment
- Cross-domain synthesis (connecting unrelated concepts)

**Where harness quality closes the gap:**
- Structured document creation (templates + validation)
- Code following established patterns (skills + examples)
- Multi-step workflows with clear checkpoints
- Tasks where "good enough" output can be refined by a stronger model

### The Pathwise Sweet Spot

For our work, I estimate a well-tuned harness could route **60-70% of tasks** to cheap models:
- Storyboard drafting → MiniMax ($0.05/storyboard)
- Code scaffolding → Mercury ($0.02/module)
- Document generation → Qwen local ($0.00)
- Content audits → MiniMax ($0.10/audit)
- Quality evaluation → Sonnet ($0.25/review, reserved for judgment calls)
- Novel design work → Opus ($0.85/session, only when needed)

**Projected cost impact:** If 65% of current Opus usage shifts to cheap models, that's roughly 80% cost reduction on those tasks.

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| claw-code gets DMCA'd | We're building on the architecture patterns, not the source. Fork is already divergent. |
| Self-improvement loop goes sideways | Regression tests, cost caps, human review gates |
| Model API changes break profiles | Provider abstraction layer; profiles are model-version-specific |
| Evaluation model bias | Use multiple evaluators; cross-validate with human scores |
| Over-optimization for benchmarks | Include real Pathwise tasks in benchmark suite, not just synthetic |

---

## Immediate Next Steps

1. **Star claw-code** ✅ (cloned to `projects/claw-code`)
2. **Build provider abstraction** — Start with OpenRouter, which gives us MiniMax + Mercury immediately
3. **Implement P0 tools** — FileRead, FileWrite, FileEdit, BashTool, Grep
4. **Create first model profiles** — MiniMax M2.7, Mercury 2, Qwen 3.5 (35B)
5. **Build evaluation harness** — Start with 5 representative tasks per domain
6. **Run first calibration** — Baseline scores for all models
7. **First self-improvement iteration** — Let Sonnet evolve Mercury's profile on coding tasks

---

## Who Does What

| Agent | Role |
|---|---|
| **Devon** | Primary implementer — builds the harness runtime |
| **Saphira** | Architecture oversight, plan management, evaluation design |
| **Petra** | Project tracking in OpenProject |
| **John** | Review gates, Pathwise domain expertise, skill design |

---

*This plan was informed by: Claude Code source analysis (claw-code), MiniMax M2.7 self-evolution paper, shareAI-lab harness engineering thesis, and Pathwise's existing skill/pipeline architecture.*
