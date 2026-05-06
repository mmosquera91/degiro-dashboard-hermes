---
name: 260428-remove-gbp-correction-batch-path
description: Remove GBp→GBP correction block from batch path in market_data.py
type: project
status: complete
---

# 260428-remove-gbp-correction-batch-path

## What

Removed the `for sym in list(price_batch.keys()): if sym.endswith(".L"): price_batch[sym] = price_batch[sym] / 100.0` block (9 lines, lines 1336–1343) from the batch price fetch path in `app/market_data.py`.

## Why

The correction was halving all `.L` prices after `yf.download()`, but `yf.download()` already returns LSE prices in GBP pounds — not GBp pence. This caused ~50% portfolio deflation for legitimate LSE holdings (ESPO.L, QDIV.L, GOAT.L, IUES.L, NDIA.L, SMH.L, R2US.L).

The 7 UCITS ETFs with prior pence inflation (ESP0, QDVD, VVGM, QDVF, QDV5, VVSM, ZPRR) are already handled by fixes 1+3 from debfd2a (evict `.L` from resolution cache at startup, block `.L` suffix in ISIN scan → resolve to `.DE` instead). So they will never appear as `.L` in the batch path.

## What was kept

The GBp safety net in `ticker.info`/`get_price_with_fallback` path (lines ~1129–1141) was preserved unchanged. That path correctly detects `currency == "GBp"` from `ticker.info` and converts pence→pounds only when needed — appropriate for individual ticker calls where the currency metadata is available.

## Verification

- No remaining `.L` price halving in batch path
- ticker.info/fallback GBp safety net still present at lines ~1129–1141
- Fix 1 (evict `.L` from resolution cache) and Fix 3 (block `.L` in ISIN scan) unchanged

## Commit

`c75db68` — fix: remove GBp→GBP correction from batch path