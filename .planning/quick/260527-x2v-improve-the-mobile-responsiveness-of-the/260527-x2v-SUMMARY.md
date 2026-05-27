---
phase: quick-260527-x2v
plan: "01"
subsystem: frontend/css
tags: [mobile, responsive, css, header, indexa]
dependency_graph:
  requires: []
  provides: [mobile-responsive-header, mobile-indexa-kpi-grid]
  affects: [app/static/style.css]
tech_stack:
  added: []
  patterns: [css-media-queries, flex-layout]
key_files:
  created: []
  modified:
    - app/static/style.css
decisions:
  - "CSS-only fix (no HTML changes): flex:1 1 auto / flex:0 0 auto replaces flex:1 1 100% at 420px so header children share one row"
  - "Logo heights: 60px desktop → 46px @768px → 40px @420px (minimum 40px to avoid 'tiny' appearance)"
  - "Indexa chart-wrap reduced to 220px at 420px for better phone proportions"
metrics:
  duration: "~15 minutes"
  completed_date: "2026-05-27"
  tasks_completed: 2
  tasks_total: 3
  files_modified: 1
---

# Quick Task 260527-x2v: Improve Mobile Responsiveness of the Brokr Dashboard — Summary

**One-liner:** CSS-only mobile pass fixing header logo sizing (40-46px) and single-row header layout at 390-412px by switching from full-width flex stacks to shrink-friendly flex basis, plus Indexa KPI grid/chart polish for narrow viewports.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fix header logo sizing and single-row header layout at mobile breakpoints | 00ffc3f | app/static/style.css |
| 2 | Polish Indexa KPI grid and chart sizing for mobile | 00ffc3f | app/static/style.css |
| 3 | Visual verification of mobile responsiveness | — (skipped — human checkpoint) | — |

Tasks 1 and 2 were committed together as a single atomic CSS commit since both modify `app/static/style.css` and their changes interleave across the same media query blocks.

## Changes Made

### Header logo sizing (`@media (max-width: 768px)` and `@media (max-width: 420px)`)

- Desktop: 60px (unchanged)
- Tablet (768px): 36px → **46px** (was too small after prior flex-wrap fix)
- Mobile (420px): 30px → **40px** (minimum 40px per plan constraint)

### Header single-row layout at 420px

**Problem:** Old rules set both `.header-left` and `.header-right` to `flex: 1 1 100%`, forcing them onto separate full-width rows.

**Fix:** Changed to:
- `.header-left`: `flex: 1 1 auto; min-width: 0; justify-content: flex-start;`
- `.header-right`: `flex: 0 0 auto; justify-content: flex-end; gap: 4px;`

This keeps the logo + tabs on the left and action icons on the right, all on one visual row at 390px and 412px. The `flex-wrap: wrap` safety net on `.header` remains for extreme narrow viewports (<360px).

**Strategy:** CSS-only — no HTML changes required.

Additional mobile compactness:
- `.btn-label` explicitly hidden at 420px (cascades from 768px block, restated for clarity)
- `.tab-btn` padding reduced to `3px 8px` and font-size to `0.7rem` at 420px
- `.btn` padding remains `4px 8px / 0.72rem`

### Indexa KPI grid and charts at 420px

- `.indexa-kpi-grid`: `repeat(2, 1fr)` with `gap: 8px` (was 1fr already correct, gap added)
- `.indexa-kpi-grid .kpi-card`: `padding: 10px 12px` (scoped to Indexa mobile)
- `.indexa-kpi-grid .kpi-card .card-value`: `font-size: 1.15rem` (was 1.4rem — prevents value truncation)
- `.indexa-kpi-grid .kpi-card .card-sub`: `word-break: break-word; font-size: 0.68rem` (prevents sub-text overflow for drawdown EUR+dates)
- `.indexa-charts`: `grid-template-columns: 1fr` explicitly stated at 420px (cascades from 768px, restated)
- `#indexa-view .chart-wrap`: `height: 220px` at 420px (was 260px at all sizes — better for phone height)
- `.chart-range-buttons`: `flex-wrap: wrap` at 420px so range buttons remain tappable

## Deviations from Plan

None. Plan executed exactly as written. CSS-only approach was sufficient for all layout goals without HTML structural changes.

## Task 3 Status: Pending Human Verification

Task 3 is a `checkpoint:human-verify` (skipped by executor per constraints). Visual verification required in Chrome DevTools at:

1. iPhone 12/13/14 — 390x844: Logo visible and proportionate, header single row (logo + DeGiro/Indexa tabs + action icons), no horizontal scroll, Indexa KPI 2-column grid readable
2. Pixel 7/8 — 412x915: Same checks as 390px
3. iPad portrait — 768x1024: Logo upsized from 36px → 46px, header single row, Indexa 3-column grid
4. Desktop — 1280px+: No regression (logo 60px, all grids unchanged)

## Known Stubs

None.

## Threat Flags

None. CSS-only changes, no new network surface or security-relevant changes.

## Self-Check

- [x] `app/static/style.css` modified and committed at `00ffc3f`
- [x] Logo heights confirmed: 60px base / 46px @768px / 40px @420px
- [x] `.header-left` at 420px: `flex: 1 1 auto` (not `1 1 100%`)
- [x] `.header-right` at 420px: `flex: 0 0 auto` (not `1 1 100%`)
- [x] Indexa 420px block contains KPI grid + chart-wrap + range-buttons rules
- [x] No unexpected file deletions in commit

## Self-Check: PASSED
