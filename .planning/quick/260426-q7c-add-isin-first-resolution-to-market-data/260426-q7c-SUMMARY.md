---
name: 260426-q7c-add-isin-first-resolution-to-market-data
description: Add ISIN-first resolution to market_data.py for ETFs/ETPs whose DeGiro symbol doesn't match Yahoo ticker
date: 2026-04-26
status: complete
quick_id: 260426-q7c
---

## Summary

Implemented ISIN-first Yahoo Finance ticker resolution in `app/market_data.py`.

### Changes Made

1. **Added `_resolve_by_isin()` function** after `_save_symbol_cache()`:
   - Uses `yfinance.Search(isin, max_results=10)` to find Yahoo Finance tickers
   - Prefers results on exchanges matching position currency (EUR/USD/GBP)
   - Currency exchange sets: EUR={AMS,PAR,FRA,EBS,MIL,MCE,HEL,OSL,BRU,LIS,VIE,GER,TDG}, USD={NYQ,NMS,NGM,PCX,ASE,CBT}, GBP={LSE,IOB}
   - First pass: currency-matched exchange; second pass: any symbol
   - Rate limit handling integrated with existing `_yf_rate_limited` global

2. **Updated `_resolve_yf_symbol()`**:
   - Added `position_currency: str = "EUR"` parameter to signature
   - Inserted ISIN resolution as Step 0 before suffix loop
   - Returns early with cached result if ISIN resolves successfully

3. **Updated `enrich_position()` caller** to pass position currency:
   - `yf_symbol = _resolve_yf_symbol(symbol, isin, position.get("currency", "EUR"))`

### Post-Deploy Note

Call `DELETE /api/admin/symbol-cache` after deploying to evict stale cache entries for QDVD, QDV5, O9T etc. that still map to wrong/bare symbols.

### Files Changed
- `app/market_data.py` (3 changes)