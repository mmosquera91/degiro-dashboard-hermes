# Phase 08: Startup Portfolio Restoration - Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Restore portfolio from latest snapshot on app startup so dashboard renders immediately without requiring a DeGiro session. After serving restored data, trigger background refresh if session is available. Delivers REST-01, REST-02, REST-03.

</domain>

<decisions>
## Implementation Decisions

### Startup Restoration (REST-01, REST-02)

- **D-01:** Hybrid restore strategy — serve snapshot immediately on startup, then background refresh in background if DeGiro session is valid
- **D-02:** Skipped TTL check for restored portfolio — treated as fresh data (no 5-min auto-refresh trigger on startup-restore)
- **D-03:** Background refresh triggers only if `_is_session_valid()` returns true after restore
- **D-04:** If no snapshot exists on first startup, app continues normally — existing login page handles no-session state (no fail-fast)

### Portfolio TTL Behavior (REST-03)

- **D-05:** Restored portfolio bypasses `_is_portfolio_fresh()` TTL check — served on `/api/portfolio` without triggering 401
- **D-06:** TTL only applies to portfolio fetched via live DeGiro session, not to restored-from-snapshot portfolio
- **D-07:** On `get_portfolio()` call: if session valid → background refresh; if session invalid but snapshot exists → serve snapshot; if neither → 401

### Snapshot Loading

- **D-08:** `load_latest_snapshot()` called in `@app.on_event("startup")` context manager (not `on_startup` event)
- **D-09:** Portfolio restored into `_session["portfolio"]` before startup event completes
- **D-10:** If snapshot's `portfolio_data` is None (old-format snapshot), treat as no snapshot (warn, continue, let login page handle)

### Background Refresh

- **D-11:** After startup restore, trigger `get_portfolio()` once in background if session valid — updates metrics via yfinance enrichment
- **D-12:** Background refresh is non-blocking — startup completes regardless of refresh outcome

### Session Expiry Behavior

- **D-13:** When session expired but cached portfolio exists: serve cached portfolio (no 401) — REST-03
- **D-14:** When session expired AND no cached portfolio: 401 with "Session expired" message

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Context
- `.planning/phases/07-snapshot-format-extension/07-CONTEXT.md` — Snapshot format, load_latest_snapshot(), portfolio_data structure, atomic write pattern
- `.planning/ROADMAP.md` §Phase 8 — Phase goal, success criteria, requirements REST-01, REST-02, REST-03
- `.planning/REQUIREMENTS.md` §Startup Restoration — REST-01, REST-02, REST-03

### Codebase
- `app/snapshots.py` — `load_latest_snapshot()` function to call on startup
- `app/main.py` — FastAPI lifespan context manager, `@app.on_event("startup")`, `_session` dict, `_is_session_valid()`, `_is_portfolio_fresh()`, `get_portfolio()` endpoint
- `app/main.py` §_build_portfolio_summary — Portfolio structure that gets restored

### Architecture
- `.planning/codebase/CONVENTIONS.md` — Thread-safe session patterns (threading.Lock around _session access)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `load_latest_snapshot()` in `app/snapshots.py` — already implemented, returns `{"date", "total_value_eur", "benchmark_value", "benchmark_return_pct", "portfolio_data"}`
- `_session["portfolio"]` — key where restored portfolio is stored
- FastAPI lifespan context manager — place to add startup restoration before first request

### Established Patterns
- Thread-safe `_session` access via `_session_lock` (all reads/writes of _session must hold this lock)
- Non-blocking snapshot saves in `get_portfolio()` (try/except, non-fatal)
- `asyncio.to_thread()` for running sync functions (enrichment) in async context

### Integration Points
- `@app.on_event("startup")` or lifespan context manager — where to call `load_latest_snapshot()`
- `get_portfolio()` endpoint — already checks `_session["portfolio"]` and serves it if present (lines 361-364)
- Existing login page handles no-session state — Phase 8 doesn't need to add new UI for missing snapshot

</code_context>

<specifics>
## Specific Ideas

- User wants background refresh after restore — hybrid approach, not pure snapshot-only serve
- User noted existing login page handles no-snapshot scenario — no need for additional empty-state UI for missing snapshot on first startup

</specifics>

<deferred>
## Deferred Ideas

### Benchmark Data on Startup Restore
Benchmark data (^GSPC series) is not stored in snapshots — fetched fresh on `/api/benchmark` call. Could store benchmark in snapshot in a future phase for full offline capability. Not planned for Phase 8.

</deferred>

---

*Phase: 08-startup-portfolio-restoration*
*Context gathered: 2026-04-24*