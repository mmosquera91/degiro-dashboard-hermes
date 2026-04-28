---
description: Fix benchmark cache stale-on-ratelimit bug in app/main.py
type: quick
status: complete
---

Fix benchmark cache stale-on-ratelimit bug in app/main.py

## Problem

After Update Prices, `_save_snapshot_for_portfolio()` calls `fetch_benchmark_series()`
while yfinance is still rate-limited (returns `[]`), then resets `_benchmark_cache_time = 0.0`.
`get_benchmark()` then sees no valid cache, calls `fetch_benchmark_series()` again,
also gets `[]`, and the frontend shows the error indefinitely until rate limit clears.

Two root causes:
1. `_save_snapshot_for_portfolio()` invalidates the benchmark cache unconditionally
   even when it has nothing better to replace it with.
2. `get_benchmark()` never serves stale cache — a failed fetch always returns empty series.

## Changes

1. **`app/main.py:286-287`** — In `_save_snapshot_for_portfolio()`, remove the cache
   invalidation (`global _benchmark_cache_time; _benchmark_cache_time = 0.0`). The 1h
   TTL in `get_benchmark()` is sufficient.

2. **`app/main.py:746-750`** — In `get_benchmark()`, after `fetch_benchmark_series()`
   returns, add a stale-cache fallback when the result is empty and valid stale series
   exist in `_benchmark_cache["series"]`.

3. **`app/main.py:736-738`** — In `get_benchmark()`, serve `snapshots` fresh from disk
   in the cache hit path (was `_benchmark_cache["snapshots"]`).

4. **`app/main.py:770`** — In `get_benchmark()`, remove `_benchmark_cache["snapshots"]`
   population. Also update `_benchmark_cache` initialization to drop the `snapshots` key.

5. **`app/main.py:816-817`** — In snapshot delete endpoint, remove cache invalidation
   (`global _benchmark_cache_time; _benchmark_cache_time = 0.0`). The cache is only for
   series+attribution, which are unaffected by snapshot deletion.