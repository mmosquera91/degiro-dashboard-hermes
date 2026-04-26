---
name: 20260426-currency-check-use-exchange
description: Replace _price_currency_safe fast_info.currency block with exchange-suffix-based derivation in enrich_position()
status: complete
date: 2026-04-26
commit: 
---

## Summary

Replaced the `_price_currency_safe` derivation in `enrich_position()` (app/market_data.py) to use exchange suffix instead of `fast_info.currency`.

### What changed

The old code used `ticker.fast_info.currency` to determine if the yfinance price was safe to use — but for EUR-listed USD-tracking UCITS ETFs (SXRU, VUSA, QDVD, VVGM, IGSG etc.), yfinance reports the index denomination (USD) rather than the listing/trading currency (EUR), causing false currency mismatches.

The new code derives trading currency from the resolved ticker suffix:
- `.AS`, `.PA`, `.DE`, `.F`, `.MI`, `.MC`, `.HE`, `.SW`, `.EAM`, `.EPA`, `.ETR` → EUR
- `.L` → GBP
- `""` (bare) or `.SI` → fall back to `fast_info.currency`
- `.TO` → CAD

### Verification

- Syntax check passed: `python3 -m py_compile app/market_data.py` → OK
- New `_EUR_EXCHANGE_SUFFIXES`, `_GBP_EXCHANGE_SUFFIXES`, `_USD_EXCHANGE_SUFFIXES`, `_CAD_EXCHANGE_SUFFIXES` constants defined
- `Currency mismatch for` warning log fires with exchange suffix + currency info
- All downstream uses of `_price_currency_safe` (lines ~603, ~615) continue unchanged