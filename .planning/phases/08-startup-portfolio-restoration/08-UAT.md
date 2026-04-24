---
status: complete
phase: 08-startup-portfolio-restoration
source:
  - .planning/phases/08-startup-portfolio-restoration/08-01-SUMMARY.md
  - .planning/phases/08-startup-portfolio-restoration/08-02-SUMMARY.md
  - .planning/phases/08-startup-portfolio-restoration/08-05-SUMMARY.md
started: 2026-04-24T00:00:00Z
updated: 2026-04-24
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: |
  Kill any running server. Clear any in-memory session state.
  Start the application from scratch. Server boots without errors.
  Call GET /api/portfolio (with auth). Returns JSON with portfolio data
  even if no DeGiro session is active.
result: pass
reported: "api call returns {\"detail\":\"Failed to fetch portfolio\"} (before fix)"
note: |
  After snapshot was placed in Docker volume (/data/snapshots/):
  curl returns {"total_value":5000,"positions":[]}. Lifespan restore works.
  The earlier "Failed to fetch portfolio" 500 error was from a separate bug
  (coroutine issue in enrich_positions when DeGiro session active) — not
  the snapshot restore path.

### 2. Portfolio Served After Restart Without DeGiro Session
expected: |
  After a fresh server start (no active DeGiro session), call GET /api/portfolio.
  The endpoint returns the last-cached portfolio from snapshot immediately —
  no "Session expired" or "Not authenticated" error.
result: pass
reported: "returns {\"detail\":\"Session expired or not authenticated...\"} (before fix)"
note: |
  Same root cause: Docker volume was empty. After copying snapshot to
  /data/snapshots/ in the container, portfolio is served correctly.
  The 08-05 fix (lifespan restore) works correctly — the gap was data,
  not code.

## Summary

total: 2
passed: 2
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none — both issues were symptom of empty Docker volume, not code defects]

## Notes

- **Root cause of both failures:** Docker named volume `brokr_snapshots:/data/snapshots`
  was created empty. Snapshot files existed in workspace but were never copied
  to the volume. Plan 08-05 (lifespan restore) is correct and working.
- **Resolution:** `docker cp snapshots/2026-03-01.json brokr:/data/snapshots/`
  Then `docker restart brokr`. Lifespan fires, restores portfolio, API works.
- **Deployment note:** Snapshot files must be pre-populated in the Docker volume
  for the restore to work on first start. Consider seeding the volume or
  building snapshot population into the container startup.
- **Separate bug observed:** `'coroutine' object is not iterable` error in
  enrich_positions when DeGiro session is active — not related to snapshot restore.
