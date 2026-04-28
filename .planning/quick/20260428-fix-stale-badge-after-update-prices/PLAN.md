# Fix stale badge after Update Prices

## Problem

Three bugs prevent the stale badge from clearing after Update Prices:

1. `waitForEnrichment()` calls `apiFetch()` but treats the result as parsed JSON — `apiFetch` returns a raw `Response` object, so `status.enriching` is always `undefined`. Phase 1 never detects enriching=true and burns the full 10s timeout.
2. `_do_enrich_session()` sets `_session["last_enriched_at"]` AFTER building summary dict, so the portfolio dict stored in session lacks `last_enriched_at`. `renderDashboard()` calls `isDataStale()` which reads `portfolioData.last_enriched_at` — finds null — badge stays visible.
3. No success toast after Update Prices completes, so user can't tell if it worked.

## Changes

### app/static/app.js

**waitForEnrichment phase 1:** parse JSON from response
- BEFORE: `const status = await apiFetch("/api/enrichment-status"); if (status.enriching) break;`
- AFTER: `const res1 = await apiFetch("/api/enrichment-status"); const status1 = await res1.json(); if (status1.enriching) break;`

**waitForEnrichment phase 2:** parse JSON from response
- BEFORE: `const status = await apiFetch("/api/enrichment-status"); if (!status.enriching) {`
- AFTER: `const res2 = await apiFetch("/api/enrichment-status"); const status2 = await res2.json(); if (!status2.enriching) {`

**After renderDashboard() in success branch:** add toast
- Add: `ToastManager.show("Prices updated successfully", "success");`

### app/main.py

**_do_enrich_session():** inject `last_enriched_at` into summary before storing
- BEFORE: `with _session_lock: _session["portfolio"] = summary; _session["portfolio_time"] = datetime.now(); _session["last_enriched_at"] = datetime.now()`
- AFTER: `now = datetime.now(); summary["last_enriched_at"] = now.isoformat(); with _session_lock: _session["portfolio"] = summary; _session["portfolio_time"] = now; _session["last_enriched_at"] = now`

## Verification

1. Verify `app/static/app.js` Phase 1: `res1.json()` followed by `status1.enriching`
2. Verify `app/static/app.js` Phase 2: `res2.json()` followed by `status2.enriching`
3. Verify `app/static/app.js` success toast: `ToastManager.show("Prices updated successfully", "success");` after `renderDashboard()`
4. Verify `app/main.py` summary dict gets `last_enriched_at` before being stored in session