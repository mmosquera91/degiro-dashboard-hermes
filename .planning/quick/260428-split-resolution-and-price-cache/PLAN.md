---
description: Split symbol cache into resolution (persistent) and price (15-min TTL) layers
---

Split `_symbol_cache` into two distinct caches in `app/market_data.py`:

## Resolution Cache
- **Store**: `{yf_symbol, exchange, currency, resolution_method}`
- **Key**: `broker_symbol:isin`
- **TTL**: None (persistent, only evicted on 404/error or manual DELETE)
- **Persisted**: Yes (`symbol_cache.json`)
- **On 404 from yfinance**: Evict entry, let next run re-resolve

## Price Cache
- **Store**: `{current_price, price_currency, price_timestamp}`
- **Key**: `resolved_yf_symbol`
- **TTL**: 15 minutes (in-memory only, not persisted)
- **Invalidated**: On TTL expiry or any enrichment run

## Changes in `enrich_position()`
1. Check resolution cache first
2. On hit: log `"Resolution cache hit for {symbol}, skipping lookup"` → use cached yf_symbol, exchange, currency; ALWAYS re-fetch price
3. On miss: call `_resolve_yf_symbol()` with `evict_on_404=True`; on 404 → evict resolution cache, return early
4. Always check price cache before yfinance fetch; re-fetch if expired/missing

## Changes in `_resolve_yf_symbol()`
- Accept `evict_on_404=False` parameter (default for backwards compat callers)
- When yfinance returns 404: if `evict_on_404=True`, delete entry from resolution cache and save; return ""
- On cache hit: return cached data directly (no re-validation network call)

## No frontend changes
