# Plan: batch-price-fetch-yf-download

## Problem
ThreadPoolExecutor parallelization in `enrich_positions()` gives minimal speedup (~18s vs ~21s) because yfinance serializes HTTP calls internally across threads (GIL + shared session). 46 individual `yf.Ticker(symbol).fast_info` calls run effectively sequentially.

## Changes

### `app/market_data.py`

1. **Batch price fetch before enrichment loop** — collect all resolved yf_symbols, fetch prices in one `yf.download()` call before the loop.

2. **Build price lookup dict from batch** — `batch["Close"].iloc[-1]` gives latest close per symbol.

3. **Update `enrich_position()` to accept pre-fetched price dict** — look up price from dict first, fall back to individual `yf.Ticker().fast_info` only if missing.

4. **Log batch fetch timing** — `[INFO] Batch price fetch: {n} symbols in {elapsed:.1f}s`.

5. **Keep ThreadPoolExecutor only if parallelizable work remains** — after moving price fetch to batch, only FX conversion and scoring remain in the loop. Remove executor if nothing parallelizable remains.

## Expected Result
- Batch fetch ~1-2s for 46 symbols
- Total enrichment ~3-5s

## Files
- `app/market_data.py`
