# 20260426-price-currency-guard

## Problem

`enrich_position()` unconditionally overwrites `current_price`, `current_value`, `unrealized_pl`, and `unrealized_pl_pct` with yfinance price data. When `_resolve_yf_symbol()` returns a wrong-exchange ticker (e.g. NASDAQ USD instead of AMS EUR), the yfinance price is in USD while `avg_buy_price` is in EUR. The FX conversion in `enrich_positions()` only converts from position currency to EUR — so a USD price treated as EUR produces wildly wrong P/L.

## Fix

Inside `enrich_position()`, after creating the `yf.Ticker` object and before calling `ticker.history(period="1y")`:

1. Read `ticker.fast_info.currency` and compare it to `position["currency"]`.
2. Store `_price_currency_safe = (not yf_currency) or (yf_currency == pos_currency)`.
3. Wrap the price-update block with the `_price_currency_safe` guard. If currencies don't match, log a warning and keep DeGiro's price.

52w high/low, RSI, and performance blocks are unaffected — they don't write back to the price fields.

## Changes

- `app/market_data.py`: Added `_price_currency_safe` check before updating price fields from yfinance. Non-price metrics (RSI, 52w range, performance) still updated regardless.
