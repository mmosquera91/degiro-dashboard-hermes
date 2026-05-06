# Quick Task: 260429-batch-enrichment-gap

## Problem
Positions with `price_source="batch"` skip the individual enrichment path. They get `current_price` from the batch `yf.download()` but none of the historical metrics (RSI, perf_30d/90d/ytd, 52w_low, distance_from_52w_high_pct).

Root cause: `enrich_position()` has a cache-warm fast path (line 952) that returns early at line 1009 BEFORE the history fetch at line 1182 that computes RSI and performance metrics.

## Fix

### Step 1 — Confirmed the batch path
`enrich_positions()` at line 1430-1473 does a batch price fetch via `yf.download()`. After that, it calls `enrich_position()` for each position. The cache-warm path in `enrich_position()` uses the batch price but returns early.

### Step 2 — Confirmed which symbols hit this path
European .AS / .DE / .L / .PA tickers and any other symbol whose resolution and fundamentals are cached will hit the cache-warm path and get batch prices but missing historical metrics.

### Step 3 — Added post-batch enrichment pass
After `asyncio.run(_run_all())` at line 1510 and before the diagnostic summary, added a post-batch enrichment pass (lines 1512-1572) that:

1. Iterates over enriched positions
2. Skips positions where `price_source != "batch"` or already have RSI+perf
3. For each missing position:
   - Fetches 1y history via `yf.Ticker(yf_sym).history(period="1y")`
   - Falls back to 3mo if <14 trading days returned (per fe6f947 pattern)
   - Computes `rsi = compute_rsi(close)` 
   - Computes `perf_30d/90d/ytd = _compute_performance(close)`
   - Computes `52w_low` and `distance_from_52w_high_pct` from history
4. Logs at INFO: `"Post-batch enrichment: {n} symbols enriched in {t:.1f}s"`

### Step 4 — Scoring recomputes correctly
`compute_scores()` is called in `main.py` AFTER `enrich_positions()` returns. Since the post-batch pass populates `perf_30d/90d/ytd` and `rsi` before return, `compute_momentum_score()`, `compute_value_score()`, and `compute_buy_priority_score()` will all work correctly.

### Step 5 — No cache schema change
Added comment: `# TODO: persist enriched metrics to cache in v2`

## Files Changed
- `app/market_data.py`: Added post-batch enrichment pass at the end of `enrich_positions()`
