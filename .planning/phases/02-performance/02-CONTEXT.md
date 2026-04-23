# Phase 02: Performance - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix blocking I/O in yfinance enrichment and thread safety issues in session/FX cache. Delivers PERF-01 through PERF-03:
- `enrich_positions()` runs in thread pool — event loop stays responsive (PERF-01)
- Session cache thread-safe with lock around read-check-return sequence (PERF-02)
- FX rate cache thread-safe with proper locking (PERF-03)

</domain>

<decisions>
## Implementation Decisions

### Threading Approach (PERF-01)

- **D-01:** Use `asyncio.to_thread()` to run `enrich_positions()` synchronous inner work off the event loop
- **D-02:** Keep per-call `_yf_throttle()` inside each thread — no cross-thread coordination needed

### FX Cache Locking (PERF-03)

- **D-03:** Add `threading.RLock` to `_fx_cache` in `market_data.py` — protect reads and writes
- **D-04:** `_fx_throttle()` (if added) uses the same lock for rate limit state

### Session Cache (PERF-02)

- **D-05:** Session cache already has `_session_lock` — continue using it
- **D-06:** Verification: profile before/after to confirm event loop no longer blocks; load test for thread safety

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Codebase Concerns
- `.planning/codebase/CONCERNS.md` — H-01 (blocking I/O), M-02 (session cache reads outside lock), M-03 (FX cache has no lock), M-04 (throttle not thread-safe)

### Prior Phase Context
- `.planning/phases/01-security-hardening/01-CONTEXT.md` — Project patterns, auth decisions, session architecture

### Project Context
- `.planning/PROJECT.md` — Single-user FastAPI app, yfinance for market data, Hermes integration
- `.planning/ROADMAP.md` §Phase 2 — Phase goal, success criteria, implementation notes
- `.planning/REQUIREMENTS.md` §Performance (PERF) — PERF-01, PERF-02, PERF-03 requirements

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_session_lock` (threading.Lock in main.py) — existing synchronization primitive
- `_fx_cache` dict in market_data.py — needs a lock added around it
- `asyncio.to_thread()` — standard Python asyncio utility for offloading sync I/O

### Established Patterns
- Thread-safe session cache with `threading.Lock` — pattern already in place
- Per-call rate throttle (`_yf_throttle`) — inside each thread, no cross-thread coordination

### Integration Points
- `app/main.py` lines 323-356 — `get_portfolio()` endpoint where `enrich_positions()` is called
- `app/market_data.py` lines 283-319 — `enrich_positions()` async function (calls sync `enrich_position` in a loop)

</code_context>

<specifics>
## Specific Ideas

No specific references or "I want it like X" moments — all decisions followed straightforward performance best practices.

</specifics>

<deferred>
## Deferred Ideas

### Verification Approach
The user didn't discuss explicit verification strategy. Planner should decide profiling approach and load testing specifics.

### Session Cache Read Issue
The session cache read-check-return sequence (lines 323-327 in main.py) returns `_session["portfolio"]` by reference while the lock is held. This is acceptable — no decision made to change it.

</deferred>

---

*Phase: 02-performance*
*Context gathered: 2026-04-23*