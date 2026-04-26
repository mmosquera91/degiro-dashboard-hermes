---
name: 20260426-symbol-cache-fix
description: Symbol cache clear/audit + startup audit for poisoned bare-symbol cache
type: quick
status: complete
completed: "2026-04-26"
commit: 580f8e9
---

## Summary

Fixed the poisoned symbol cache issue that caused all per-stock metrics (RSI, Momentum, BuyPriority, Sector) to show None on every restart after a rate-limiting event during the first suffix scan run.

## Changes

- **market_data.py**: `math` moved to module-level import; added `clear_symbol_cache()` and `audit_symbol_cache()` functions
- **main.py**: `audit_symbol_cache()` called at startup in `lifespan()` after portfolio restore; added `DELETE /api/admin/symbol-cache` endpoint

## Verification

- Python syntax check passed on both files
