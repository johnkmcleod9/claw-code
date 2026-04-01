# Pathwise Adaptive Harness

A multi-model coding agent harness that adapts to maximize the effectiveness of different LLMs.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set API key (for OpenRouter models)
export OPENROUTER_API_KEY="your-key-here"

# Run a task
python cli.py "Write hello world to hello.py" --model minimax-m2.7
```

## Architecture

```
src/
├── providers/       # LLM provider abstraction (OpenRouter, Anthropic, LM Studio)
├── profiles/        # Model profile loader
├── tools_impl/      # Working tool implementations (file ops, bash, grep, glob)
├── agent/           # Agent loop, context builder, compaction
└── (existing)       # Original claw-code structural port

profiles/            # YAML model profiles (capabilities, costs, tuning)
cli.py              # CLI entry point
```

## Available Models

| Model | Provider | Context | Cost (in/out per M) |
|-------|----------|---------|---------------------|
| `minimax-m2.7` | OpenRouter | 205K | $0.30 / $1.10 |
| `mercury-2` | OpenRouter | 128K | $0.25 / $1.00 |
| `sonnet` | Anthropic | 200K | $3.00 / $15.00 |
| `qwen-3.5-local` | LM Studio | 128K | $0 / $0 |

## CLI Usage

```bash
python cli.py "task description" [options]

Options:
  --model, -m       Model name (matches profiles/*.yaml). Default: minimax-m2.7
  --profile, -p     Path to specific profile YAML
  --max-turns, -t   Maximum agent turns. Default: 10
  --tools           Comma-separated tool filter
  --workdir, -w     Working directory. Default: cwd
  --no-stream       Disable streaming output
```

## Available Tools

- **file_read** — Read file contents (with optional offset/limit)
- **file_write** — Write content to a file
- **file_edit** — Find and replace exact text
- **bash** — Execute shell commands
- **grep** — Regex search across files
- **glob** — Find files matching patterns

## Environment Variables

- `OPENROUTER_API_KEY` — Required for OpenRouter models (MiniMax, Mercury, Qwen via cloud)
- `ANTHROPIC_API_KEY` — Required for direct Anthropic API (Sonnet)

## Adding a New Model

1. Create a YAML file in `profiles/`:
```yaml
name: my-model
provider: openrouter
model_id: org/model-name
context_window: 128000
max_output_tokens: 8192
supports_tool_calling: true
supports_streaming: true
tool_call_format: native
optimal_temperature: 0.7
optimal_top_p: 0.95
system_prompt_style: direct
cost_per_million_input: 0.50
cost_per_million_output: 1.50
strengths: [coding, fast]
weaknesses: [reasoning]
```

2. Run: `python cli.py "test task" --model my-model`

## Project Roadmap

See `PATHWISE-HARNESS-PLAN.md` for the full implementation plan:
- **Phase 1** ✅ Foundation (providers, profiles, tools, agent loop)
- **Phase 2** — Evaluation & calibration framework
- **Phase 3** — Self-improvement loop
- **Phase 4** — Pathwise domain specialization
- **Phase 5** — OpenClaw integration
