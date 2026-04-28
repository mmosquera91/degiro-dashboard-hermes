---
name: "260428-skip-yf-delay-on-batch-hit"
status: complete
---

## Summary
- **File changed:** `app/market_data.py`
- **Lines changed:** removed 1 line (the unconditional `_yf_throttle()` at former line 993), added 1 line (conditional `_yf_throttle()` inside `else` block at line 1024)

## What changed
- Removed `_yf_throttle()` that fired unconditionally before `ticker.history()` at line 993
- Added `_yf_throttle()` inside the `else` block (price_batch miss + cached_price miss/stale/wrong_currency), so delay only fires when actually fetching price from history
- Throttle at line 900 (before `ticker.info`) is unchanged — always fires since `ticker.info` always runs for fundamentals

## Result
- Batch hit + currency-safe: no throttle, no sleep
- Cache hit + currency-safe: no throttle, no sleep
- Both miss or currency unsafe: throttle before reading price from history
