# 260428-fix-fx-double-conversion-after-batch-fetch

## Problem

Portfolio total was lightly inflated after batch price fetch implementation (d7efbb5).

**Root cause:** The FX conversion decision at `enrich_positions()` line 1309 used
`enriched_pos.get("currency")` — which reflects DeGiro's reported position currency.
For Xetra ETFs (VUSA.DE, IGSG.DE, etc.), DeGiro sometimes reports `USD` even though
the Yahoo Finance price is in `EUR` (from the `.DE` exchange suffix). The yf_currency
was correctly derived from the exchange suffix, but the FX conversion block compared
against the wrong (DeGiro-reported) currency, causing EUR prices to be multiplied by
the USD→EUR FX rate — a ~1.08× inflation.

## Fix

After `yf_currency` is determined from the exchange suffix (both cache-hit and
cache-miss paths), store it in `position["currency"]`. This ensures the FX
conversion block at line 1309 uses the correct yfinance-reported price currency
rather than the potentially-wrong DeGiro position currency.

Also added debug logging when FX conversion is applied:
`[DEBUG] FX conversion applied for {symbol}: {price} {from_currency} → {converted} EUR`

## Changes

- `app/market_data.py`: After `yf_currency` is set (lines 1026-1021), store
  `position["currency"] = yf_currency` so the FX conversion block uses the
  correct currency
- `app/market_data.py`: Add `[DEBUG] FX conversion applied for ...` log line
  at FX conversion site (after line 1323)

## Scope

- Backend only (no frontend changes)
- Only affects Xetra/LSE/etc. ETFs where DeGiro currency differs from listing currency
