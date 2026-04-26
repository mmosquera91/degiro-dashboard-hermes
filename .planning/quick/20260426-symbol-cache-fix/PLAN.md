# Quick Task: 20260426-symbol-cache-fix

## Root Cause
commit ae7e392 fixed the suffix scan but rate limiting hit during first run — bare symbols (no "." suffix) got written to symbol_cache.json. Every restart loads this poisoned cache → wrong tickers → empty history → RSI/Momentum/BuyPriority/Sector all None.

## Changes

### app/market_data.py

1. **Move `import math` to module-level** (currently locally imported inside `_sanitize_floats` at line 428)
   - Add `import math` alongside existing imports at top of file
   - Remove `import math` from inside `_sanitize_floats`

2. **Add `clear_symbol_cache() -> int`**
   - Under `_symbol_cache_lock`, clear `_symbol_cache` dict
   - Delete `_SYMBOL_CACHE_PATH` file if it exists
   - Return count of entries cleared

3. **Add `audit_symbol_cache() -> int`**
   - Iterate over `_symbol_cache` entries
   - Count entries where `resolved == bare symbol` (no "." suffix in resolved value)
   - Log WARNING with count and advice: "Call DELETE /api/admin/symbol-cache to clear"
   - Return suspicious count

### app/main.py

4. **Update import** from `.market_data` (line 19):
   - Add `clear_symbol_cache, audit_symbol_cache` to existing import

5. **Call `audit_symbol_cache()` in `lifespan()`** after `_restore_portfolio_from_snapshot()`:
   - At line ~257, after the existing `_restore_portfolio_from_snapshot()` call

6. **Add endpoint** `DELETE /api/admin/symbol-cache`:
   - `dependencies=[Depends(verify_brok_token)]`
   - Calls `clear_symbol_cache()`, logs result, returns `{"cleared": N}`
   - Docstring: "Use after yfinance upgrade or when per-stock metrics all show —"
