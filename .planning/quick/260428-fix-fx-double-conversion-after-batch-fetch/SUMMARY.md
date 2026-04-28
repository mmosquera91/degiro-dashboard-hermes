---
name: 260428-fix-fx-double-conversion-after-batch-fetch
description: Fix FX double-conversion on Xetra ETFs after batch price fetch
type: quick
status: complete
---

## Summary

Fixed FX double-conversion bug that inflated portfolio totals for Xetra-listed ETFs.

**Root cause:** `enrich_positions()` FX conversion block (line 1309) used
`enriched_pos.get("currency")` which returned DeGiro's position currency — wrong for
Xetra UCITS ETFs where DeGiro reports USD but Yahoo Finance prices are in EUR.

**Fix:** Store exchange-suffix-derived `yf_currency` in `position["currency"]`
before the FX conversion block, ensuring correct currency comparison.

**Debug log added:**
`[DEBUG] FX conversion applied for {symbol}: {price} {from_currency} → {converted} EUR`

## Files Changed

- `app/market_data.py` — FX currency fix + debug logging

## Verification

- Python syntax check: PASS
- Import sanity check: PASS
- Exchange suffix → currency mapping: PASS (VUSA.DE→EUR, VUSA.L→GBP, bare→"")
