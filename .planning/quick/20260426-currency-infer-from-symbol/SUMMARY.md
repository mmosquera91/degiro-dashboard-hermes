---
name: 20260426-currency-infer-from-symbol
description: Add _infer_currency_from_symbol() to degiro_client.py and wire it into fetch_portfolio() currency resolution chain as fallback before hardcoded "EUR"
date: 2026-04-26
status: complete
---

## Summary

Added a new `_infer_currency_from_symbol()` function as a final fallback in the currency resolution chain in `fetch_portfolio()`, after `_infer_currency_from_isin()` and before the hardcoded `"EUR"` default.

## Changes

### app/degiro_client.py

**Added constant and method to DeGiroClient class (after line 487):**
- `_KNOWN_USD_SYMBOLS`: set of 50 well-known US stock tickers (UNH, AAPL, MSFT, NVDA, etc.)
- `_infer_currency_from_symbol(symbol)`: returns `"USD"` if symbol is in the set, `""` otherwise

**Updated currency resolution chain in `fetch_portfolio()`:**
- Extracted `pos_isin = prod.get("isin", "")` to avoid duplicate calls
- Added `DeGiroClient._infer_currency_from_symbol(...)` as second-to-last fallback before `"EUR"`

## Verification

- `_KNOWN_USD_SYMBOLS` found at line 491
- `_infer_currency_from_symbol` found at line 501
- Currency chain now includes `_infer_currency_from_symbol` call at line 749

## Result

UNH and NVDA (and any other symbol in `_KNOWN_USD_SYMBOLS`) will now resolve to `currency=USD` even when `products_map` has no entry for the position's product ID, enabling proper FX conversion and enrichment.