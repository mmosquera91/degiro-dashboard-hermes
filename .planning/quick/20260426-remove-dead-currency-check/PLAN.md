---
name: 20260426-remove-dead-currency-check
description: Remove dead fast_info.currency block from enrich_position()
status: complete
---

Remove the redundant `fast_info.currency` fallback from `enrich_position()` in
`app/market_data.py`. After the exchange-suffix currency fix (commit dbd9381), both
the old `fast_info.currency` check and the new exchange-suffix check were running,
producing duplicate warnings and wasting one HTTP call per position per refresh.

Changes:
- Delete the bare-ticker `ticker.fast_info.currency` fallback (lines 615-620)
- Delete the resulting `_price_currency_safe` comparison and warning (lines 622-632)
- Delete the orphaned duplicate warning in the price-update branch (lines 673-677)
- Remove unused `_USD_EXCHANGE_SUFFIXES` and `_CAD_EXCHANGE_SUFFIXES` sets

Result: one warning per mismatch, zero extra HTTP calls.
