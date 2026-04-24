# Phase 05: Dashboard Polish - Context

**Gathered:** 2026-04-23 (assumptions mode)
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace browser `alert()` calls with toast notifications, improve error state handling with graceful degradation, and ensure the dashboard works on tablet (768px) and mobile (420px) viewports. Deliverables are DASH-01, DASH-02, DASH-03.

</domain>

<decisions>
## Implementation Decisions

### Toast Notifications (DASH-01)

- **D-01:** Toast library — use a lightweight custom implementation (no heavy dependency), inspired by common patterns: positioned top-right, auto-dismiss after 4 seconds, supports success/error/info variants
- **D-02:** Three alert calls in `app/static/app.js` need replacement:
  - Line 267: `alert("Error: " + err.message)` — network/fetch error
  - Line 794: `alert("Hermes context copied to clipboard!")` — clipboard success
  - Line 804: `alert("Export failed: " + err.message)` — export error
- **D-03:** Toasts should be non-blocking (no modal overlay), visually distinct from the loading overlay
- **D-04:** Stacking behavior — multiple toasts queue and dismiss sequentially, max 3 visible at once

### Error States (DASH-02)

- **D-05:** When API calls fail, show last valid data with a "stale" indicator (e.g., timestamp shows when data was last fetched, subtle warning badge)
- **D-06:** API failures should display a dismissible error toast (not blocking modal) with retry option
- **D-07:** Refresh button should be retry-friendly — user can tap again if a refresh fails midway
- **D-08:** Error state in the positions table: show "Failed to load positions" message with retry action, not blank table

### Responsive Design (DASH-03)

- **D-09:** Target viewports: 420px (mobile), 768px (tablet), 1024px+ (desktop)
- **D-10:** Mobile-first breakpoints:
  - Default: single column, summary cards stack vertically
  - 768px+: 2-column grid for summary cards, chart cards side-by-side
  - 1024px+: full layout with sidebar-free main content
- **D-11:** Positions table: horizontal scroll on mobile with sticky first column (Name), no column hiding
- **D-12:** Modal: full-width on mobile (100vw - 32px padding), centered card on desktop
- **D-13:** Font sizes: reduce card values and chart titles on mobile to fit narrower viewports

### Prior Decisions (from Phase 3)

- **D-14:** Health alerts are rendered in a dedicated "Health Alerts" section in the dashboard
- **D-15:** All environment variable configs use `os.getenv` with defaults — same pattern applies here if any new env vars are added (none anticipated for DASH)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Context
- `.planning/phases/01-security-hardening/01-CONTEXT.md` — Auth token pattern, env var conventions
- `.planning/phases/02-performance/02-CONTEXT.md` — Threading patterns, FX cache locking
- `.planning/phases/03-health-indicators/03-CONTEXT.md` — Alert format, health alerts rendering
- `.planning/ROADMAP.md` §Phase 5 — Phase goal, success criteria, implementation notes
- `.planning/REQUIREMENTS.md` §Dashboard (DASH) — DASH-01, DASH-02, DASH-03

### Codebase
- `app/static/app.js` — Contains the 3 `alert()` calls to replace (lines 267, 794, 804)
- `app/static/index.html` — Dashboard structure, modal HTML
- `app/static/style.css` — Existing styles to extend for toasts and responsive

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Existing modal overlay pattern in `style.css` — can inform toast positioning and animation
- `loading-overlay` div in index.html — similar dismiss pattern could apply to toasts
- Health alerts list rendering in `app.js` — alerts rendered via DOM manipulation, toasts could follow similar pattern
- Lucide icons already loaded via CDN (`data-lucide` attributes) — reuse for toast icons (info, check-circle, alert-circle)

### Established Patterns
- CSS class-based component pattern (`.toast`, `.toast-success`, `.toast-error`)
- Event-driven updates via DOM manipulation
- Fetch with try/catch and error display in UI

### Integration Points
- `app/static/app.js` `showError()` / `showSuccess()` functions — where toasts will be called
- `app/static/index.html` — toast container will be added near `</body>`
- `app/static/style.css` — toast styles extend existing CSS

</code_context>

<specifics>
## Specific Ideas

- "Toast should feel non-intrusive — don't block the user, just inform them"
- Mobile-first approach since that's the hardest constraint

</specifics>

<deferred>
## Deferred Ideas

None — all three DASH requirements are within scope for this phase.

</deferred>

---

*Phase: 05-dashboard-polish*
*Context gathered: 2026-04-23*