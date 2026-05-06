---
name: 260429-fix-double-degiro-fetch
description: Add 30s TTL cache + lock to DeGiro.fetch_portfolio() to deduplicate concurrent calls
status: complete
---

## Summary

**Symptom:** Every request showed two "Fetched 46 positions from DeGiro" log entries ~600ms apart, with HTTP 200 OK landing between them.

**Root cause:** Two independent callers of `DeGiroClient.fetch_portfolio()`:
1. `/api/portfolio` (line 577) — request handler, called when no cached portfolio exists
2. `/api/portfolio-raw` (line 650) — called when `_session["portfolio"]` is None

Both hit the network independently since there was no caching at the DeGiro client level.

**Fix applied in `app/degiro_client.py`:**
- Added module-level `_fetch_cache: dict[int, tuple[dict, float]]`, `_fetch_lock: threading.Lock()`, `_FETCH_TTL = 30.0`
- Fast path (outside lock): checks cache, returns immediately if fresh
- Slow path (under lock): double-checks then fetches, caches result by `id(trading_api)`
- TTL of 30s means any second caller within 30 seconds gets the cached result

**Verification:** Log should show exactly one "Fetched N positions from DeGiro" per enrichment cycle.