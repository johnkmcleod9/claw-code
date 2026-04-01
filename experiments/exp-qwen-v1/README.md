# Experiment: qwen-evolution-v1

**Date:** 2026-04-01  
**Model:** qwen-local (Qwen3.5-35B-A3B, 4-bit, LM Studio)  
**Context:** 10K  

## Goal
Improve Qwen's engineering quality from 0.82 baseline toward Sonnet-level (0.87).

## What Changed
Sonnet-tuned system prompt with these additions:
- Tool usage strategy (file_read before editing, structured debugging)
- Timeout prevention guidelines (incremental progress, frequent saves)
- Debugging approach (5-step systematic method)
- Output format emphasis (file_write requirement reinforced)
- Efficiency guidelines (file_list first, minimal reads)
- **Config: temperature 0.7 → 0.3**

## Results

### Engineering Suite
| Task | Baseline | Evolved | Δ |
|------|----------|---------|---|
| eng-001 | 0.95 | 1.00 | ⬆️ |
| eng-002 | 0.35 | 0.00 | ⬇️ |
| eng-003 | 0.75 | 0.75 | — |
| eng-004 | 0.85 | 0.85 | — |
| eng-005 | 0.95 | 0.85 | ⬇️ |
| eng-006 | 0.95 | 0.95 | — |
| eng-007 | timeout | 0.95 | ⬆️⬆️ |
| eng-008 | timeout | timeout | — |
| eng-009 | 0.95 | 0.85 | ⬇️ |
| eng-010 | 0.85 | 0.85 | — |
| **Avg** | **0.82** | **0.78** | **⬇️** |

### Summary
- **VERDICT: FAILED** — overall quality dropped 0.04
- ✅ Fixed eng-007 timeout (big win)
- ❌ eng-002 quality dropped further (0.35 → 0.00)
- ❌ Multiple tasks lost 0.10 quality

## Root Cause
**Temperature 0.3 was too low.** Qwen at 4-bit quantization is already more literal/conservative than MiniMax. Dropping from 0.7 → 0.3 made it over-follow the prompt template and second-guess itself on tasks it was acing at 0.7.

## Lessons Learned
1. Do NOT lower temperature below 0.7 for Qwen-3.5-35B-A3B (4-bit)
2. The timeout prevention additions WERE useful — keep those
3. The tool usage strategy additions may have contributed to verbosity — monitor
4. Future experiments: keep temp at 0.7 or try 0.9 instead

## Files
- `profiles/qwen-local.yaml` — baseline profile
- `profiles/qwen-local_improved.yaml` — evolved profile (this experiment)
