---
name: 260429-batch-enrichment-gap
description: Fix batch-enriched positions missing RSI and performance metrics
type: quick
status: complete
---

## Summary

Fixed the batch enrichment gap where positions with `price_source="batch"` were getting `current_price` from `yf.download()` but missing all historical metrics (RSI, perf_30d/90d/ytd, 52w_low, distance_from_52w_high_pct).

## What was done

**Root cause**: `enrich_position()` has a cache-warm fast path (line 952) that returns early at line 1009 before the history fetch block (line 1182) that computes RSI and performance.

**Fix**: Added a post-batch enrichment pass at the end of `enrich_positions()` (after line 1510) that:
- Iterates over all enriched positions
- Identifies batch-fetched positions missing `rsi` or `perf_30d`
- Fetches 1y history individually with 3mo fallback (same pattern as fe6f947)
- Computes RSI via `compute_rsi()` and performance via `_compute_performance()`
- Computes 52w_low and distance_from_52w_high_pct from history
- Logs: `"Post-batch enrichment: {n} symbols enriched in {t:.1f}s"`

## Files changed
- `app/market_data.py`: ~60 lines added (post-batch enrichment pass)

## Verification
- Python syntax check passed
- `compute_scores()` in `main.py` is called AFTER `enrich_positions()` returns, so downstream `momentum_score`, `value_score`, and `buy_priority_score` will be computed correctly from the now-populated metrics
