# Phase 04 - UI Review

**Audited:** 2026-04-24
**Baseline:** Abstract 6-pillar standards
**Screenshots:** captured (desktop, mobile, tablet)

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 4/4 | Specific, helpful empty-state messages with clear user guidance |
| 2. Visuals | 3/4 | Well-structured chart and table; `section-title` h3 mixed with `card` structure creates minor inconsistency |
| 3. Color | 2/4 | Malformed CSS variable `var(----border)` causes fallback to black; attribution table uses hardcoded hex colors instead of CSS variables |
| 4. Typography | 3/4 | ~16 distinct font sizes used; full weight range (300-700); readable but not fully systematic |
| 5. Spacing | 3/4 | Spacing is consistent with rem units; multiple distinct values but no arbitrary pixel values |
| 6. Experience Design | 4/4 | Loading states, error handling, and empty states all properly implemented |

**Overall: 19/24**

---

## Top 3 Priority Fixes

1. **Malformed CSS variable `var(----border)` in style.css** — Benchmark comparison table and attribution table borders silently fall back to `#2a2a2a` instead of using the `--border` CSS variable. Fix: change `var(----border, #2a2a2a)` to `var(--border, #2a2a2a)` at lines 674 and 715.

2. **Attribution table hardcoded colors bypass CSS variables** — The `.attribution-table td.positive` and `.attribution-table td.negative` rules use hardcoded `#22c55e` and `#ef4444` instead of `--green` and `--red` defined in CSS custom properties. Fix: replace with `color: var(--green)` and `color: var(--red)` at lines 730-735.

3. **Hardcoded S&P 500 color `#d97706` not using CSS variable** — Chart.js config uses inline `#d97706` instead of `--amber` or `--teal` token. While amber is not in the current CSS variable set, it should be added as a named token (`--amber: #d97706`) for consistency, matching how `--teal` and `--teal-light` are defined.

---

## Detailed Findings

### Pillar 1: Copywriting (4/4)

Benchmark and attribution sections use specific, helpful copy with no generic placeholders.

**Empty-state messages (app.js):**
- Line 312: `"No snapshots yet. Refresh your portfolio to record a baseline."` — actionable guidance
- Line 409: `"No attribution data yet. Attribution requires portfolio snapshots and benchmark data."` — explains why data is absent
- Line 333: `"Only one snapshot recorded. Chart will appear after next portfolio refresh."` — manages user expectations

**No generic labels found** — No instances of "Submit", "Click Here", "OK", "Cancel", "Save" in the benchmark/attribution sections.

**Score: 4/4** — Copywriting is excellent.

---

### Pillar 2: Visuals (3/4)

**Benchmark chart section (index.html lines 116-125):**
- `#chart-benchmark` canvas wrapped in `.benchmark-chart-wrap`
- Fallback comparison table in `#benchmark-comparison-table` (D-18 single-snapshot handling)
- Chart colors: Portfolio teal `#01696f`, S&P 500 amber `#d97706` — correct per spec

**Attribution table section (index.html lines 127-133):**
- `#attribution-table-wrap` contains JS-rendered table
- Two columns: Absolute Contribution and Relative Contribution
- Positive/negative coloring applied via CSS classes

**Minor visual inconsistency:**
- `section-title` class (0.95rem, font-weight 600) applied to "Benchmark Comparison" h3, while benchmark content lives in `.benchmark-chart-wrap` (a plain div, not a `.card`)
- Attribution section similarly uses `section-title` h3 without `.card` wrapper
- By contrast, positions table is wrapped in `.card`
- This creates slightly inconsistent visual weight between sections

**Score: 3/4** — Good overall structure; minor inconsistency in section container styling.

---

### Pillar 3: Color (2/4)

**CSS custom properties defined (style.css lines 4-21):**
```
--teal: #01696f; --teal-light: #028a92; --green: #22c55e; --red: #ef4444; --amber: #d97706
```

**Bug 1 — Malformed CSS variable (style.css lines 674, 715):**
```css
border-bottom: 1px solid var(----border, #2a2a2a);  /* FOUR dashes — broken reference */
```
Should be `var(--border, #2a2a2a)`. This affects the benchmark comparison table and attribution table headers. The malformed variable means the fallback value `#2a2a2a` is always used (coincidentally correct color, but bypasses the variable system entirely).

**Bug 2 — Hardcoded colors in attribution table (style.css lines 729-735):**
```css
.attribution-table td.positive { color: #22c55e; }   /* should use var(--green) */
.attribution-table td.negative { color: #ef4444; }   /* should use var(--red) */
```
These bypass the established CSS variable system. Should use `var(--green)` and `var(--red)` to respect any future theme changes.

**Chart.js hardcoded colors (app.js lines 362, 370, 538, 561):**
- `#01696f` and `#d97706` used inline in Chart.js configs (not CSS variables)
- This is acceptable since Chart.js does not read from CSS, but it creates a maintenance risk if colors ever change

**Score: 2/4** — Two bugs (malformed variable, hardcoded attribution colors) prevent higher score.

---

### Pillar 4: Typography (3/4)

**Font sizes found in style.css** (distinct values):
0.68rem, 0.72rem, 0.75rem, 0.78rem, 0.8rem, 0.82rem, 0.85rem, 0.875rem, 0.88rem, 0.9rem, 0.95rem, 1.1rem, 1.2rem, 1.4rem, 1.5rem — **15 distinct sizes**

**Font weights in use:** 300 (light), 400 (normal), 500 (medium), 600 (semibold), 700 (bold) — **5 distinct weights**

**Analysis:**
- The 15 font sizes exceed the abstract standard's threshold of >4 sizes
- However, all sizes are purposeful: the design uses fine gradations for labels (0.68-0.82rem), body text (0.85-0.9rem), and headings (0.95-1.5rem)
- No Tailwind classes — this is custom CSS with rem units, which is appropriate
- Chart.js uses Inter at sizes 10, 11 (inline in app.js lines 381-391)

**Score: 3/4** — Functional but not fully systematic. A tighter scale (8-10 sizes max) would improve maintainability.

---

### Pillar 5: Spacing (3/4)

**Spacing values found:** 4px, 6px, 8px, 10px, 12px, 14px, 16px, 20px, 28px — all using `rem` units (consistent).

**No arbitrary spacing detected** — all values are on a consistent 2-4px grid.

**Benchmark-specific spacing:**
- `.benchmark-section { margin-bottom: 1.5rem; }` (line 650)
- `.benchmark-chart-wrap { height: 280px; margin-top: 1rem; }` (lines 653-657)
- `.attribution-section { margin-bottom: 1.5rem; }` (line 699)
- Consistent with the rest of the dashboard's spacing rhythm

**Score: 3/4** — Consistent and rem-based; a tighter scale (6-8 distinct values) would be more systematic.

---

### Pillar 6: Experience Design (4/4)

**Loading states:**
- Full-screen loading overlay at app.js lines 271-277: `showLoading()` toggles `.loading-overlay`
- "Enriching" banner during background data fetch (lines 279-286)
- Connect button shows spinner during auth (lines 136, 159)
- Benchmark fetch error caught and logged silently (app.js lines 294-296)

**Error states:**
- Auth errors displayed in `#cred-error` div (app.js lines 154-155)
- Session errors in `#session-error` div (app.js lines 198-199)
- Portfolio load errors logged to console (app.js lines 235-238) — non-intrusive
- Benchmark fetch failure returns null silently — no user-facing error shown for benchmark failure

**Empty states:**
- Benchmark: `"No snapshots yet. Refresh your portfolio to record a baseline."` (app.js line 312)
- Attribution: `"No attribution data yet. Attribution requires portfolio snapshots and benchmark data."` (app.js line 409)
- Health alerts: checkmark with "All systems healthy" (app.js lines 755-761)
- All empty states are specific and actionable

**Single-snapshot fallback (D-18):**
- Comparison table shown when only one snapshot exists (app.js lines 320-337)
- Chart hidden, table displayed with message explaining the limitation

**Score: 4/4** — Excellent state coverage across all phases of user interaction.

---

## Registry Safety

Registry audit: N/A — no third-party component registry (shadcn) used in this project.

---

## Files Audited

- `/home/server/workspace/brokr/app/static/index.html` — HTML structure for benchmark and attribution sections
- `/home/server/workspace/brokr/app/static/app.js` — `fetchBenchmarkData()`, `renderBenchmark()`, `renderAttribution()` functions
- `/home/server/workspace/brokr/app/static/style.css` — CSS variables, benchmark and attribution section styles

---

## Screenshots

Captured to `.planning/ui-reviews/04-20260424-000606/`:
- `desktop.png` (1440x900)
- `mobile.png` (375x812)
- `tablet.png` (768x1024)
