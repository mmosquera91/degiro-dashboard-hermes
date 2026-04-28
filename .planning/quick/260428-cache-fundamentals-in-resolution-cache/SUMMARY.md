---
name: 260428-cache-fundamentals-in-resolution-cache
description: Cache ticker.info fundamentals in resolution cache with 24h TTL
status: complete
---

## Done

- Added `_FUNDAMENTALS_TTL = 86400` constant (24 hours)
- Added `_get_cached_fundamentals(cache_key)` helper — returns cached fundamentals dict if fresh (< 24h), else None
- Added `_update_fundamentals_cache()` — stores sector, country, pe_ratio, week52_high, currency, short_name in resolution cache entry; persists to symbol_cache.json
- Modified `enrich_position()`:
  - Before calling `ticker.info`, checks `_get_cached_fundamentals(cache_key)`
  - Cache hit: skips `ticker.info` entirely, uses cached values for sector/country/pe_ratio/week52_high/currency; `_yf_throttle()` not called
  - Cache miss: calls `ticker.info`, extracts fundamentals, calls `_update_fundamentals_cache()` then continues
  - Log: `"[INFO] Fundamentals cache hit for {symbol}, skipping ticker.info"`
- No changes to frontend or backend endpoints
