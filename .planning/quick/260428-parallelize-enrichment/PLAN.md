---
name: 260428-parallelize-enrichment
description: Parallelize yfinance price fetches in enrich_positions() using ThreadPoolExecutor(max_workers=8)
status: in-progress
created: 2026-04-28
---

# Task: 260428-parallelize-enrichment

## Problem

Warm run takes ~21s because 46 yfinance price fetches run sequentially —
each waits for HTTP response before starting the next.
Resolution cache (Task 1) is confirmed working.

## Changes

### app/market_data.py

Wrap the per-position enrichment loop in `enrich_positions()` in a `ThreadPoolExecutor`:

- `max_workers=8`
- `enrich_position()` itself is unchanged
- Snapshot save happens AFTER all futures complete, never inside a worker (unchanged — already in main.py after `enrich_positions` returns)
- Operation lock still wraps the entire executor block (unchanged — lock is in main.py)
- Log timing at completion: `"[INFO] Enrichment completed {n} positions in {elapsed:.1f}s"`

## Rules

- `max_workers=8`
- `enrich_position()` itself is unchanged
- Snapshot save happens AFTER all futures complete, never inside a worker
- Operation lock still wraps the entire executor block
- Log timing at completion: `[INFO] Enrichment completed {n} positions in {elapsed:.1f}s`
- No frontend or backend endpoint changes
