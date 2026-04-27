---
name: brokr-total-value-eur
description: Add total_value_eur key to portfolio summary responses
type: quick
status: complete
completed_at: "2026-04-27"
---

## Done

Added `"total_value_eur": round(total_value, 2)` to both `_build_raw_portfolio_summary()` and `_build_portfolio_summary()` return dicts in `app/main.py`.

No other changes to main.py.
