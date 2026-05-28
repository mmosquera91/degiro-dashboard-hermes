---
phase: quick-260528-wtv
plan: 01
subsystem: frontend
tags: [css, ui, accessibility, responsive, dark-theme]
dependency_graph:
  requires: []
  provides: [design-token-system, responsive-breakpoints, a11y-focus-states, scroll-ux-mobile]
  affects: [app/static/style.css, app/static/index.html]
tech_stack:
  added: []
  patterns: [CSS custom properties design tokens, BEM-adjacent class hierarchy, sticky positioning scroll-ux]
key_files:
  modified:
    - app/static/style.css
    - app/static/index.html
  created: []
decisions:
  - "scroll-ux (pure CSS) chosen for positions-table mobile treatment — zero JS risk"
  - "Bumped --text-muted from #555 to #6b6b6b for improved contrast without breaking visual hierarchy"
  - "Added 480px breakpoint tier alongside existing 420px/768px to give cleaner KPI grid step-down"
metrics:
  duration: 7 minutes
  completed: "2026-05-28"
  tasks_completed: 3
  tasks_total: 3
---

# Phase quick-260528-wtv Plan 01: UI Revamp Summary

**One-liner:** Comprehensive CSS/markup polish adding `--gold`/spacing/type-scale tokens, 1024px breakpoint, scroll-ux pinned-column mobile table, real `border-color` transitions replacing dead `--border` pseudo-rules, and ARIA accessibility attributes.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Design-system foundation — tokens, typography, spacing, dark-mode | ac341c3 | app/static/style.css |
| 2 | Responsive breakpoints, micro-interactions, focus/accessibility states | c8dbe9a | app/static/style.css, app/static/index.html |
| 3 | checkpoint:decision (scroll-ux pre-decided) | — | — |
| 4 | Scroll-ux mobile treatment + final consistency sweep | fa8471f | app/static/style.css |

## What Was Built

### Task 1 — Design token system
- Added `--gold: #d97706` and `--gold-dim` tokens; replaced all `#d97706` literals
- Completed spacing scale: `--space-1/2/6/8` alongside existing `--space-3/4/5`
- Added type scale: `--text-sm/base/md/lg/xl` for consistent hierarchy
- Bumped `--text-muted` from `#555` to `#6b6b6b` (improved contrast)
- Replaced stray `#444`/`#888`/`#ccc` in `.chart-range-buttons` with token refs
- Fixed all dead `--border` pseudo-transitions on `.btn`, `.filter-tab`, `input`
- Added `@media (prefers-reduced-motion: reduce)` block
- Added `border-color` transition to `.card`

### Task 2 — Responsiveness, micro-interactions, accessibility
- Added 1024px breakpoint: KPI grids step 6→4→3→2 (was 6→3→2)
- Added 480px breakpoint tier for small mobiles
- Added global `:focus-visible` outline with `var(--teal-light)`
- Fixed `.filter-tab:hover/.active` dead `--border` rules → real `border-color`
- Added `.btn-primary` hover lift and `:active` pressed state
- Added ARIA: `role="tablist"` + `role="tab"` on filter-tabs; `role="group"` on chart-range-buttons
- Added `aria-label` to positions-table, alloc-bar, all action buttons, lock-btn
- Added `scope="col"` to all `th` in positions and funds tables
- Capped chart-wrap heights at mobile breakpoints

### Task 4 — Scroll-ux mobile + final sweep
- Strengthened `.table-wrap::after` scroll-shadow: 48px wide, `rgba(0,0,0,0.6)` — clearly visible on dark surface
- Applied scroll-shadow and sticky `.col-name` at both 480px and 420px breakpoints
- Increased mobile td/th vertical padding for easier touch targets on expandable rows
- app.js left byte-unchanged (scroll-ux is pure CSS)
- Final sweep: zero remaining `#d97706` literals outside `:root` token definition, zero dead `--border` rules, CSS braces balanced (330/330)

## Compatibility Verification

- `colspan="11"` count in app.js: **2** (unchanged)
- `data-sort` count in index.html: **11** (unchanged)
- `data-filter`, `data-range`, `data-view` attributes: all preserved
- Selectors intact: `.filter-tab`, `.col-name`, `.row-detail`, `.kpi-card`, `.private-value`, `.hhi-pill`, body classes `view-degiro`/`view-indexa`/`privacy-mode`

## Deviations from Plan

### Auto-fixed Issues

None — plan executed as written.

### Implementation Notes

- The plan mentioned `--text-muted` as `#555` but also noted `#7a7974` as a possible improvement. Chose `#6b6b6b` as a balanced mid-point that passes WCAG AA for the relevant use cases (card labels, de-emphasized text) without over-brightening purely decorative muted text.
- The existing Indexa-section `@media (max-width: 420px)` block duplicated `indexa-kpi-grid` rules. Consolidated into the new 480px tier to avoid specificity conflicts, keeping 420px block for font-size and layout overrides only.

## Known Stubs

None — all token wiring and CSS changes are complete. No placeholder content or empty data flows introduced.

## Threat Flags

None — this is a purely presentational CSS/markup pass. No new network endpoints, auth paths, file access patterns, or schema changes.

## Self-Check: PASSED

- `app/static/style.css` exists and has balanced braces (330/330)
- `app/static/index.html` exists with all required ARIA attributes
- `app/static/app.js` is byte-unchanged (verified via `git diff`)
- Commits ac341c3, c8dbe9a, fa8471f all present in git log
