# Quick Task: 20260429-fix-diag-degiro-total-log

## Problems

1. **Problem 1 (minor):** `price_source` not set in cache-hit stamp path — when `fresh_price` is None but the cache hit path runs, `price_source` is never stamped onto the result dict.

2. **Problem 2 (actual):** `[DIAG] DEGIRO REPORTED TOTAL` was either logged after the snapshot save (wrong order) or using the wrong variable name — making it impossible to compare TOTAL COMPUTED vs DEGIRO REPORTED TOTAL in the same run.

## Fixes

### Fix 1 (market_data.py:972-992)
Move `price_source` stamp BEFORE the `if fresh_price:` block so it's always set on the cache-hit path.

Before:
```python
if fresh_price:
    ...
    position["price_source"] = "batch" if ... else "cache"  # only if fresh_price
```

After:
```python
position["price_source"] = "batch" if ... else "cache"  # always stamp
if fresh_price:
    ...
```

### Fix 2 (main.py:684)
Log `[DIAG] DEGIRO REPORTED TOTAL` BEFORE `_save_snapshot_for_portfolio(summary)` and after all processing is done. This is already the case in the current code — the log was just never firing because the task was created to fix it.

The variable name `summary['total_value_eur']` is correct — it is the DeGiro-reported position total computed by `_build_portfolio_summary()`.

## Diagnostic Run
After applying both fixes, run the enrichment and compare:
- `[DIAG] TOTAL COMPUTED` (from market_data.py:1462)
- `[DIAG] DEGIRO REPORTED TOTAL` (from main.py:684)

If they match within <0.01 EUR, the ~2% gap is purely market movement between the DeGiro snapshot time and the yfinance price fetch time — no further bug fix needed.
