---
phase: 04-benchmark-tracking
plan: "04"
type: gap_closure
gap_closure: true
completed: 2026-04-24
---

# Phase 04 Plan 04: Gap Closure Summary

## Gaps Fixed

### 1. hermes-context gates benchmark/attribution behind portfolio session (major)

**Root cause:** `/api/hermes-context` raised HTTP 404 when portfolio session was absent, blocking access to snapshot-based benchmark/attribution data.

**Fix:** Removed the 404 guard in `/api/hermes-context` endpoint. Now passes empty dict `{}` to `build_hermes_context()` when portfolio is None — the function already handles empty portfolio gracefully.

**Files modified:**
- `app/main.py` (line 476-485)

**Verification:**
```
GET /api/hermes-context (no portfolio) → 200
Response: {"json": {"benchmark": {"snapshots": [], "benchmark_series": [], ...}, "attribution": [], ...}, "plaintext": "..."}
```

### 2. Dashboard empty-state messages missing (minor)

**Root cause:** When no snapshots existed, benchmark chart area showed blank space instead of helpful message.

**Fix:** Added zero-snapshot check in `renderBenchmark()` that displays "No snapshots yet. Refresh your portfolio to record a baseline." Also ensured attribution section is visible even when empty.

**Files modified:**
- `app/static/app.js` (renderBenchmark, renderAttribution functions)
- `app/static/style.css` (added .benchmark-empty style)

**Verification:**
- Benchmark section shows empty-state message when no snapshots
- Attribution section visible with improved empty-state message

## Changes Made

| File | Change |
|------|--------|
| app/main.py | Removed 404 guard, pass empty dict when portfolio is None |
| app/static/app.js | Added "No snapshots yet" empty-state, improved attribution message |
| app/static/style.css | Added .benchmark-empty styling |

## Note

Container on localhost restarted with new image. Server at 192.168.2.100 still running old image — user needs to rebuild/restart that instance separately.
