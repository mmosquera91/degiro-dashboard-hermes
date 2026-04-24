---
name: fix-yf-rate-limited
description: Fix _yf_rate_limited race condition with 60s cooldown
type: quick
status: complete
completed: 2026-04-24
---

## Summary

Applied all 3 changes to `app/market_data.py`:
- Added `_yf_rate_limited_until` module-level variable
- Made `enrich_positions()` reset conditional on cooldown expiry
- Set 60s cooldown in `_resolve_yf_symbol()` 429 handler
- Added time-based expiry check in `_resolve_yf_symbol()` rate limit guard

## Files Changed

- `app/market_data.py` (4 line changes)
