---
name: benchmark-ttl-cache complete
description: Add TTL cache to GET /api/benchmark endpoint
status: complete
---

## Summary

Added 1-hour TTL cache to `GET /api/benchmark` to avoid hitting yfinance on every request.

## Changes

- **app/main.py:37-40** — Added `_benchmark_cache`, `_benchmark_cache_time`, and `_BENCHMARK_TTL = 3600` module-level variables
- **app/main.py:626-633** — Cache check before `fetch_benchmark_series()`; returns cached `{snapshots, benchmark_series, attribution}` if fresh
- **app/main.py:658-662** — Cache population after successful fetch
- **app/main.py:516-517** — Cache invalidation (`_benchmark_cache_time = 0.0`) after `save_snapshot()` in `get_portfolio()`
