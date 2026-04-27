# brokr-total-value-eur

Add `total_value_eur` key to portfolio summary responses so the frontend receives the EUR total instead of `None`.

## Changes

**app/main.py**

In `_build_raw_portfolio_summary()` (line ~137): after `"total_value": round(total_value, 2),` add `"total_value_eur": round(total_value, 2),`.

In `_build_portfolio_summary()` (line ~198): after `"total_value": round(total_value, 2),` add `"total_value_eur": round(total_value, 2),`.

`total_value` is already the EUR-denominated sum in both functions, so this is a cosmetic duplicate key to satisfy the frontend's `total_value_eur` field lookup.
