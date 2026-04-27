# Plan: refresh-prices endpoint and daily enrichment

## Problem
Enrichment only runs when user explicitly syncs DeGiro. Prices go stale between buys (weeks).

## Changes

1. **`_sanitize_floats_deep(portfolio)`** — new helper that applies `_sanitize_floats` recursively to all positions in a portfolio dict.

2. **`_save_snapshot_for_portfolio(portfolio)`** — extracted snapshot-save logic from `get_portfolio()` into a reusable helper. Invalidates `_benchmark_cache_time`.

3. **`_do_enrich_session()`** — plain `def` (no async) callable containing the enrichment logic shared by both the on-demand endpoint and the daily loop.

4. **`POST /api/refresh-prices`** — new endpoint that validates a portfolio exists, spawns `_do_enrich_session` in a daemon thread, returns immediately with `{"status": "enrichment_started"}`.

5. **`_daily_enrichment_loop()`** — `async` coroutine that sleeps until ~08:00 local time each day, then calls `_do_enrich_session` via `asyncio.to_thread`. Started as an `asyncio.create_task` in the lifespan after `_restore_portfolio_from_snapshot()`.

6. Updated `get_portfolio()` to use `_save_snapshot_for_portfolio()` instead of inline snapshot logic.

## Files
- `app/main.py`
