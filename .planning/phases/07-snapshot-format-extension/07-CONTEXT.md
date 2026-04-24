# Phase 07: Snapshot Format Extension - Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Extend snapshot format to store full enriched portfolio data (positions, sector_breakdown, allocation) alongside existing benchmark tracking fields. Implement atomic writes (temp file + rename + fsync) for crash safety. Delivers SNAP-01, SNAP-02, SNAP-03, DOCK-01, DOCK-02.

</domain>

<decisions>
## Implementation Decisions

### Snapshot Format (SNAP-01)

- **D-01:** New snapshot format extends old format with `portfolio_data` key containing full enriched portfolio dict (positions, sector_breakdown, allocation)
- **D-02:** Backward compatible — `load_latest_snapshot()` detects old format and returns `portfolio_data: None` (graceful degradation)
- **D-03:** Snapshot structure:
  ```json
  {
    "date": "YYYY-MM-DD",
    "total_value_eur": 12345.67,
    "benchmark_value": 100.1234,
    "benchmark_return_pct": 5.2341,
    "portfolio_data": { ... full portfolio dict ... }
  }
  ```
- **D-04:** Old snapshots without `portfolio_data` are readable — Phase 8 planner handles how `load_latest_snapshot()` handles None portfolio_data (restore from raw DeGiro vs error vs other)

### Atomic Writes (SNAP-03)

- **D-05:** Snapshot writes use temp file + rename pattern:
  1. Write to `{SNAPSHOT_DIR}/{date}.json.tmp`
  2. `os.fsync()` on the file descriptor before rename
  3. `os.rename()` to final `{date}.json`
- **D-06:** Prevents corruption if container crashes mid-write — partial writes go to `.tmp` file, final path stays intact
- **D-07:** Follows existing codebase conventions (no custom code — planner implements the standard pattern)

### Load Behavior (SNAP-02)

- **D-08:** `load_latest_snapshot()` returns `{"date": ..., "total_value_eur": ..., "portfolio_data": ...}` — portfolio data only, no benchmark fetched at load time
- **D-09:** Benchmark data (benchmark_value, benchmark_return_pct) fetched fresh from yfinance on `/api/benchmark` call — existing behavior unchanged
- **D-10:** If snapshot is old format (no `portfolio_data`), `portfolio_data` field is `None` — Phase 8 planner handles restoration logic

### Snapshot Trigger

- **D-11:** `save_snapshot()` called inside `get_portfolio()` after enrichment/scoring completes (end of the full pipeline)
- **D-12:** Snapshot happens on every user-triggered portfolio refresh — same trigger as current benchmark tracking
- **D-13:** No separate endpoint or scheduler — Phase 7 implements only the pipeline integration

### Docker Volume (DOCK-01, DOCK-02)

- **D-14:** `docker-compose.yml` uses a named volume `brokr_snapshots` mounted at `/data/snapshots`
- **D-15:** Named volume survives `docker-compose down -v` — preferred over anonymous volume
- **D-16:** Planner handles volume configuration in docker-compose.yml

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Context
- `.planning/phases/01-security-hardening/01-CONTEXT.md` — Auth token pattern, env var conventions, thread-safe patterns
- `.planning/phases/02-performance/02-CONTEXT.md` — Threading patterns, FX cache locking
- `.planning/phases/04-benchmark-tracking/04-CONTEXT.md` — Snapshot storage patterns, benchmark data fetching, SNAPSHOT_DIR conventions
- `.planning/phases/06-testing/06-CONTEXT.md` — Test patterns, mock strategy
- `.planning/ROADMAP.md` §Phase 7 — Phase goal, success criteria, requirements SNAP-01, SNAP-02, SNAP-03, DOCK-01, DOCK-02
- `.planning/REQUIREMENTS.md` §Snapshot Persistence — SNAP-01, SNAP-02, SNAP-03, SNAP-04

### Codebase
- `app/snapshots.py` — Current `save_snapshot()` and `load_snapshots()` functions to extend
- `app/main.py` — `get_portfolio()` endpoint where snapshot trigger will be added
- `docker-compose.yml` — Volume configuration to add
- `.planning/codebase/CONVENTIONS.md` — Atomic write pattern, thread-safe patterns

### Project Context
- `.planning/PROJECT.md` — Single-user architecture, yfinance for market data, no database
- `.planning/STATE.md` — Current phase position, milestone v1.1 goals

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/snapshots.py` `save_snapshot()` — already writes JSON to `{SNAPSHOT_DIR}/{date}.json`, can be extended to include `portfolio_data`
- `app/snapshots.py` `load_snapshots()` — already reads all snapshots, can be extended for single latest load
- `Path(SNAPSHOT_DIR).mkdir(parents=True, exist_ok=True)` — already creates directory
- `get_portfolio()` in main.py — full pipeline endpoint where snapshot is triggered

### Established Patterns
- JSON file storage for snapshots (Phase 4)
- `os.getenv` with defaults for configuration
- Thread-safe session with `threading.Lock`
- `logger.info/warning` for operation logging

### Integration Points
- `get_portfolio()` endpoint in `app/main.py` — where `save_snapshot()` is called after enrichment/scoring
- `docker-compose.yml` — where named volume for `/data/snapshots` is configured
- Phase 8 (Startup Portfolio Restoration) will call `load_latest_snapshot()` in `@app.on_event("startup")`

</code_context>

<specifics>
## Specific Ideas

- User wants backward compatibility with existing snapshots — don't break on upgrade
- User prefers portfolio data in snapshot for Phase 8 restoration, benchmark stays separate (fetched on demand)

</specifics>

<deferred>
## Deferred Ideas

### Benchmark Data Persistence
Benchmark data (^GSPC) is fetched fresh from yfinance. Could store in snapshot in a future phase to avoid re-fetch on restart. Not planned for Phase 7.

### Snapshot Cleanup
No automatic cleanup of old snapshots. User manages manually. Could add retention policy in future.

</deferred>

---

*Phase: 07-snapshot-format-extension*
*Context gathered: 2026-04-24*