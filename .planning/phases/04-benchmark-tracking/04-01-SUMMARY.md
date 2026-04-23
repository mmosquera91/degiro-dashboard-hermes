---
phase: "04"
plan: "01"
subsystem: benchmark-tracking
tags: [benchmark, snapshots, attribution, yfinance]
dependency_graph:
  requires: []
  provides:
    - TRACK-01: Benchmark comparison (S&P 500 overlay)
    - TRACK-02: Historical performance chart (snapshots)
    - TRACK-03: Attribution analysis
  affects:
    - app/main.py (get_portfolio side effect, /api/benchmark endpoint)
tech_stack:
  added:
    - app/snapshots.py (snapshot save/load, benchmark fetch, attribution)
  patterns:
    - Snapshot-on-refresh side effect pattern
    - benchmark_value indexed to 100 at first snapshot date
    - Fresh benchmark fetch (not stored) via yfinance
key_files:
  created:
    - app/snapshots.py (1121 lines)
  modified:
    - app/main.py (+74 lines)
decisions:
  - SNAPSHOT_DIR defaults to /data/snapshots
  - BENCHMARK_TICKER defaults to ^GSPC
  - benchmark_value indexed to 100 at portfolio start, not current date
  - snapshot failure is non-blocking (logged warning, does not break portfolio fetch)
metrics:
  duration: ~
  completed: "2026-04-23"
  tasks: 2/2
---

# Phase 04 Plan 01 Summary: Benchmark Tracking Backend

## Objective

Create the backend snapshot module (app/snapshots.py) and /api/benchmark endpoint. Have get_portfolio() save a snapshot as a side effect on each portfolio refresh.

## Completed Tasks

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Create app/snapshots.py with snapshot save/load, benchmark fetch, attribution | 48083e6 | app/snapshots.py |
| 2 | Add /api/benchmark endpoint and snapshot side effect to get_portfolio() | 2bc2363 | app/main.py |

## What Was Built

### app/snapshots.py

Four exported functions:

- **save_snapshot(date_str, total_value_eur, benchmark_value, benchmark_return_pct)**
  - Writes `{date_str}.json` to SNAPSHOT_DIR (default `/data/snapshots`)
  - Validates date format via `datetime.strptime` before file access (T-04-01)
  - Creates directory with `parents=True, exist_ok=True`

- **load_snapshots() -> list[dict]**
  - Reads all `{date}.json` files from SNAPSHOT_DIR
  - Returns sorted by date ascending; empty list if directory missing
  - Skips invalid files with warning log

- **fetch_benchmark_series(start_date, end_date) -> list[dict]**
  - Fetches from yfinance using BENCHMARK_TICKER (default `^GSPC`)
  - Uses `_yf_throttle()` from market_data for rate limiting
  - Returns `{"date": "YYYY-MM-DD", "value": float}` indexed to 100 at start_date
  - Benchmark data NOT stored — fetched fresh each call (D-07)

- **compute_attribution(positions, benchmark_return) -> list[dict]**
  - Implements D-11 formula:
    - `relative_contribution = (position_return - benchmark_return) * weight * direction`
    - `absolute_contribution = position_return * weight`
    - `direction = 1 if position_return >= 0 else -1`
  - Returns sorted by absolute_contribution descending
  - Handles None perf_ytd as 0

### app/main.py modifications

**Snapshot side effect in get_portfolio():**
- After health_alerts computation, before returning
- Calls `load_snapshots()` to check if first snapshot
- If existing snapshots: fetches benchmark series to compute indexed benchmark_value
- If first snapshot: benchmark_value = 100.0, benchmark_return_pct = 0.0
- Wrapped in try/except — snapshot failure is non-blocking

**New endpoint /api/benchmark:**
- Route: `GET /api/benchmark`
- Auth: requires `verify_brok_token` dependency
- Returns: `{snapshots, benchmark_series, attribution}` or `{message}` if empty
- Benchmark series fetched fresh from yfinance (not stored in snapshots)

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface

| Flag | File | Description |
|------|------|-------------|
| threat_flag: path_traversal | app/snapshots.py | Date format validated before file access — malicious filenames rejected |

## Self-Check

- [x] app/snapshots.py exists with all 4 functions exported
- [x] Python syntax valid (py_compile passes)
- [x] get_portfolio() calls save_snapshot() as side effect after health_alerts
- [x] /api/benchmark returns correct JSON structure with snapshots, benchmark_series, attribution
- [x] benchmark_series indexed to 100 at first snapshot date
- [x] Attribution sorted by absolute_contribution descending
- [x] Commit 48083e6 exists for Task 1
- [x] Commit 2bc2363 exists for Task 2

## TDD Gate Compliance

N/A — plan type is `execute`, not `tdd`.

---
*Plan 04-01 executed by gsd worktree agent on branch gsd/phase-04-benchmark-tracking*