# 20260426-negative-cache-final-fix

Fix negative cache scoping bug and Stockholm (.ST) log noise in `app/market_data.py`.

## Changes

1. **CHANGE 1** — `import time` is already at module level (line 9). Verify no `import time as _time` inside function bodies. (Already correct)
2. **CHANGE 2** — Replace `_time.time()` with `time.time()` in `_resolve_yf_symbol()` and `_resolve_by_isin()`. (No `_time` references found in current code)
3. **CHANGE 3** — Wrap exchangeId candidate `history()` call in try/except, log at DEBUG. (Already implemented at line 401-416)

## Verification

Current code already implements all requested changes:
- `time` is imported at module level (line 9)
- No `_time.time()` references exist
- Candidate verification has try/except with DEBUG logging (lines 401-416)

No code changes needed. Confirm and close.
