---
name: 20260426-symbol-resolution-hardening
description: Fix Yahoo symbol resolution: suffix ordering, missing .HE/.F exchanges, BRK.B dash normalization, numeric symbol guard
type: quick
status: in-progress
created: 2026-04-26
---

Fix 4 root causes in `_resolve_yf_symbol()` in app/market_data.py:

1. Suffix order: move bare "" to last so European exchanges resolve before NASDAQ
2. Add missing .HE (Helsinki/Nokia) and .F (Frankfurt Xetra ETFs)
3. Fix early exit for dot-in-symbol: BRK.B has single-char dot = class indicator, not exchange suffix — normalize to BRK-B
4. Guard: skip numeric symbols (vwdId leakage) before wasting HTTP calls
