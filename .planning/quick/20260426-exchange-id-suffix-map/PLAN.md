# Plan: exchange-id-suffix-map

Map DeGiro `exchangeId` → Yahoo Finance suffix for deterministic single-call symbol resolution.

## Changes

### CHANGE 1 — app/degiro_client.py
In `fetch_portfolio()` position construction, extract `exchangeId` from product info and include it as `exchange_id` in the position dict.

### CHANGE 2 — app/market_data.py
Add `_DEGIRO_EXCHANGE_TO_YF_SUFFIX` mapping dict after imports.

### CHANGE 3 — app/market_data.py
Add `_suffix_from_exchange_id()` helper function with 663 tiebreak logic.

### CHANGE 4 — app/market_data.py
Add `exchange_id` parameter to `_resolve_yf_symbol()` and insert Step 0 (exchangeId resolution) before the ISIN search and suffix scan.

### CHANGE 5 — app/market_data.py
Update the `enrich_position()` call site to pass `position.get("exchange_id", "")`.

## Post-deploy
DELETE /api/admin/symbol-cache and refresh once to clear any stale entries.