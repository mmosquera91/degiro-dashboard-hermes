---
name: 260429-cleanup-ccy-and-724
status: complete
---

## Summary

All three items completed in a single commit:

1. **ccy= fix** — stamp path now defaults to `"USD"` when `yf_currency` is empty after suffix-based derivation. Applied to `enrich_position` fast-path at `app/market_data.py:986`.

2. **RES_PROBE added** — two diagnostic logs at line 1391-1393 probe the resolution cache for broker symbol "724" and any key starting with "724". Will reveal the actual key format or confirm no entry exists.

3. **Diagnostic cleanup** — removed BATCH_INPUT, BATCH_OUTPUT, BATCH_KEYS, and BATCH_PROBE lines. Kept YFSYM, RES_PROBE, DIAG TOTAL COMPUTED, and [STAMP] warnings.

## Commit

- `d9ec0e9` fix: set USD as default currency in stamp path; add RES_PROBE for position 724

## Next Steps

Run `/update-prices` and inspect RES_PROBE output in logs for broker symbol "724" to understand why resolution cache returns None (key format mismatch or genuinely missing entry).