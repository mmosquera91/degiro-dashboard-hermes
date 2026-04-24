# Quick Task: fix-market-data-global-fx

## Fix 1 — global _yf_rate_limited in _resolve_yf_symbol()
Add `global _yf_rate_limited` at top of `_resolve_yf_symbol()` to fix UnboundLocalError.

## Fix 2A — remove None caching in get_fx_rate()
Remove `_fx_cache[key] = None` so failed lookups retry rather than returning None.

## Fix 2B — None guard in enrich_positions()
Add `if fx_rate is None` guard after `get_fx_rate()` call as defensive fallback.
