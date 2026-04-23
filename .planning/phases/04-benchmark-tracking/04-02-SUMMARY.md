---
phase: 04-benchmark-tracking
plan: 02
subsystem: dashboard-ui
tags: [benchmark, attribution, chart.js, frontend]
dependency_graph:
  requires:
    - 04-01  # Benchmark API endpoint (/api/benchmark)
  provides:
    - Dashboard benchmark overlay chart (Portfolio vs S&P 500, indexed to 100)
    - Dashboard attribution analysis table (sorted by absolute contribution)
  affects:
    - app/static/index.html
    - app/static/app.js
    - app/static/style.css
tech_stack:
  added:
    - Chart.js line chart with spanGaps for sparse/missing data
  patterns:
    - Indexed-to-100 dual-series comparison chart
    - Single-snapshot fallback to comparison table (D-18)
    - Attribution table sorted by absolute_contribution descending
key_files:
  created: []
  modified:
    - app/static/index.html     # Added benchmark-section and attribution-section HTML
    - app/static/app.js         # Added fetchBenchmarkData, renderBenchmark, renderAttribution
    - app/static/style.css      # Added benchmark and attribution CSS styles
decisions:
  - id: D-15
    decision: Both chart series indexed to 100 at earliest snapshot date
    rationale: "Indexed overlay gives meaningful performance comparison regardless of portfolio scale"
  - id: D-16
    decision: "Normalized 0-100 rejected"
    rationale: "Absolute indexed values preserve return magnitude information"
  - id: D-17
    decision: "Chart.js spanGaps: true enabled"
    rationale: "Allows chart to render across date gaps without breaking the line"
  - id: D-18
    decision: "Single snapshot shows comparison table instead of chart"
    rationale: "A line chart with one data point per series is meaningless"
metrics:
  duration: "~5 minutes"
  completed: "2026-04-23"
---

# Phase 04 Plan 02: Benchmark Overlay Chart and Attribution Table Summary

## One-liner

Benchmark overlay chart (Portfolio vs S&P 500 indexed to 100) and attribution analysis table with single-snapshot edge case handling.

## What Was Built

Added two new dashboard sections to the portfolio analytics UI:

1. **Benchmark Comparison Section** — A Chart.js line chart overlaying portfolio performance against the S&P 500 benchmark, both indexed to 100 at the earliest snapshot date. The chart handles sparse data via `spanGaps: true` (D-17) and falls back to a comparison table when only one snapshot exists (D-18).

2. **Attribution Analysis Section** — A table showing each position's absolute and relative contribution to portfolio performance, sorted by absolute contribution descending.

## Completed Tasks

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Add benchmark chart canvas and attribution table section to index.html | 9713f90 | app/static/index.html |
| 2 | Add renderBenchmark() and renderAttribution() to app.js | 73883c8 | app/static/app.js |
| 3 | Add CSS styles for benchmark chart and attribution table | 3c6beff | app/static/style.css |

## Deviations from Plan

None — plan executed exactly as written.

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| D-15 | Both series indexed to 100 at earliest snapshot | Indexed overlay gives meaningful comparison regardless of portfolio scale |
| D-16 | Normalized 0-100 rejected | Absolute indexed values preserve return magnitude information |
| D-17 | Chart.js spanGaps: true | Allows chart to render across date gaps without breaking the line |
| D-18 | Single snapshot shows comparison table | A line chart with one data point per series is meaningless |

## Acceptance Criteria Status

| Criterion | Status |
|-----------|--------|
| index.html has #chart-benchmark canvas | PASS |
| index.html has #attribution-table-wrap | PASS |
| benchmark-section appears after charts-section | PASS |
| renderBenchmark() creates Chart.js line chart with two datasets | PASS |
| Both series indexed to 100 at earliest snapshot date (D-15) | PASS |
| Chart uses spanGaps: true (D-17) | PASS |
| renderAttribution() creates table sorted by absolute_contribution descending | PASS |
| Single snapshot case: comparison table shown, chart hidden (D-18) | PASS |
| fetchBenchmarkData() calls GET /api/benchmark | PASS |
| CSS styles for benchmark and attribution sections present | PASS |

## Threat Flags

None. The benchmark data is public S&P 500 information rendered via Chart.js from verified JSON — no user input reaches rendering, no trust boundary is crossed.

## Self-Check

- [x] index.html: 9713f90 exists and contains #chart-benchmark and #attribution-table-wrap
- [x] app.js: 73883c8 exists and contains renderBenchmark, renderAttribution, fetchBenchmarkData
- [x] style.css: 3c6beff exists and contains .benchmark-section and .attribution-table styles
- [x] No STATE.md or ROADMAP.md modifications

## Self-Check: PASSED
