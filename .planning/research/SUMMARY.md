# Project Research Summary

**Project:** Brokr v1.1 — Dashboard Fix & Persistence
**Domain:** Portfolio Analytics Dashboard with Persistent Caching
**Researched:** 2026-04-24
**Confidence:** HIGH

## Executive Summary

Brokr v1.1 is a single-user portfolio analytics dashboard that enriches DeGiro holdings with yfinance market data (RSI, momentum, sector) and scores them for buy priority. The core problem requiring v1.1 fixes is that container restarts clear the in-memory session cache, causing the dashboard to show blank metrics ("-") even though snapshot files exist on disk — because snapshots store only 4 scalar fields (date, total_value, benchmark_value, return_pct), not the enriched position data needed to render per-stock metrics.

Research confirms **no new stack dependencies are needed**. The existing stdlib JSON + pathlib snapshot system is correct. The blank metrics are a data-flow bug: the session cache serves stale portfolio data on restart, but the snapshot format never included enriched positions. The fix involves extending `save_snapshot()` to accept full `portfolio_data`, adding `load_latest_snapshot()`, and restoring portfolio into `_session["portfolio"]` on startup. Five critical pitfalls were identified: silent yfinance failures cascading to blank metrics, snapshot persistence without restart recovery, partial snapshot write corruption, session expiry blocking fresh portfolio, and scoring normalization pollution from None values.

## Key Findings

### Recommended Stack

**No new dependencies required for v1.1.** The existing stack is validated and sufficient.

**Core technologies:**
- **Python 3.11** — Dockerfile base, no changes needed
- **FastAPI 0.115.6** — Route handling, Pydantic v2, static file serving
- **degiro-connector 3.0.35** — Broker API integration
- **yfinance 0.2.51** — Market data enrichment (RSI, momentum, sector, 52w range)
- **stdlib json + pathlib** — Snapshot persistence (already implemented in `snapshots.py`)
- **Chart.js 4.4.7** — Dashboard charts via CDN

**Docker requirement:** Add volume mount to `docker-compose.yml` to persist `/data/snapshots` across restarts:
```yaml
volumes:
  - ./snapshots:/data/snapshots
```

**What NOT to add:** SQLite, Redis, Celery, Dask/Polars, orjson/msgspec — these add unnecessary complexity for a single-user app.

### Expected Features

**Must have (table stakes):**
- Per-stock RSI — computed from yfinance 1y history; "-" when enrichment fails
- Per-stock Weight — % of portfolio (EUR-based); "-" when compute_portfolio_weights not called
- Per-stock Momentum Score — weighted 30d/90d/YTD; "-" when no price history
- Per-stock Buy Priority Score — composite of value_score + distance + RSI + weight; "-" when upstream fails
- Sector Allocation Chart — doughnut chart from `sector_breakdown` dict; empty dict = no chart
- Benchmark Comparison Chart — line chart indexed to 100; needs 2+ snapshots

**Should have (differentiators — already shipped):**
- Health Alerts — proactive risk signals (concentration, sector drift, drawdown)
- Buy Radar — top 3 candidates with reason strings
- Attribution Analysis — position contribution vs benchmark
- Hermes Context API — plaintext/JSON export for external AI agent

**Defer (v2+):**
- Snapshot-based historical portfolio viewer
- Export/import snapshot data for backup
- Docker volume configuration (action item for v1.1)

### Architecture Approach

The application uses a layered enrichment pipeline: DeGiro fetch -> yfinance enrichment (thread pool) -> scoring -> portfolio summary -> snapshot save. The in-memory `_session` dict caches portfolio data with 5-minute TTL. On every `/api/portfolio` call, the pipeline runs and a snapshot is saved. The critical gap is that snapshots do not include enriched position data — only total_value and benchmark scalars. After container restart, `_session` is cleared, and even with valid snapshots on disk, `get_portfolio()` cannot serve data because the session is expired and no cached portfolio exists.

**Solution architecture:**
1. **Extend `save_snapshot()`** to accept optional `portfolio_data` dict (full enriched portfolio from `_build_portfolio_summary`)
2. **Add `load_latest_snapshot()`** to load most recent snapshot with `portfolio` key populated
3. **Modify `@app.on_event("startup")`** to call `load_latest_snapshot()` and restore into `_session["portfolio"]`
4. **Modify `get_portfolio()`** flow: cache hit returns immediately; on startup-cold-start, restore from snapshot

**Anti-patterns to avoid:**
- Re-enriching on every request (yfinance is slow, defeats restart-survival)
- Storing unprocessed positions (yfinance rate limits make re-enrichment unreliable)
- Blocking startup on enrichment (requires live DeGiro session)

### Critical Pitfalls

1. **Silent yfinance Failures Cascading to Blank Dashboard Metrics** — `enrich_position()` catches all exceptions silently, scoring chain propagates None values as "0", dashboard shows "-" with no indication of staleness. Fix: Add `_enrichment_error` field, explicit error propagation, and "No data" display instead of "-".

2. **Snapshot Persistence Without Restart Recovery** — Snapshots only store 4 scalar fields, not enriched positions. After restart, `_session` is empty and `/api/portfolio` returns 401 even though valid snapshot files exist. Fix: Include full `portfolio_data` in snapshots, restore on startup.

3. **Partial Snapshot Write on Crash** — `save_snapshot()` writes JSON directly without atomic rename. Process crash mid-write produces corrupt JSON. Fix: Write to temp file then rename (atomic on POSIX).

4. **Session TTL Independent of Portfolio TTL** — Session expires at 30 min, portfolio at 5 min. When session expires but fresh snapshot exists, user sees 401 instead of serving stale portfolio. Fix: Serve fresh cached portfolio regardless of session age.

5. **Scoring Normalization Pool Pollution from None Values** — `p.get("value_score", 0) or 0` converts None to 0 before normalization, making "data missing" positions indistinguishable from "genuinely bad value" positions. Fix: Exclude None positions from normalization pool or use sentinel value.

## Implications for Roadmap

Based on research, suggested phase structure for v1.1:

### Phase 1: Snapshot Format Extension
**Rationale:** All other phases depend on having enriched portfolio data in snapshots. Cannot test restart recovery without this.
**Delivers:** Extended `save_snapshot()` accepting `portfolio_data` dict; `load_latest_snapshot()` function; backward-compatible JSON format
**Implements:** `snapshots.py` changes
**Avoids:** Pitfall 2 (snapshot persistence without recovery), Pitfall 3 (partial write corruption via rename-after-write)

### Phase 2: Startup Portfolio Restoration
**Rationale:** Startup restoration enables dashboard to serve data immediately after restart without DeGiro session. Depends on Phase 1 completing snapshot format.
**Delivers:** `@app.on_event("startup")` modified to call `load_latest_snapshot()`; `_session["portfolio"]` pre-populated; dashboard shows last-known portfolio on restart
**Implements:** `main.py` startup handler
**Avoids:** Pitfall 2, Pitfall 4 (session expiry blocking fresh portfolio)

### Phase 3: Data Enrichment & Scoring Fixes
**Rationale:** The blank metrics ("-") for RSI, Momentum, Buy Priority are caused by silent yfinance failures and None propagation through scoring. This phase adds explicit error handling and missing-data tracking.
**Delivers:** `_enrichment_error` field propagation; "No data" vs "-" display distinction; `_yfinance_available` flag per position; fixed scoring normalization excluding None values
**Implements:** `market_data.py` error handling, `scoring.py` normalization
**Avoids:** Pitfall 1 (silent yfinance failures), Pitfall 5 (scoring normalization pollution)

### Phase 4: Frontend Dashboard Verification
**Rationale:** Verify sector breakdown chart and benchmark comparison chart render correctly from restored portfolio data. Depends on Phase 2 restoring portfolio into session.
**Delivers:** Sector doughnut chart rendering from `portfolio["sector_breakdown"]`; benchmark line chart from `GET /api/benchmark`; "No data available" inline messages for failed charts
**Implements:** `static/app.js` chart rendering
**Avoids:** UX pitfalls (blank charts with no explanation)

### Phase Ordering Rationale

- **Phase 1 before 2:** Startup restoration requires snapshots to contain portfolio data
- **Phase 2 before 4:** Frontend verification needs portfolio restored on startup
- **Phase 3 can run in parallel with 1-2** but should complete before Phase 4 (enrichment errors would show as "-" in Phase 4 verification)
- **Docker volume mount** is a prerequisite for Phase 1-2 to work (verify `docker-compose.yml` has `./snapshots:/data/snapshots`)

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (Data Enrichment):** Complex yfinance error propagation — may need additional API research if edge cases discovered
- **Phase 4 (Frontend):** Chart.js rendering edge cases — existing code may have rendering logic bugs not visible in research

Phases with standard patterns (skip research-phase):
- **Phase 1 (Snapshot Format):** Well-understood JSON serialization, established patterns in `snapshots.py`
- **Phase 2 (Startup Restoration):** Standard FastAPI lifespan pattern, only modifies existing startup handler

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | No new dependencies; stdlib JSON already implemented and working |
| Features | HIGH | All features identified from codebase analysis; v1.0 shipped features confirmed |
| Architecture | HIGH | Architecture researched via code inspection; solution derived from existing patterns |
| Pitfalls | HIGH | Pitfalls observed directly in code (`market_data.py`, `scoring.py`, `main.py`, `snapshots.py`) |

**Overall confidence:** HIGH

### Gaps to Address

- **Docker volume mount verification:** Need to confirm `docker-compose.yml` has `./snapshots:/data/snapshots` configured before Phase 1
- **yfinance edge case behavior:** Some tickers may return empty `info` dict (`{}`) rather than raising exceptions — `market_data.py` needs to handle this explicitly
- **DeGiro session expiry timing:** Session TTL (30 min) vs portfolio TTL (5 min) interaction needs live testing to verify fix behavior

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `app/main.py`, `app/snapshots.py`, `app/market_data.py`, `app/scoring.py`, `app/degiro_client.py` — directly observed architecture and bugs
- Project context: `.planning/PROJECT.md` v1.1 milestone goals

### Secondary (MEDIUM confidence)
- Existing architecture research: `.planning/research/ARCHITECTURE.md` (2026-04-23)
- Existing feature research: `.planning/research/FEATURES.md` (2026-04-23)

### Tertiary (LOW confidence)
- yfinance behavior on edge-case tickers — needs live testing with actual portfolio positions

---
*Research completed: 2026-04-24*
*Ready for roadmap: yes*
