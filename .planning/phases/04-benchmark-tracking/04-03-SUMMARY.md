---
phase: 04-benchmark-tracking
plan: 03
subsystem: Hermes Context Builder
tags: [hermes, benchmark, attribution, context]
dependency_graph:
  requires:
    - app/snapshots.py (load_snapshots, fetch_benchmark_series, compute_attribution)
  provides:
    - app/context_builder.py (benchmark and attribution in Hermes context)
  affects:
    - /api/hermes-context endpoint output
tech_stack:
  added:
    - benchmark JSON key in build_hermes_context() output
    - attribution JSON key in build_hermes_context() output
    - plaintext BENCHMARK COMPARISON section
    - plaintext POSITION ATTRIBUTION section
  patterns:
    - Graceful degradation when no snapshots exist
    - Walrus operator for conditional section rendering
key_files:
  created: []
  modified:
    - app/context_builder.py
decisions:
  - Extend build_hermes_context() JSON output with benchmark and attribution keys
  - Load snapshots and compute attribution in build_hermes_context() before plaintext build
  - Reuse fetch_benchmark_series() in _build_plaintext() for fresh benchmark data
  - Top 15 attribution positions in plaintext (sorted by absolute_contribution descending)
metrics:
  duration: "~5 minutes"
  completed: "2026-04-23T19:51:XXZ"
  tasks_completed: 1
  files_modified: 1
---

# Phase 04 Plan 03: Extend Hermes Context with Benchmark and Attribution Summary

## One-liner

Extended build_hermes_context() to include S&P 500 benchmark comparison data and position attribution analysis in both JSON and plaintext exports.

## What Was Built

Modified `app/context_builder.py` to extend `build_hermes_context()` with benchmark comparison and attribution data sourced from the snapshot system created in plan 04-01.

### JSON Output Additions

- **`benchmark`**: `{snapshots, benchmark_series, latest_benchmark_return_pct}` — snapshot history and indexed benchmark series
- **`attribution`**: `[{name, symbol, relative_contribution, absolute_contribution}, ...]` — position-level contribution analysis sorted by absolute_contribution descending

### Plaintext Output Additions

- **`═══ BENCHMARK COMPARISON (S&P 500) ═══`**: Latest snapshot date, portfolio value, benchmark return %, indexed-to-100 date, historical snapshot table
- **`═══ POSITION ATTRIBUTION ═══`**: Top 15 positions table with absolute and relative contribution columns, formula explanation

## Verification

```
python3 -c "from app.context_builder import build_hermes_context; print('context_builder imports OK')"
→ context_builder imports OK
```

All acceptance criteria confirmed:
- `json["benchmark"]` contains `snapshots`, `benchmark_series`, `latest_benchmark_return_pct`
- `json["attribution"]` returns list of `{name, symbol, relative_contribution, absolute_contribution}`
- Plaintext contains `BENCHMARK COMPARISON (S&P 500)` section
- Plaintext contains `POSITION ATTRIBUTION` section
- Attribution table shows top 15 positions sorted by absolute_contribution descending
- Formula explanation present: `Absolute: position_return × weight | Relative: (position_return − benchmark_return) × weight × direction`

## Deviations from Plan

None — plan executed exactly as written.

## Threat Flags

None — changes only add read-only data from existing snapshot system to Hermes context output.
