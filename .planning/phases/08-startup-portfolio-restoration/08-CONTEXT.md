# Phase 08: Startup Portfolio Restoration - Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Restore portfolio from latest snapshot on app startup so dashboard renders immediately without requiring a DeGiro session. No automatic refresh is ever triggered by the app — the user manually triggers portfolio fetch via API call. Delivers REST-01, REST-02, REST-03.

</domain>

<decisions>
## Implementation Decisions

### Startup Restoration (REST-01, REST-02)

- **D-01:** On app startup, `load_latest_snapshot()` is called and portfolio is restored into `_session["portfolio"]`
- **D-02:** Dashboard serves last-known portfolio immediately after restart (no DeGiro session required)

### No Auto-Fetch Model

- **D-03:** NO automatic portfolio refresh is triggered after startup restore — there is no persistent DeGiro session
- **D-04:** DeGiro session is always user-triggered: user calls refresh API → app connects to DeGiro → fetches portfolio → disconnects
- **D-05:** After startup restore, the app serves the snapshot portfolio only. No background task, no session check, no auto-fetch
- **D-06:** The snapshot contains the last known portfolio state from when the user last manually triggered a fetch

### Session TTL Behavior (REST-03)

- **D-07:** `_is_session_valid()` returns False in normal operation (trading_api is None — no persistent session exists)
- **D-08:** Session TTL check does not block serving restored snapshot portfolio — served directly from `_session["portfolio"]`
- **D-09:** On `get_portfolio()` call: if session valid (trading_api present) → fetch fresh; if session invalid but snapshot exists → serve snapshot; if neither → return 401

### Snapshot Loading

- **D-10:** `load_latest_snapshot()` called in `@app.on_event("startup")` context manager (not `on_startup` event)
- **D-11:** Portfolio restored into `_session["portfolio"]` before startup event completes
- **D-12:** If snapshot's `portfolio_data` is None (old-format snapshot), treat as no snapshot (warn, continue, let login page handle)
- **D-13:** If no snapshot exists on first startup, app continues normally — existing login page handles no-session state (no fail-fast)

### Session Expiry Behavior

- **D-14:** When session expired but cached portfolio exists: serve cached portfolio (no 401) — REST-03
- **D-15:** When session expired AND no cached portfolio: 401 with "Session expired" message

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

- No persistent DeGiro session — user triggers fetch manually each time
- Snapshot contains last known portfolio state from user's last manual fetch
- No auto-fetch after startup restore — user decides when to trigger a new fetch

</specifics>

<deferred>
## Deferred Ideas

### Benchmark Data on Startup Restore
Benchmark data (^GSPC series) is not stored in snapshots — fetched fresh on `/api/benchmark` call. Could store benchmark in snapshot in a future phase for full offline capability. Not planned for Phase 8.

</deferred>

---

*Phase: 08-startup-portfolio-restoration*
*Context gathered: 2026-04-24*
