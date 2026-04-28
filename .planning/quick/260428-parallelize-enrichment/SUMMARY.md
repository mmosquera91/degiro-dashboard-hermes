---
name: 260428-parallelize-enrichment
description: Parallelize yfinance price fetches in enrich_positions() using ThreadPoolExecutor(max_workers=8)
status: complete
completed: 2026-04-28
commit: c1d4002
---

# Summary: 260428-parallelize-enrichment

## What

Wrapped the sequential `for pos in positions` loop in `enrich_positions()` with `ThreadPoolExecutor(max_workers=8)`. Each position's `enrich_position()` call + FX conversion runs concurrently across 8 workers.

## Changes

- **app/market_data.py**: Added `from concurrent.futures import ThreadPoolExecutor, as_completed`. Refactored the enrichment loop to use a `_enrich_and_convert()` inner function submitted to the thread pool. Log timing added at completion.

## Rules followed

- `max_workers=8` — as specified
- `enrich_position()` unchanged
- Snapshot save remains in `main.py` after `enrich_positions()` returns — no worker touches it
- Operation lock in `main.py` wraps the entire `enrich_positions()` call — unchanged
- Timing log: `[INFO] Enrichment completed {n} positions in {elapsed:.1f}s`
- No frontend or backend endpoint changes

## Expected impact

Warm run (~46 positions, all cache misses on first run) drops from ~21s sequential to ~3-4s with 8 workers. With resolution cache hit rate ~70%, the benefit scales with cache misses.

## Verification

- Module imports cleanly (`python3 -c "import app.market_data; print('OK')"`)
- Commit: `c1d4002`
