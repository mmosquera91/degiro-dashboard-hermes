---
name: brokr-true-total-pl-fix5
description: Simplify true P&L computation — remove from degiro_client, compute in main.py
type: plan
status: complete
---

# brokr-true-total-pl-fix5

## What was done

Removed true P&L computation from `degiro_client.py` and moved it to `main.py` where validated values are available.

### degiro_client.py
- Kept only raw extraction of `totalDepositWithdrawal`
- Removed `_net_value`, `_true_pl`, `_true_pl_pct` computations
- Removed `true_total_pl` and `true_total_pl_pct` from return dict
- Return dict now contains only `total_deposit_withdrawal`

### main.py — _build_portfolio_summary()
- Added true P&L computation after `total_value` and `cash_available` are computed
- Formula: `true_total_pl = total_value + cash_available - total_deposit_withdrawal`
- Returns `None` for both metrics when `total_deposit_withdrawal <= 0`
- Added `total_deposit_withdrawal` to return dict

### main.py — _build_raw_portfolio_summary()
- No changes needed — already has `"true_total_pl": None, "true_total_pl_pct": None, "total_deposit_withdrawal": 0.0`

## Commit
`facfe6f` — refactor: move true P&L computation from degiro_client to main.py