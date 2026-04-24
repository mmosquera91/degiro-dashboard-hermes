# fix-yf-rate-limited

Fix `_yf_rate_limited` race condition in `app/market_data.py`.

## Problem

The `_yf_rate_limited` flag was being unconditionally reset at the start of each `enrich_positions()` call, but the 429 rate limit from yfinance should persist for 60 seconds before allowing retries.

## Changes

1. Add `_yf_rate_limited_until: float = 0.0` module-level variable alongside `_yf_rate_limited`
2. Change `enrich_positions()` reset from unconditional to conditional: only reset if `time.time() >= _yf_rate_limited_until`
3. In `_resolve_yf_symbol()`, set `_yf_rate_limited_until = time.time() + 60.0` when 429 is detected
4. In `_resolve_yf_symbol()`, check `time.time() < _yf_rate_limited_until` when testing the rate limit flag
