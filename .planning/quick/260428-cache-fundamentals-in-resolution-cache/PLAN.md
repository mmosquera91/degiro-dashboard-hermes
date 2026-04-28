# 260428-cache-fundamentals-in-resolution-cache

## Problem
`ticker.info` is called unconditionally for every position on every enrichment run to fetch sector, country, P/E, 52w-high. At ~0.4s per call × 46 positions = ~19s of avoidable overhead. These values change at most weekly.

## Changes

### app/market_data.py

**Add fundamentals to the resolution cache entry with a 24h TTL:**

Cached fields: sector, country, pe_ratio, week52_high, currency, shortName
Cache key: same as resolution cache (broker_symbol:isin)
TTL: 24 hours (separate from resolution TTL which is permanent)

**Logic in enrich_position():**
- Check if resolution cache entry has fundamentals AND cached_at < 24h ago
  → skip ticker.info entirely, use cached values
- If fundamentals missing or stale → call ticker.info, update cache entry
- _yf_throttle() only fires when ticker.info is actually called

Persist updated fundamentals to symbol_cache.json alongside resolution data.

Log: "[INFO] Fundamentals cache hit for {symbol}, skipping ticker.info"

**No frontend or backend endpoint changes**

## Expected
Warm run ~7-8s total (6.1s batch fetch + ~1s loop, no ticker.info calls)

## Verification
- Cold run: ticker.info still called, fundamentals cached
- Warm run (within 24h): ticker.info skipped, cache hit logged
- Check symbol_cache.json for persisted fundamentals entries
