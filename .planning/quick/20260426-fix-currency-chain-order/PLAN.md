---
name: fix-currency-chain-order
description: Reorder currency resolution chain in fetch_portfolio() to use DeGiro product currency before exchangeId lookup
status: complete
---

## Problem

In `fetch_portfolio()` (app/degiro_client.py:797-805), `_currency_from_exchange_id(exchange_id)` is placed first in the currency resolution chain. For US stocks routed through DeGiro's exchangeId=663 (shared NYSE/LSE code), this returns "GBP", overriding the correct "USD" from `prod.get("currency")`.

## Fix

Reorder the currency chain so `prod.get("currency")` and `prod.get("tradingCurrency")` are checked before `_currency_from_exchange_id()`.

## Changes

app/degiro_client.py:797-805 — replace the `currency` tuple to put product currency sources before exchangeId lookup.
