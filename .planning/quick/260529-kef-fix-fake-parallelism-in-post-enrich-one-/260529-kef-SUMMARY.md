---
phase: quick-260529-kef
plan: "01"
subsystem: market-data-enrichment
tags: [async, performance, yfinance, run-in-executor]
dependency_graph:
  requires: []
  provides: [real-async-post-batch-enrichment]
  affects: [app/market_data.py]
tech_stack:
  added: [functools]
  patterns: [run_in_executor with functools.partial for keyword-arg blocking calls]
key_files:
  modified: [app/market_data.py]
decisions:
  - Used functools.partial (not lambda) to bind keyword args for run_in_executor, matching plan spec and Python convention
metrics:
  duration: 48s
  completed: "2026-05-29"
---

# Quick Task 260529-kef: Fix Fake Parallelism in _post_enrich_one Summary

**One-liner:** Offloaded both `ticker.history()` blocking calls in `_post_enrich_one` via `loop.run_in_executor(None, functools.partial(...))`, enabling real concurrency in the asyncio.gather post-batch enrichment pass.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Offload both ticker.history() calls via run_in_executor | cc35de8 | app/market_data.py |

## What Changed

`app/market_data.py` received four targeted modifications:

1. `import functools` added to the module-level stdlib import block (alphabetically after `import os`, before `import re`)
2. `loop = asyncio.get_running_loop()` added inside `_post_enrich_one` immediately after `ticker = yf.Ticker(yf_sym)`
3. First blocking call `hist = ticker.history(period="1y", auto_adjust=True)` replaced with `hist = await loop.run_in_executor(None, functools.partial(ticker.history, period="1y", auto_adjust=True))`
4. Second blocking call `hist = ticker.history(period="3mo", interval="1d", auto_adjust=True)` replaced with `hist = await loop.run_in_executor(None, functools.partial(ticker.history, period="3mo", interval="1d", auto_adjust=True))`

No other code was modified — the batching logic, throttle calls, exception handling, RSI/perf/52w computations, and `_enrich_one` are all untouched.

## Decisions Made

- **functools.partial vs lambda:** Used `functools.partial` as specified — `run_in_executor` accepts only a positional callable, so keyword args must be pre-bound. `functools.partial` is the idiomatic, safe approach (lambdas would also work but are less explicit).

## Deviations from Plan

None - plan executed exactly as written.

## Verification

All checks passed:
- `import functools` present at line 8 (module top)
- `grep -c "await loop.run_in_executor(None, functools.partial(ticker.history"` returns `2`
- `python3 -c "import ast; ast.parse(open('app/market_data.py').read())"` succeeds with "syntax ok"
- `git diff` shows exactly: 1 import line added, 1 `loop =` line added, 2 `ticker.history(...)` lines rewritten - no other hunks

## Self-Check: PASSED

- [x] app/market_data.py modified and committed at cc35de8
- [x] import functools present
- [x] Both run_in_executor calls present (count=2)
- [x] Syntax valid
- [x] No unexpected file deletions
