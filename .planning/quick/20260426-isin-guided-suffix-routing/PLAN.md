# ISIN-guided suffix routing

Route suffix scan order based on ISIN country prefix to reduce HTTP calls.

## Changes

### CHANGE 1 — Add `_get_suffix_order()` before `_resolve_yf_symbol()`
ISIN-prefix-guided suffix ordering: US/CA stocks try bare symbol first; IE/LU UCITS ETFs try .DE/.F first; GB tries .L first; etc.

### CHANGE 2 — Replace hardcoded suffix list in `_resolve_yf_symbol()`
Replace `suffixes_to_try = [".AS", ".PA", ".DE", "..."]` with `suffixes_to_try = _get_suffix_order(isin, symbol)`.

### CHANGE 3 — Add cache staleness guard in `_resolve_yf_symbol()`
When returning a cached entry, re-validate currency against position currency; evict if mismatch to clear stale USD results from before ISIN-strict-EUR fix.

## Expected outcome
- US stocks (QUBT, RGTI, etc.): 1 HTTP call instead of 11
- EUR UCITS ETFs (ESP0, ZPRR, etc.): 1-2 calls instead of 3-4
- Full refresh drops from ~2 min to ~30s
