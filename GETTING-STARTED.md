# 🐾 Claw Code — Getting Started

## Install (one-time setup)

### 1. Clone the repo
```bash
git clone https://github.com/johnkmcleod9/claw-code.git
cd claw-code
```

### 2. Install Python dependencies
```bash
pip3 install httpx pyyaml anthropic
```

### 3. Set up your OpenRouter API key
```bash
mkdir -p ~/.claw-code
echo "OPENROUTER_API_KEY=your-key-here" > ~/.claw-code/.env
chmod 600 ~/.claw-code/.env
```

Get your key at: https://openrouter.ai/keys

### 4. (Optional) Add to your PATH
```bash
# Add this line to your ~/.zshrc or ~/.bashrc:
export PATH="$HOME/path-to/claw-code:$PATH"
```

Then you can run `claw` from anywhere.

---

## Usage

### Interactive mode (REPL)
```bash
./claw                           # Start with default model (DeepSeek)
./claw -m sonnet                 # Start with Claude Sonnet
./claw -w ~/myproject            # Start in a specific directory
```

### One-shot mode
```bash
./claw -t "Create a hello world script" -w ~/myproject
./claw -t "Fix the bug in main.py" -m sonnet -w ~/myproject
```

---

## REPL Commands

| Command | What it does |
|---------|-------------|
| `/model sonnet` | Switch to a different model mid-conversation |
| `/models` | List all available models |
| `/cost` | Show token usage and cost for this session |
| `/clear` | Clear conversation history |
| `/compact` | Compress conversation to save context space |
| `/workdir ~/other` | Change working directory |
| `/approval` | Toggle tool approval on/off |
| `/help` | Show all commands |
| `/quit` | Exit |

---

## Approval Gates

By default, Claw Code asks before running commands or writing files:

```
⚠️  Approval required: bash
  Command: python3 hello.py
──────────────────────────────────────────
  [Y]es / [n]o / [a]lways:
```

- **Y** (or Enter) — approve this one
- **n** — skip it
- **a** — auto-approve everything for the rest of the session

To start with approvals off: `./claw --no-approval`

---

## Available Models

All models route through OpenRouter (one API key covers everything):

| Name | Model | Best for | Cost |
|------|-------|----------|------|
| `deepseek` | DeepSeek V3 | General coding, cheap | $0.14/M in |
| `sonnet` | Claude Sonnet 4 | Quality coding | $3/M in |
| `opus` | Claude Opus 4 | Complex reasoning | $15/M in |
| `flash` | Gemini 2.5 Flash | Fast + cheap | $0.15/M in |
| `gemini-pro` | Gemini 2.5 Pro | Quality + huge context | $1.25/M in |
| `minimax` | MiniMax M2.7 | Good tool calling, cheap | $0.30/M in |
| `mercury` | Mercury 2 | Fast iteration | $0.25/M in |
| `haiku` | Claude 3.5 Haiku | Quick tasks | $0.80/M in |
| `qwen-local` | Qwen 3.5 35B | Free (needs LM Studio) | $0 |

Switch anytime in the REPL: `/model flash`

---

## Tips

- **Multi-line input:** End a line with `\` to continue on the next line
- **Cancel generation:** Ctrl+C
- **Exit:** Ctrl+D or `/quit`
- **Working directory matters:** The agent sees the file tree of wherever you point it
- **Start cheap:** Use `deepseek` or `minimax` for iteration, switch to `sonnet` when you need quality
