---
name: fix-429-abort
description: Replace broken string-based 429 detection with module-level rate-limit flag in _resolve_yf_symbol
type: quick
status: complete
---

## Changes

- Added `_yf_rate_limited: bool = False` and `_yf_rate_limited_lock = threading.RLock()` at module level (line 28)
- `_resolve_yf_symbol` now checks `_yf_rate_limited` flag before each suffix attempt and returns early if set
- On 429 exception, sets `_yf_rate_limited = True` and returns instead of `break`
- `enrich_positions` resets `_yf_rate_limited = False` at the start of each call

## Files changed
- `app/market_data.py`

## Verification
- tests/test_market_data.py: module imports ok, tests have pre-existing import issues unrelated to this change
- The `_session_rate_limited` flag in `enrich_positions` continues to work independently for enrichment-level abort
