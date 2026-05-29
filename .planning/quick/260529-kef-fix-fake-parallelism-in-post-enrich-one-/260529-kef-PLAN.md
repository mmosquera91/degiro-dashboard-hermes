---
phase: quick-260529-kef
plan: 01
type: execute
wave: 1
depends_on: []
files_modified: [app/market_data.py]
autonomous: true
requirements: [QUICK-260529-kef]

must_haves:
  truths:
    - "ticker.history() calls inside _post_enrich_one no longer block the event loop"
    - "asyncio.gather over a 20-position batch issues history fetches concurrently, not sequentially"
    - "Post-batch enrichment output (rsi, perf_*, 52w_low/high) is byte-for-byte identical to before — only the execution scheduling changed"
  artifacts:
    - path: "app/market_data.py"
      provides: "_post_enrich_one with both ticker.history() calls offloaded via loop.run_in_executor"
      contains: "run_in_executor"
  key_links:
    - from: "app/market_data.py::_post_enrich_one"
      to: "loop.run_in_executor(None, ...)"
      via: "asyncio.get_running_loop() + functools.partial"
      pattern: "run_in_executor\\(None"
---

<objective>
Fix fake parallelism in `_post_enrich_one` (app/market_data.py). The coroutine calls the
blocking `ticker.history()` synchronously inside an async function, so `asyncio.gather` over
batches of 20 runs them sequentially — no real concurrency. Wrap each blocking
`ticker.history()` call in `loop.run_in_executor(None, ...)`, mirroring the pattern already
used in `_enrich_one`.

Purpose: real parallelism in the post-batch enrichment pass, matching how `_enrich_one`
already offloads its blocking work.
Output: modified `app/market_data.py` — only the two `ticker.history()` calls inside
`_post_enrich_one` change, nothing else.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@./CLAUDE.md

<interfaces>
<!-- The existing _enrich_one pattern to mirror (app/market_data.py:1718-1725). -->
<!-- Note `import asyncio` already exists at line 1716, in scope for both coroutines. -->

```python
async def _enrich_one(idx: int, pos: dict) -> dict:
    """Async wrapper for enrich_position to enable parallel execution."""
    yf_sym = resolved_symbols[idx]
    pos["_resolved_yf_symbol"] = yf_sym
    loop = asyncio.get_running_loop()
    enriched_pos = await loop.run_in_executor(None, enrich_position, pos, price_batch)
    is_rl = enriched_pos.get("_enrichment_error") == "rate_limited"
    return _sanitize_floats(enriched_pos), is_rl
```

<!-- Current _post_enrich_one — the two blocking calls to fix (app/market_data.py:1782, 1788): -->
<!--   line 1782: hist = ticker.history(period="1y", auto_adjust=True)                          -->
<!--   line 1788: hist = ticker.history(period="3mo", interval="1d", auto_adjust=True)           -->
<!-- run_in_executor passes ONLY positional args, so the keyword args (period=, auto_adjust=,    -->
<!-- interval=) must be bound with functools.partial. functools is NOT yet imported.             -->
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Offload both ticker.history() calls in _post_enrich_one via run_in_executor</name>
  <files>app/market_data.py</files>
  <action>
Add `import functools` to the top-level import block (alphabetically near the other stdlib
imports around lines 3-13; e.g. after `import re` or wherever it sorts cleanly). `asyncio`
is already imported at line 1716 within the enclosing function and is in scope.

In `_post_enrich_one` (starts at line 1778), get the running loop once near the top of the
`try` block, immediately after `ticker = yf.Ticker(yf_sym)`:
  `loop = asyncio.get_running_loop()`

Replace the first blocking call (line 1782):
  `hist = ticker.history(period="1y", auto_adjust=True)`
with:
  `hist = await loop.run_in_executor(None, functools.partial(ticker.history, period="1y", auto_adjust=True))`

Replace the second blocking call (line 1788, inside the `if len(hist) < 14:` branch):
  `hist = ticker.history(period="3mo", interval="1d", auto_adjust=True)`
with:
  `hist = await loop.run_in_executor(None, functools.partial(ticker.history, period="3mo", interval="1d", auto_adjust=True))`

Use `functools.partial` (NOT lambda) to bind the keyword args, because `run_in_executor`
accepts only positional callable args. This mirrors `_enrich_one`'s
`loop.run_in_executor(None, enrich_position, pos, price_batch)` pattern, adapted for the
keyword arguments that `ticker.history` requires.

Do NOT touch anything else: not the `_yf_throttle()` call between the two history fetches,
not the batching loop `_run_post_batch`, not the `_batch_size = 20`, not the exception
handling, not `_enrich_one`, not the FX loop, not any computation of rsi/perf/52w values.
The ONLY change is making these two existing blocking calls non-blocking via the executor.
  </action>
  <verify>
    <automated>cd /home/server/workspace/brokr && grep -n "import functools" app/market_data.py && grep -c "await loop.run_in_executor(None, functools.partial(ticker.history" app/market_data.py | grep -qx 2 && python -c "import ast; ast.parse(open('app/market_data.py').read()); print('syntax ok')"</automated>
  </verify>
  <done>`import functools` present at module top; both `ticker.history()` calls inside `_post_enrich_one` are awaited through `loop.run_in_executor(None, functools.partial(ticker.history, ...))`; file parses with no SyntaxError; no other code in the file changed.</done>
</task>

</tasks>

<verification>
- `python -c "import ast; ast.parse(open('app/market_data.py').read())"` succeeds (no syntax error).
- `grep -c "await loop.run_in_executor(None, functools.partial(ticker.history" app/market_data.py` returns `2`.
- `git diff app/market_data.py` shows ONLY: one added `import functools` line, one added `loop = asyncio.get_running_loop()` line inside `_post_enrich_one`, and the two `ticker.history(...)` lines rewritten as awaited executor calls. No other hunks.
</verification>

<success_criteria>
- Both `ticker.history()` calls in `_post_enrich_one` run via `loop.run_in_executor`, so a
  `gather` batch of 20 issues fetches concurrently instead of sequentially.
- Enrichment results (rsi, perf_30d/90d/ytd/1y, 52w_low/high, distance_from_52w_high_pct) are
  computed identically to before — only scheduling changed.
- No other stage, batching logic, throttle, or behavior is modified.
</success_criteria>

<output>
Create `.planning/quick/260529-kef-fix-fake-parallelism-in-post-enrich-one-/260529-kef-SUMMARY.md` when done
</output>
