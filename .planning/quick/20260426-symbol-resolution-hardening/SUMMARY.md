---
name: 20260426-symbol-resolution-hardening
status: complete
completed: 2026-04-26
---

Completed 4 fixes in `app/market_data.py`, function `_resolve_yf_symbol()`:

1. Suffix order: European suffixes first, bare "" last — dual-listed stocks now resolve to EUR listing before NASDAQ
2. Added .HE (Helsinki) and .F (Frankfurt Xetra ETFs) to suffix list
3. BRK.B dot handling: single-char after dot = class indicator, normalized to BRK-B (Yahoo dash convention)
4. Numeric symbol guard: returns "" immediately for vwdId numeric strings

Commit: 202d91d
Post-deploy action: DELETE /api/admin/symbol-cache
