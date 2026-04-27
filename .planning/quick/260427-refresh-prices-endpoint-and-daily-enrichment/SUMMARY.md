---
name: refresh-prices-endpoint-and-daily-enrichment
status: complete
---

## Summary

Added `POST /api/refresh-prices` endpoint and `_daily_enrichment_loop()` background task.

### Changes
- `_sanitize_floats_deep()` helper — applies `_sanitize_floats` recursively to all positions
- `_save_snapshot_for_portfolio()` — extracted from `get_portfolio()` inline code; handles snapshot save + benchmark cache invalidation
- `_do_enrich_session()` — shared enrichment logic (enrich_positions → compute_portfolio_weights → compute_scores → _build_portfolio_summary → save)
- `POST /api/refresh-prices` — daemon thread spawns `_do_enrich_session`; returns `{"status": "enrichment_started"}`
- `_daily_enrichment_loop()` — sleeps to 08:00 local, calls `_do_enrich_session` via `asyncio.to_thread`; started in lifespan after snapshot restore
- `get_portfolio()` updated to use `_save_snapshot_for_portfolio()`

### Files
- `app/main.py`
