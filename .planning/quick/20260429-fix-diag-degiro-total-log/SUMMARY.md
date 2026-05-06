---
name: 20260429-fix-diag-degiro-total-log
description: Fix price_source cache-hit stamp and add missing DEGIRO REPORTED TOTAL log
status: complete
---

## Done

**Fix 1 — market_data.py:972-992 (cache-hit path `price_source`):**
Moved `position["price_source"] = "batch" if ... else "cache"` to BEFORE the `if fresh_price:` block, so it stamps even when `fresh_price` is None. Previously it was inside the `if fresh_price:` block meaning `price_source` was missing for every cache-hit position.

**Fix 2 — main.py:684 (DEGIRO REPORTED TOTAL log):**
The `[DIAG] DEGIRO REPORTED TOTAL: {summary['total_value_eur']:.2f} EUR` log already existed in the file at the right place (before `_save_snapshot_for_portfolio()`) but was missing from `_do_enrich_session()` entirely — the log was only in a different code path. Added it to `_do_enrich_session()` so both DIAG logs appear together during enrichment.

**Commit:** `1f17d9d` — "fix: set price_source always in cache-hit path; add missing DIAG log before snapshot"

## How to verify

Run the enrichment and check logs for:
- `[DIAG] TOTAL COMPUTED: {X.XX} EUR` — from `market_data.py:1462`
- `[DIAG] DEGIRO REPORTED TOTAL: {X.XX} EUR` — from `main.py:684`

If they match within <0.01 EUR, the ~2% gap is market movement between DeGiro snapshot time and yfinance fetch time — no further bug fix needed.
