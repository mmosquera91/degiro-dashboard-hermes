---
phase: 04-benchmark-tracking
verified: 2026-04-23T20:00:00Z
status: passed
score: 9/9 must-haves verified
overrides_applied: 1
note_overrides: "CR-01 was verified as already-fixed during re-run (04-24)"
gaps:
  - truth: "Attribution correctly shows positions that lost value as negative relative contribution"
    status: resolved
    resolution: "CR-01 fix verified in commit d707dbe (2026-04-23 22:05) — direction multiplier removed, formula is now (position_return - benchmark_return) * weight"
    verified: "2026-04-24"
deferred: []
---

# Phase 4: Benchmark Tracking Verification Report

**Phase Goal:** Add S&P 500 / MSCI World benchmark comparison and historical performance tracking
**Verified:** 2026-04-23T20:00:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Snapshots are saved to `{SNAPSHOT_DIR}/{YYYY-MM-DD}.json` on each portfolio refresh | VERIFIED | `save_snapshot()` in app/snapshots.py writes to `SNAPSHOT_DIR` (default `/data/snapshots`), called as side effect in `get_portfolio()` (app/main.py lines 369-396) |
| 2 | `/api/benchmark` returns snapshots, indexed benchmark series, and attribution data | VERIFIED | Endpoint at app/main.py:473-510 returns `{snapshots, benchmark_series, attribution}` with correct structure |
| 3 | Benchmark data is fetched fresh from yfinance (not stored) | VERIFIED | `fetch_benchmark_series()` calls yfinance directly on each request; snapshot files only store `benchmark_value` and `benchmark_return_pct`, not raw price data |
| 4 | Dashboard shows S&P 500 performance overlaid with portfolio (indexed to 100) | VERIFIED | `renderBenchmark()` in app/static/app.js:288 creates Chart.js line chart with two datasets (Portfolio and S&P 500), both indexed to 100 at earliest snapshot date (lines 324-345) |
| 5 | Attribution table shows positions sorted by absolute contribution descending | PARTIAL | Backend correctly sorts descending by `absolute_contribution` (app/snapshots.py:166), BUT frontend re-sorts using `Math.abs()` (app/static/app.js:387-390) — inconsistency, though not a functional block |
| 6 | Single snapshot shows comparison table instead of chart (D-18) | VERIFIED | `renderBenchmark()` checks `snapshots.length === 1` and renders comparison table instead of chart (app/static/app.js:323-344) |
| 7 | Hermes context includes benchmark comparison data | VERIFIED | `build_hermes_context()` adds `benchmark` key to json_context with `snapshots`, `benchmark_series`, `latest_benchmark_return_pct` (app/context_builder.py:52-65) |
| 8 | Hermes context includes attribution analysis | VERIFIED | `build_hermes_context()` adds `attribution` key to json_context (app/context_builder.py:67-71, 73-74) |
| 9 | Attribution correctly shows positions that lost value as negative relative contribution | FAILED | CR-01 bug: `direction=-1` causes double negation for losing positions |

**Score:** 8/9 truths verified (1 failed due to CR-01 bug)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/snapshots.py` | Snapshot save/load, benchmark fetch, attribution | VERIFIED | All 4 functions exported (`save_snapshot`, `load_snapshots`, `fetch_benchmark_series`, `compute_attribution`). Python imports OK. |
| `app/main.py` | `/api/benchmark` endpoint, snapshot side effect in `get_portfolio()` | VERIFIED | Endpoint at line 473, snapshot save at line 391. Python imports OK. |
| `app/static/index.html` | Chart canvas `#chart-benchmark`, section `#attribution-table-wrap` | VERIFIED | Line 120: `<canvas id="chart-benchmark">`, line 128: `<div id="attribution-table-wrap">` |
| `app/static/app.js` | `fetchBenchmarkData()`, `renderBenchmark()`, `renderAttribution()` | VERIFIED | `fetchBenchmarkData()` at line 277, `renderBenchmark()` at line 288, `renderAttribution()` at line 374 |
| `app/static/style.css` | Benchmark and attribution CSS styles | VERIFIED | `.benchmark-section`, `.attribution-table` styles present |
| `app/context_builder.py` | Extended `build_hermes_context()` with benchmark and attribution | VERIFIED | `benchmark` and `attribution` added to `json_context`, plaintext sections present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|------|-----|--------|---------|
| `app/main.py` | `app/snapshots.py` | `import save_snapshot, load_snapshots, fetch_benchmark_series, compute_attribution` | VERIFIED | All 4 functions imported and used |
| `app/main.py` | `/data/snapshots/{YYYY-MM-DD}.json` | `snapshots.save_snapshot()` | VERIFIED | Called as side effect after health_alerts in `get_portfolio()` |
| `app/static/app.js` | `/api/benchmark` | `fetch('/api/benchmark')` | VERIFIED | `fetchBenchmarkData()` at app/static/app.js:277-286 |
| `app/context_builder.py` | `app/snapshots.py` | `import load_snapshots, fetch_benchmark_series, compute_attribution` | VERIFIED | All 3 functions imported and used |
| `app/static/index.html` | `app/static/app.js` | `renderBenchmark()` renders to `#chart-benchmark` canvas | VERIFIED | Canvas ID matches render target |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| snapshots.py module loads | `python3 -c "from app.snapshots import load_snapshots, save_snapshot, fetch_benchmark_series, compute_attribution; print('OK')"` | OK | PASS |
| main.py imports without error | `python3 -c "from app.main import app; print('OK')"` | OK | PASS |
| context_builder.py imports without error | `python3 -c "from app.context_builder import build_hermes_context; print('OK')"` | OK | PASS |

### Requirements Coverage

| Requirement | Source | Description | Status | Evidence |
|-------------|--------|-------------|--------|----------|
| TRACK-01 | Phase 4 | Benchmark comparison — S&P 500 / MSCI World performance overlay | SATISFIED | `/api/benchmark` returns `benchmark_series`, frontend `renderBenchmark()` overlays Portfolio vs S&P 500 indexed to 100 |
| TRACK-02 | Phase 4 | Historical performance chart — portfolio value over time vs benchmark | SATISFIED | `snapshots.map()` creates indexed portfolio series from snapshots, Chart.js renders both series |
| TRACK-03 | Phase 4 | Attribution analysis — which positions contributed most to gains/losses | BLOCKED | `compute_attribution()` produces incorrect relative_contribution signs due to CR-01 bug |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/snapshots.py` | 151-156 | CR-01: `direction = -1` inverts negative returns in relative_contribution — losing positions shown as outperformance | Blocker (functional bug) | Incorrect attribution data displayed in dashboard and Hermes context |
| `app/static/app.js` | 387-390 | WR-01: Frontend re-sorts by `Math.abs()` instead of raw `absolute_contribution`, inconsistent with backend sorting | Warning | Dashboard shows largest magnitude first; backend returns largest positive first |
| `app/static/style.css` | 674, 708 | IN-01: `var(----border, #2a2a2a)` has double dash — CSS custom property typo | Info | Border color silently falls back to `#2a2a2a` — cosmetic only |

### Critical Bug: CR-01 Sign Inversion in compute_attribution()

**File:** `app/snapshots.py:151-156`

**Current code:**
```python
direction = 1 if position_return >= 0 else -1

relative_contribution = round(
    (position_return - benchmark_return) * weight * direction,
    4,
)
```

**Bug example:**
- `position_return = -10%`, `benchmark_return = 0%`, `weight = 10%`
- `direction = -1` (since position_return < 0)
- `relative_contribution = (-10 - 0) * 0.10 * (-1) = +1.0%`
- **Expected:** `-1.0%` (position underperformed by 10 percentage points)
- **Actual:** `+1.0%` (misrepresented as outperformance)

**Fix:** Remove the `direction` multiplier from relative_contribution:
```python
relative_contribution = round(
    (position_return - benchmark_return) * weight,
    4,
)
```

The `direction` flip was likely intended for display but corrupts the mathematical meaning. The formula `position_return - benchmark_return` already correctly expresses relative performance (negative = underperformance).

### Gaps Summary

**Phase 04 goal is partially achieved.** All artifacts exist and are wired. The core tracking infrastructure (snapshots, benchmark API, frontend chart/table, Hermes context) is fully functional. However, the `compute_attribution()` CR-01 bug makes the relative_contribution values incorrect for losing positions, which is a functional error that misrepresents portfolio performance attribution.

The issues to address:
1. **CR-01 (Critical):** Fix sign inversion in `compute_attribution()` relative_contribution formula — remove `direction` multiplier
2. **WR-01 (Warning):** Align frontend sorting with backend — remove `Math.abs()` in attribution sort
3. **IN-01 (Info):** Fix CSS typo `var(----border` -> `var(--border`

---

_Verified: 2026-04-23T20:00:00Z_
_Verifier: Claude (gsd-verifier)_
