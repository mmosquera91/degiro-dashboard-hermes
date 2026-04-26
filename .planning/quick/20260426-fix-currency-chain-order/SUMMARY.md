---
name: fix-currency-chain-order
description: Reorder currency resolution chain in fetch_portfolio() to use DeGiro product currency before exchangeId lookup
status: complete
---

## Summary

Fixed currency resolution chain in `fetch_portfolio()` (app/degiro_client.py:796-805). Moved `_currency_from_exchange_id()` after `prod.get("currency")` and `prod.get("tradingCurrency")` so DeGiro's explicit product currency takes precedence over the ambiguous exchangeId=663 → "GBP" mapping.

## Changes

- **app/degiro_client.py:796-805** — Reordered currency chain: product currency sources (`prod.get("currency")`, `prod.get("tradingCurrency")`, `pos.get("currency")`, `pos.get("currencyCode")`) now checked before `_currency_from_exchange_id()`, then ISIN/symbol inference, then EUR default.
