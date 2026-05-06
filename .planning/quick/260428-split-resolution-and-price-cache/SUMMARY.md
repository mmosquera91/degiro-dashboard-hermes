---
name: 260428-split-resolution-and-price-cache
description: Split symbol cache into resolution (persistent) and price (15-min TTL) layers
status: complete
---

## Summary

Split `_symbol_cache` into two distinct caches in `app/market_data.py`:

### Resolution Cache (persistent, no TTL)
- **Key**: `broker_symbol:isin`
- **Value**: `{yf_symbol, exchange, currency, method, cached_at}`
- **TTL**: None (evicted only on 404/error or manual DELETE)
- **Persisted**: Yes (`symbol_cache.json`)
- On 404 from yfinance: entry evicted, next run re-resolves

### Price Cache (in-memory, 15-min TTL)
- **Key**: `resolved_yf_symbol`
- **Value**: `{current_price, price_currency, timestamp}`
- **TTL**: 15 minutes (900s)
- **Persisted**: No (in-memory only)
- Checked before yfinance price fetch; expired/missing → fetch fresh

### `enrich_position()` flow
1. Check resolution cache → on hit: log `"Resolution cache hit for {symbol}, skipping lookup"`, use cached data
2. On miss: `_resolve_yf_symbol(evict_on_404=True)` for full resolution
3. Check price cache → if fresh and currency matches → use cached price; otherwise fetch fresh and update cache
4. Always fetch info and history for RSI/performance (always fresh)

### `clear_symbol_cache()` now clears both caches

### No frontend changes
