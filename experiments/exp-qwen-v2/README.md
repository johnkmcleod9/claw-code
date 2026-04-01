# Experiment: qwen-evolution-v2

**Date:** 2026-04-01  
**Model:** qwen-local (Qwen3.5-35B-A3B, 4-bit, LM Studio)  
**Context:** 10K  

## Goal
Fix the timeout failures (eng-007, eng-008) without hurting quality on other tasks.

## Hypothesis
The timeout prevention chunk from v1 helped eng-007 complete. But v1 also dropped temperature to 0.3, which hurt other tasks. v2 tests: keep temperature at 0.7, only keep the timeout prevention addition.

## What Changed vs Baseline
**ONLY added:** timeout prevention guidelines (incremental work, frequent saves, save state before timeout)
**NO changes to:** temperature, tool instructions, or any other prompt sections

## Parent
Branch `exp/qwen-evolution-v1` — see v1 for full analysis of what NOT to do (temp 0.3 = bad)

## Expected Outcome
- eng-007: timeout → completes (from v1 we know this chunk works)
- eng-008: timeout → may complete
- Other tasks: no quality drop (temp unchanged at 0.7)

## Next Step if Successful
If v2 improves overall quality without regressing anything, merge to main.
