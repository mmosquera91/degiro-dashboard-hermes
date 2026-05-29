---
phase: quick-260529-lm1
plan: "01"
subsystem: enrichment-pipeline
tags: [performance, concurrency, yfinance, threading]
dependency_graph:
  requires: []
  provides: [T2-chunked-threaded-batch-download, T3-deferred-symbol-cache-save, T4-lock-safe-refresh-prices]
  affects: [app/market_data.py, app/main.py]
tech_stack:
  added: []
  patterns: [thread-local-deferral, asyncio-create-task-fire-and-forget]
key_files:
  created: []
  modified:
    - app/market_data.py
    - app/main.py
decisions:
  - "Used thread-local _save_defer flag (option a) for T3 deferral: all existing _save_symbol_cache() callers become no-ops without signature changes, preserving immediate-write behavior for non-stage-2 contexts"
  - "Defined _CHUNK_SIZE = 25 as a local constant inside enrich_positions near _fetch_and_unpack — visible at point of use, does not pollute module namespace"
  - "Wrapped T4 asyncio.create_task in a local _runner coroutine to catch HTTPException(409) from _do_enrich_session_async — prevents unhandled exception escaping background task when lock is already held"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-29T13:39:50Z"
  tasks_completed: 3
  files_modified: 2
---

# Phase quick-260529-lm1 Plan 01: Enrichment Pipeline Optimizations T2-T4 Summary

**One-liner:** Chunked threaded yf.download with deferred symbol-cache writes and lock-safe fire-and-forget refresh-prices endpoint.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| T2 | threads=True + chunking in yf.download | 98c2b52 | app/market_data.py |
| T3 | Batch symbol cache disk writes in stage 2 | 157001b | app/market_data.py |
| T4 | Acquire operation lock in /api/refresh-prices | 6394b83 | app/main.py |

## What Was Built

### T2: Chunked threaded batch price fetch (98c2b52)

Modified `_fetch_and_unpack` inside `enrich_positions` (app/market_data.py):
- Added `_CHUNK_SIZE = 25` local constant
- Symbol list is split into consecutive chunks of at most 25 before download
- Each chunk calls `yf.download(..., threads=True)` — yfinance parallelises sub-requests internally
- Per-chunk try/except preserves fault isolation: a 429 or error on one chunk does not abort others
- EU/US split (lines 1680-1681) and the Close-DataFrame/Series unpack logic are unchanged

### T3: Deferred symbol-cache disk writes (157001b)

Modified app/market_data.py:
- Added `_save_defer = threading.local()` module-level thread-local near the cache definitions (line 40)
- `_save_symbol_cache()` checks `getattr(_save_defer, "active", False)` at entry; when active, sets `_save_defer.dirty = True` and returns without writing to disk
- Stage 2 resolution loop wrapped in try/finally: sets `_save_defer.active = True` / `dirty = False` before the loop; finally block clears `active`, then calls `_save_symbol_cache()` exactly once if `dirty` is True
- In-loop `_save_symbol_cache()` call and all internal calls inside `_resolve_yf_symbol`/`_resolve_by_isin` remain in place — they are simply no-ops for disk during the window
- Non-stage-2 callers (e.g. cache-clear endpoint, other resolve paths) still write immediately — no behavior change outside `enrich_positions`

### T4: Lock-safe fire-and-forget refresh-prices (6394b83)

Modified `refresh_prices` in app/main.py:
- Replaced `threading.Thread(target=_do_enrich_session, daemon=True)` with `asyncio.create_task(_runner())`
- `_runner` is a local async coroutine that calls `_do_enrich_session_async()` (which acquires `_operation_lock` before `asyncio.to_thread(_do_enrich_session)`)
- 409 contention case caught and logged as warning; other HTTPExceptions also logged rather than escaping the background task
- 400 guard ("No portfolio loaded") and immediate `{"status": "enrichment_started"}` response preserved unchanged
- `asyncio` import confirmed at line 3 — no duplicate import added

## Verification

### Static checks (all pass)

- `grep -n "threads=True" app/market_data.py` — match at line 1692
- `grep -n "range(0, len" app/market_data.py` — match at line 1689 (chunking)
- `grep -c "_save_defer" app/market_data.py` — 12 matches (definition + docstring + usage sites)
- `grep -n "create_task" app/main.py` — match at line 908
- `grep -n "threading.Thread(target=_do_enrich_session" app/main.py` — no match (removed)

### Container tests

```
docker exec brokr bash -c "cd /app && python -m pytest tests/ -q"
123 passed, 1 warning in 5.57s
```

All 123 tests pass. Container used docker-compose.dev.yml per project memory.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None — changes are internal to the enrichment pipeline. No new network endpoints, auth paths, or schema changes introduced.

## Self-Check: PASSED

- app/market_data.py: modified (threads=True, _CHUNK_SIZE, _save_defer, try/finally wrap)
- app/main.py: modified (asyncio.create_task, _runner coroutine)
- Commits: 98c2b52 (T2), 157001b (T3), 6394b83 (T4) — all present in git log
