---
name: "20260426-isin-guided-suffix-routing"
description: "ISIN-prefix-guided suffix routing + cache staleness guard"
type: quick
status: complete
completed: "2026-04-26"
---

## Summary

Added `_get_suffix_order()` function that routes suffix scan based on ISIN country prefix:
- US/CA stocks → bare symbol (NASDAQ/NYSE) first
- IE/LU UCITS ETFs → .DE/.F (Xetra) first
- GB → .L (London) first
- FI → .HE (Helsinki) first
- CH → .SW (SIX) first
- DE/NL/FR/... → local exchange first
- Default → European-first (existing behavior)

Replaced hardcoded suffix list in `_resolve_yf_symbol()` with `_get_suffix_order(isin, symbol)`.

Added cache staleness guard: when returning a cached entry, re-validate currency against position currency; evict if mismatch to clear stale USD results from before ISIN-strict-EUR fix.

## Changes
- `app/market_data.py`: +90/-13 lines

## Testing
- Syntax validated: `python3 -m py_compile app/market_data.py` — OK
- Committed: `22656cc`

## Deploy
```
docker compose down && docker compose up -d --build
curl -s -X DELETE http://localhost:8000/api/admin/symbol-cache \
  -H "Authorization: Bearer <BROKR_AUTH_TOKEN>"
```
