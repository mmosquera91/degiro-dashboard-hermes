---
name: 20260424-fix-market-data-global-fx
description: Fix global declaration in _resolve_yf_symbol + remove None caching in get_fx_rate
type: quick
status: complete
completed: 2026-04-24
---

## Summary

Fixed 2 bugs in `app/market_data.py`:

1. **Bug #1 (UnboundLocalError)** — `_resolve_yf_symbol()` assigned to `_yf_rate_limited` without a `global` declaration. Added `global _yf_rate_limited` immediately after the docstring.

2. **Bug #3 (TypeError)** — `get_fx_rate()` cached `None` on failed lookups then returned `1.0`. A second call would return cached `None` instead, causing `float * None` in `enrich_positions()`.
   - Fix 2A: Removed the `None` caching — failed lookups now return `1.0` directly without caching.
   - Fix 2B: Added defensive `if fx_rate is None` guard in `enrich_positions()`.

## Files Changed
- `app/market_data.py` — 6 insertions, 2 deletions

## Commit
`8d1a6ac` — fix(market_data): add global declaration in _resolve_yf_symbol and remove None caching in get_fx_rate
