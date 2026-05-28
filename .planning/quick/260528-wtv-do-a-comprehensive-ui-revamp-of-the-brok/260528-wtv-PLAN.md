---
phase: quick-260528-wtv
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - app/static/style.css
  - app/static/index.html
  - app/static/app.js
autonomous: false
requirements: [UI-REVAMP]
must_haves:
  truths:
    - "Dashboard is usable and readable on mobile (≤420px), tablet (≤768px), and desktop without horizontal page overflow"
    - "Spacing, font sizes, and dark-theme colors are consistent across all sections via design tokens"
    - "Interactive elements (buttons, tabs, table rows, sort headers) have visible hover AND keyboard-focus states"
    - "Positions table on mobile is navigable via improved scroll UX with a pinned name column and a visible scroll affordance"
    - "All existing JS data flow still works — selectors (.filter-tab, th[data-sort], .range-btn, #positions-body, #indexa-funds-body), colspans, and toggle classes are unchanged"
  artifacts:
    - path: "app/static/style.css"
      provides: "Expanded design-token system, consistent spacing/typography, micro-interactions, accessible focus states, improved responsive breakpoints"
    - path: "app/static/index.html"
      provides: "ARIA labels and roles on interactive controls; no structural changes that break app.js selectors"
  key_links:
    - from: "app/static/style.css"
      to: ":root design tokens"
      via: "var() references replacing hardcoded values"
      pattern: "var\\(--space|var\\(--text|var\\(--teal"
---

<objective>
Comprehensive visual/polish revamp of the Brokr dashboard. Purely a CSS + markup-attribute pass: improve responsiveness, typography/spacing consistency, micro-interactions, accessibility, and dark-mode consistency. NO backend changes, NO change to JS data flow or DOM contracts.

Purpose: The dashboard works but has inconsistent spacing, incomplete responsive breakpoints, weak focus states, and a cramped positions table on mobile. This pass tightens the design system and improves UX without touching functionality.

Output: A polished `style.css`, ARIA-enhanced `index.html`, and (only if the card-layout option is chosen) minimal `data-label` additions in `app.js` that do NOT alter any selector, colspan, or class used for behavior.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@app/static/index.html
@app/static/style.css
@app/static/app.js

<constraints>
HARD COMPATIBILITY RULES — verify before editing, do not break any of these:
- Positions table rows are built in app.js `renderPositions()` as 11 `<td>` cells; the detail row and the error row use `colspan="11"`. Do NOT change the column count or colspans.
- JS depends on these selectors/attributes — keep them exactly: `.filter-tab` + `data-filter`, `#positions-table th[data-sort]`, `.range-btn` + `data-range`, `#positions-body`, `#indexa-funds-body`, `.row-detail` / `.expanded`, `.col-name`, `.private-value`, `.kpi-card`, `.card-value`, `.card-sub`, `.hhi-pill`, `#alloc-stocks-bar`, `#alloc-etfs-bar`, body classes `view-degiro`/`view-indexa`/`privacy-mode`.
- Charts are Chart.js canvases sized by `.chart-wrap` height (CSS) with `maintainAspectRatio:false`. Changing `.chart-wrap` height is safe; do not remove `position:relative` or the `canvas { width/height:100% !important }` rule.
- Prefer evolving the existing `:root` token system over rewriting. Tokens already present: `--bg --surface --surface-hover --border --text --text-dim --text-muted --teal --teal-light --green --red --radius* --space-3/4/5 --shadow-*`. Note `--gold` is referenced but never defined — define it.
- Known dead CSS: several rules treat `--border` as an animatable/settable border property (e.g. `transition: ... --border 0.15s`, `:hover { --border: ... }`, `input:focus { --border: ... }`). These are no-ops. Replace with real `border-color` declarations where a border change is intended.
- This is a single-file CSS app loaded via `<link href="/static/style.css">`. No build step.
</constraints>

<verification_setup>
There is no automated CSS/visual test harness in this repo. Automated verification per task is limited to static checks (grep/parse). Final visual confirmation is a human checkpoint. Build/serve via `docker-compose.dev.yml` per project memory.
</verification_setup>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Design-system foundation — tokens, typography, spacing, dark-mode consistency</name>
  <files>app/static/style.css</files>
  <action>
Evolve the existing `:root` token system (do not rewrite it). Additions/normalizations:
- Define the missing `--gold: #d97706;` and `--gold-dim: rgba(217,119,6,0.12);` token and replace literal `#d97706` usages across the file (allocation bar, accent-gold, hhi-pill concentrated, stale-badge, alert warn) with `var(--gold)` / `var(--gold-dim)` for consistency.
- Complete the spacing scale: add `--space-1: 4px; --space-2: 8px; --space-6: 24px; --space-8: 32px;` alongside existing `--space-3/4/5`. Replace ad-hoc pixel margins/paddings in section rules (`margin-bottom: 20px`, `gap: 12px`, `padding: 14px 16px`, etc.) with the nearest scale token. Do this for the major section/card/grid rules; leave hairline values (1px borders, 2px accents) literal.
- Establish a type scale as tokens: add `--text-sm: 0.78rem; --text-base: 0.85rem; --text-md: 0.95rem; --text-lg: 1.1rem; --text-xl: 1.4rem;` (keep existing `--text-xs`). Replace scattered font-size values on `.section-title`, `.chart-title`, `.card-label`, `.card-sub`, `.btn`, `.tab-btn`, `.filter-tab`, table cells with these tokens so the hierarchy is consistent. Keep `.card-value` clamp() as-is.
- Dark-mode consistency: audit every hardcoded color. Replace stray literals like `#444`/`#666`/`#ccc`/`#888` in `.chart-range-buttons` and chart-button hover with token equivalents (`--border`, `--text-muted`, `--text-dim`, `--text`). Ensure all surfaces use `--surface`, all borders use `--border`, all dim text uses `--text-dim`. The Indexa view and DeGiro view must share identical surface/border/text tokens (they already use `.card`/`.kpi-card` — just verify no Indexa-specific literal overrides introduce mismatch).
- Add a smooth color/background transition baseline: ensure `.card` keeps its existing box-shadow transition; add `transition` for `border-color` where hover/focus changes it.
- Respect reduced motion: add `@media (prefers-reduced-motion: reduce) { *, *::before, *::after { transition-duration: 0.01ms !important; animation-duration: 0.01ms !important; } }`.

Do NOT change any selector names, layout structure, or grid column counts in this task — only token plumbing, colors, spacing, and font sizes.
  </action>
  <verify>
  <automated>cd /home/server/workspace/brokr && grep -q -- '--gold:' app/static/style.css && grep -q -- '--space-6:' app/static/style.css && grep -q -- '--text-lg:' app/static/style.css && grep -q 'prefers-reduced-motion' app/static/style.css && echo TOKENS_OK</automated>
  </verify>
  <done>New tokens (`--gold`, `--space-1/2/6/8`, `--text-sm/base/md/lg/xl`) are defined in `:root`; literal `#d97706` and stray grey literals are replaced with tokens; reduced-motion media query present; no selector renamed; file is valid CSS (no unbalanced braces).</done>
</task>

<task type="auto">
  <name>Task 2: Responsive breakpoints, micro-interactions, focus/accessibility states</name>
  <files>app/static/style.css, app/static/index.html</files>
  <action>
RESPONSIVENESS (work within existing 768px and 420px media blocks; add a mid 1024px tier only if needed):
- KPI grids: smooth the steps. DeGiro `.kpi-grid` is `repeat(6,1fr)` → at ≤1024px use `repeat(4,1fr)` (add tier), ≤768px `repeat(3,1fr)` (exists), ≤480px `repeat(2,1fr)`. Indexa `.indexa-kpi-grid` is `repeat(5,1fr)` → ≤1024px `repeat(4,1fr)`, ≤768px `repeat(3,1fr)` (exists), ≤480px `repeat(2,1fr)` (exists at 420px — shift to 480px or keep, your discretion for a cleaner breakpoint).
- Allocation bar header: the existing 420/768px handling collapses the 3-column grid; verify the stocks/ETFs labels and the title remain legible and the bar spans full width. Keep `#alloc-stocks-bar`/`#alloc-etfs-bar` untouched.
- Charts/radar/winners-losers already collapse to 1 column at 768px — verify chart-wrap heights aren't too tall on mobile (cap at ~200px ≤480px).

MICRO-INTERACTIONS (subtle, fast, 120–180ms, ease):
- Buttons (`.btn`, `.btn-outline`, `.btn-primary`): add subtle hover lift/`background` transition and an `:active` pressed state (slight translateY or reduced opacity). Replace the dead `transition: ... --border 0.15s` with real `border-color` transition, and replace `.btn-outline:hover { --border: ... }` with `border-color: var(--text-muted);`.
- Tabs (`.tab-btn`, `.filter-tab`): smooth background/color transition (mostly present) — fix `.filter-tab:hover`/`.active` dead `--border` rules to real `border-color`.
- Table rows: keep existing `tbody tr:hover` background; add a subtle transition already present — ensure the expanded `.row-detail` reveal has a gentle background.
- Loading states: the spinners exist; ensure `prefers-reduced-motion` (from Task 1) neutralizes spin. Add a subtle skeleton/pulse class `.is-loading` (opacity pulse) available for future use on `.card` — optional, only if cheap.
- Form inputs: replace dead `input { transition: --border 0.15s }` and `input:focus { --border: var(--teal) }` with real `border-color` transition + `border-color: var(--teal)` on focus.

ACCESSIBILITY:
- Add a global visible focus style: `:focus-visible { outline: 2px solid var(--teal-light); outline-offset: 2px; }` and remove reliance on default `outline:none` where it kills keyboard focus (the form input sets `outline:none` — pair it with the focus-visible border so keyboard users still see focus).
- Color contrast: `--text-muted: #555` on `--surface: #1a1a1a` is below WCAG AA for small text. Bump `--text-muted` to a more legible value (e.g. `#7a7974` or `#6b6b6b`) used for de-emphasized-but-readable text; keep truly decorative uses subtle. Verify `.card-label`/`.card-sub` remain readable.
- ARIA in index.html (markup-only, no selector/structure changes):
  - `#btn-refresh`, `#btn-update-prices`, `#btn-export`, `#btn-refresh-indexa`, `#btn-save-snapshot`: add descriptive `aria-label` (titles already exist — mirror them).
  - `.filter-tabs` container: add `role="tablist"` and each `.filter-tab` `role="tab"` with `aria-pressed`/`aria-selected` left for JS-free static default (set `aria-selected` on the active one). Do NOT add/remove classes the JS toggles; only static ARIA attributes.
  - `.chart-range-buttons`: add `role="group"` and `aria-label="Performance range"`.
  - `#positions-table`: add `aria-label="Positions"`; sortable `th[data-sort]` add `aria-sort` is JS-managed-only, so add a static `scope="col"` to all `th` instead (safe, no JS dependency).
  - `#alloc-bar`: add `role="img"` with `aria-label="Stocks versus ETFs allocation"`.
  - Toast container already has `aria-live="polite"` — leave it.
  - Confirm every `<button>` that contains only an icon has an accessible name (privacy button already has aria-label; lock link has title — add `aria-label="Lock session"`).

Verify after edits: no `data-filter`, `data-sort`, `data-range`, `data-view` attribute removed; no element id changed; colspans untouched.
  </action>
  <verify>
  <automated>cd /home/server/workspace/brokr && grep -q 'focus-visible' app/static/style.css && grep -Eq '@media \(max-width: *1024px\)' app/static/style.css && grep -q 'aria-label="Lock session"' app/static/index.html && grep -q 'role="group"' app/static/index.html && [ "$(grep -c 'data-sort' app/static/index.html)" = "11" ] && echo A11Y_OK</automated>
  </verify>
  <done>Focus-visible outline present; 1024px tier added; KPI grids step smoothly 6/5→4→3→2; dead `--border` pseudo-rules replaced with real `border-color`; `--text-muted` contrast improved; ARIA labels/roles added in markup; all 11 `data-sort` headers and all `data-filter`/`data-range`/`data-view` attributes intact; no id renamed; colspans unchanged.</done>
</task>

<task type="checkpoint:decision" gate="blocking">
  <decision>Positions table mobile treatment: improved horizontal-scroll UX vs. CSS card layout</decision>
  <context>
The positions table has 11 columns and is the densest element on mobile. Two viable approaches with different risk profiles. The card approach requires a tiny app.js change (adding `data-label` attributes to each `<td>`); the scroll approach is pure CSS. This choice affects Task 4 implementation, so it must be decided before implementing.
  </context>
  <options>
    <option id="scroll-ux">
      <name>Enhanced horizontal scroll (pure CSS, lowest risk)</name>
      <pros>No app.js change at all. Sticky `.col-name` first column (partially present) + clear right-edge scroll-shadow affordance + larger touch targets + momentum scroll. Zero risk to JS data flow. Keeps all 11 columns accessible.</pros>
      <cons>Still requires horizontal scrolling on small screens; less "native app" feel than cards.</cons>
    </option>
    <option id="card-layout">
      <name>CSS card layout on mobile (needs minimal app.js data-label additions)</name>
      <pros>Each position becomes a stacked card on ≤480px — no horizontal scroll, very mobile-friendly. Implemented via CSS `display:block` on `tr`/`td` + `td::before { content: attr(data-label); }`.</pros>
      <cons>Requires adding `data-label="Value"` etc. to each `<td>` template string in app.js `renderPositions()` (the detail/expand row and click toggle must still work; colspan stays 11; selectors unchanged). Slightly higher risk; the expand-detail interaction needs verification under the block layout.</cons>
    </option>
  </options>
  <resume-signal>Select: scroll-ux or card-layout</resume-signal>
</task>

<task type="auto">
  <name>Task 4: Implement chosen positions-table mobile treatment + final consistency sweep</name>
  <files>app/static/style.css, app/static/app.js</files>
  <action>
Implement the option selected in Task 3.

IF "scroll-ux" (pure CSS, app.js UNCHANGED):
- In the ≤480px (and ≤768px) blocks, keep `.table-wrap { overflow-x:auto; -webkit-overflow-scrolling:touch }`. Strengthen the existing right-edge scroll-shadow (`.table-wrap::after` gradient) so it is clearly visible on the dark surface, and make it fade out when fully scrolled is NOT required (CSS-only static gradient is fine).
- Pin the first column: keep `.col-name { position:sticky; left:0; background:var(--surface); z-index:3 }` and ensure the header cell stays above it. Verify the sticky header `th` z-index ordering (header z above body, name-column header highest) is correct so nothing overlaps wrong.
- Increase mobile touch target: bump `td`/`th` vertical padding slightly on ≤480px for easier tapping (rows are clickable to expand).
- Do NOT touch app.js.

IF "card-layout":
- In app.js `renderPositions()`, add a `data-label` attribute to each of the 11 `<td>` cells in the main row template (e.g. `<td data-label="Value" class="private-value">`). Do NOT change the cell order, count, classes used by JS, the colspan="11" detail/error rows, the `tr.dataset.id`, the click handler, or `.col-name`. The detail row stays a single `colspan="11"` cell.
- In style.css, add a ≤480px block that converts `.positions-table thead { display:none }`, `.positions-table tr { display:block; ... }`, `.positions-table td { display:flex; justify-content:space-between }`, `td::before { content: attr(data-label); color:var(--text-dim) }`. Ensure `.row-detail` (the colspan cell) still spans full width and its `.detail-grid` renders; ensure `.row-detail.expanded` toggle still reveals it (the JS toggles the class — CSS must show it as a block when expanded).
- Verify the click-to-expand still works conceptually: tapping a card toggles `.row-detail.expanded` on the next sibling row; in block layout that detail row must `display:block` when expanded and `display:none` otherwise.

BOTH paths — final consistency sweep:
- Re-scan style.css for any remaining hardcoded `#d97706`, stray greys, or `--border`-as-property dead rules and fix.
- Ensure the funds table (`#indexa-funds-body`, 7 columns) on mobile uses the SAME treatment approach chosen (if card-layout, the funds table can keep scroll-ux since its rows are JS-rendered separately — note: applying card-layout there would require data-labels in `renderIndexaFunds()`; keep funds table on scroll-ux to limit scope unless trivial).
- Verify no unbalanced braces and that every interactive element has a focus-visible style.
  </action>
  <verify>
  <automated>cd /home/server/workspace/brokr && python3 -c "import pathlib,sys; s=pathlib.Path('app/static/style.css').read_text(); sys.exit(0 if s.count('{')==s.count('}') else 1)" && grep -c 'colspan="11"' app/static/app.js | grep -q '2' && echo SWEEP_OK</automated>
  </verify>
  <done>Chosen mobile treatment implemented; CSS braces balanced; if card-layout chosen, app.js still emits exactly 11 `<td>` cells per row with `colspan="11"` on detail + error rows and all JS selectors/classes intact; if scroll-ux chosen, app.js is byte-unchanged; positions and funds tables both usable on mobile; final color/token sweep done.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>
A comprehensive CSS/markup polish of the dashboard: expanded design tokens (spacing/type/color scales, `--gold`), consistent dark-theme colors, smoother responsive breakpoints (KPI grids step 6/5→4→3→2), micro-interactions (button hover/active, real border-color transitions replacing dead `--border` rules), accessible focus-visible outlines and ARIA labels/roles, improved contrast, and the chosen positions-table mobile treatment.
  </what-built>
  <how-to-verify>
1. Build/serve locally: `docker compose -f docker-compose.dev.yml up -d --build` (per project memory), then open the dashboard URL in a browser.
2. Desktop: confirm DeGiro view renders identically in structure — KPIs, allocation bar, charts, positions table, Indexa tab. Switch to Indexa tab; confirm colors/spacing match DeGiro (no jarring mismatch).
3. Functionality regression (critical): sort the positions table by clicking column headers; use the All/ETFs/Stocks filter tabs; click a row to expand detail; on Indexa, use the performance range buttons (All/5Y/1Y/6M/1M); toggle privacy mode. ALL must still work.
4. Responsiveness: resize to ~1024px, ~768px, and ~390px (mobile). Confirm KPI grids reflow cleanly with no page horizontal overflow; positions table mobile treatment behaves as chosen (smooth scroll with pinned name + scroll-shadow, OR stacked cards).
5. Accessibility: Tab through header buttons, tabs, filter tabs, and table headers — confirm a visible focus ring appears on each.
6. Micro-interactions: hover buttons/tabs/rows — confirm subtle, smooth transitions (no jank).
  </how-to-verify>
  <resume-signal>Type "approved" or describe issues to fix</resume-signal>
</task>

</tasks>

<verification>
- No app.js selector, id, class, data-* attribute, or colspan used for behavior was changed (unless card-layout chosen, where only `data-label` attributes were added to td cells — never altering count/order/classes).
- `style.css` has balanced braces and is valid (loads without console errors).
- KPI grids, charts, radar, winners/losers, positions table, and Indexa view all render and function exactly as before, with improved visuals.
- Focus-visible outlines present on all interactive elements; ARIA labels/roles added.
- No page-level horizontal scroll at 390px/768px/1024px.
</verification>

<success_criteria>
- Dashboard is visually polished and consistent across DeGiro and Indexa views.
- Responsive at mobile/tablet/desktop with no horizontal overflow and a usable positions table on mobile.
- Design tokens drive spacing, typography, and color; no stray literals or dead `--border` rules remain.
- All existing functionality (sort, filter, expand, range, privacy, tab switch, refresh) works unchanged.
- Accessibility improved: visible focus states, ARIA labels, better contrast, reduced-motion support.
- Human verification approved.
</success_criteria>

<output>
Create `.planning/quick/260528-wtv-do-a-comprehensive-ui-revamp-of-the-brok/260528-wtv-SUMMARY.md` when done.
</output>
