---
name: 260428-fix-ucits-etf-gbp-pence-inflation
description: Fix 7 UCITS ETFs (ESP0, QDVD, VVGM, QDVF, QDV5, VVSM, ZPRR) 100x price inflation from GBp pence confusion
status: in-progress
---

## Problem
7 UCITS ETFs not in yf.download() batch — fall through to individual ticker fallback.
Their bundled_overrides.json entries still point to .L (LSE) tickers. yfinance returns
LSE prices in GBp (pence), but code treats them as GBP pounds → 100× inflation before FX conversion.

## Fix Part 1 — bundled_overrides.json
Update 7 ETF ISIN→ticker entries from .L to .DE:
  ESP0 → ESP0.DE  (IE00B...?)  → IE00...: "ESP0.DE"
  QDVD → QDVD.DE  (IE00B...?)  → IE00...: "QDVD.DE"
  VVGM → VVGM.DE  (IE00B...?)  → IE00...: "VVGM.DE"
  QDVF → QDVF.DE  (IE00B...?)  → IE00...: "QDVF.DE"
  QDV5 → QDV5.DE  (IE00B...?)  → IE00...: "QDV5.DE"
  VVSM → VVSM.DE  (IE00B...?)  → IE00...: "VVSM.DE"
  ZPRR → ZPRR.DE  (IE00B...?)  → IE00...: "ZPRR.DE"
.DE prices are in EUR — no FX conversion needed, no GBp issue.

Note: bundled_overrides.json keys are ISINs. Need to find ISINs for these 7 ETFs.
If not found in bundled_overrides.json, they may be resolved via ISIN scan instead.

## Fix Part 2 — GBp safety net in market_data.py
Before the FX conversion block (line 1318+), detect "GBp" (lowercase p) as distinct from "GBP":
  if currency == "GBp":
      price = price / 100        # convert pence to pounds
      currency = "GBP"
Apply before any GBP→EUR FX conversion.

## After Fix
- Run DELETE /api/admin/symbol-cache to clear stale .L resolution cache entries
- Run Update Prices — no GBP FX conversion warnings for these 7 ETFs
- Portfolio total should match DeGiro

## Files
- app/bundled_overrides.json
- app/market_data.py (around line 1318, FX conversion block)
