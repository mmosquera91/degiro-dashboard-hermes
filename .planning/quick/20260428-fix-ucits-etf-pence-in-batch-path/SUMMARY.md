---
name: 260428-fix-ucits-etf-pence-in-batch-path
description: Evict stale .L cache entries, skip .L in suffix scan, GBp correction in batch path
status: complete
---

## Problem
7 UCITS ETFs (ESP0, QDVD, VVGM, QDVF, QDV5, VVSM, ZPRR) resolve to .L tickers in the resolution cache. yf.download() fetches their prices in GBp (pence) but returns no currency metadata — so the GBp safety net never fires. Batch path treats pence as GBP → 100× inflation before GBP→EUR FX conversion.

## Fixes Applied

### Fix 1 — Evict .L entries from resolution cache at load (`_load_symbol_cache`)
When loading `symbol_cache.json`, any entry whose `yf_symbol` ends in `.L` is skipped (not loaded into `_resolution_cache`). Forces cold re-resolve on next run → ISIN scan picks `.DE`.

### Fix 2 — GBp detection in batch path (`enrich_positions`)
After `yf.download()` populates `price_batch`, any symbol ending in `.L` has its price halved (`/ 100`). This corrects pence→pounds before the FX→EUR conversion.

### Fix 3 — Skip .L in suffix scan (`_resolve_yf_symbol`)
When scanning exchange suffixes for a symbol, `.L` is explicitly skipped (`continue`). IE/LU UCITS ETFs go straight to `.DE` rather than landing on LSE. The `_get_suffix_order` for IE/LU already puts `.DE` first; this just prevents `.L` from being tried as a fallback.

## Changes
- `app/market_data.py`: 3 targeted edits (cache load, batch correction, suffix skip)
- `STATE.md`: Quick task table updated

## Verification
- Syntax check passed (`python3 -m py_compile`)
- Committed as `debfd2a`
