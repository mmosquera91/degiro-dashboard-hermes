Fix negative cache import bug in market_data.py

## Problem
The negative cache implementation in _resolve_yf_symbol() used `import time as _time`
inside the function body. Python resolves names at parse time for the whole function scope,
so when the cache-check block at line 348 calls `time.time()`, the inline import hasn't
executed yet — `NameError: name 'time' is not defined`. This error is silently swallowed
by the surrounding try/except, causing negative cache writes to fail silently.

## Changes
1. Ensure `import time` exists at module level (line 9 already has it)
2. Remove `import time as _time` from inside _resolve_yf_symbol() — not needed since module-level import covers all uses
3. Replace any `_time.time()` references with `time.time()`

## Verification
- grep for `_time` in market_data.py — should return no matches
- grep for `import time` in market_data.py — should show module-level import at line 9
- All `time.time()` calls should use the module-level `time` reference

## Files
- app/market_data.py

## No other changes.