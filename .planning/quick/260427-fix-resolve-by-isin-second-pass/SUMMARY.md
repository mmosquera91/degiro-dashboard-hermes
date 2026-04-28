---
name: 260427-fix-resolve-by-isin-second-pass
description: Fix _resolve_by_isin() to try fallback exchanges when no preferred-exchange match found
type: quick
status: complete
date: 2026-04-27
---

Completed: 2026-04-27

Changes:
- app/market_data.py: Added second-pass fallback loop in _resolve_by_isin() to resolve ISINs via non-preferred exchanges (e.g. TSX, SGX) when no preferred-exchange match is found
