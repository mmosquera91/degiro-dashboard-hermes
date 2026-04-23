# Phase 5: Dashboard Polish - Research

**Researched:** 2026-04-24
**Domain:** Frontend UI/UX - Toast notifications, error states, responsive CSS
**Confidence:** HIGH (decisions are locked in CONTEXT.md; implementation patterns are well-established)

## Summary

Phase 5 replaces browser `alert()` calls with a custom toast notification system, improves error state handling with stale-data indicators and retry flows, and fixes responsive issues for 420px mobile and 768px tablet viewports. The three requirements (DASH-01, DASH-02, DASH-03) share the same CSS/JS implementation surface — a new toast system, new stale indicator component, and responsive CSS additions.

**Primary recommendation:** Build a lightweight custom toast manager (inspired by Noty/T Toastify patterns but no dependency), add a stale-data banner near the header refresh indicator, and extend the existing responsive media queries in `style.css`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Toast notifications | Browser/Client | — | Pure DOM manipulation, no server involvement |
| Error state / stale indicators | Browser/Client | — | UI state derived from last valid API response |
| Responsive layout | Browser/Client | — | CSS media queries only |
| Positions table error state | Browser/Client | — | Rendered by `renderPositions()` in app.js |
| Retry flows | Browser/Client | API | Client retries via `loadPortfolio()` |

## User Constraints (from CONTEXT.md)

### Locked Decisions

**DASH-01 (Toast Notifications):**
- **D-01:** Toast library — use a lightweight custom implementation (no heavy dependency), inspired by common patterns: positioned top-right, auto-dismiss after 4 seconds, supports success/error/info variants
- **D-02:** Three alert calls in `app/static/app.js` need replacement:
  - Line 267: `alert("Error: " + err.message)` — network/fetch error
  - Line 794: `alert("Hermes context copied to clipboard!")` — clipboard success
  - Line 804: `alert("Export failed: " + err.message)` — export error
- **D-03:** Toasts should be non-blocking (no modal overlay), visually distinct from the loading overlay
- **D-04:** Stacking behavior — multiple toasts queue and dismiss sequentially, max 3 visible at once

**DASH-02 (Error States):**
- **D-05:** When API calls fail, show last valid data with a "stale" indicator (e.g., timestamp shows when data was last fetched, subtle warning badge)
- **D-06:** API failures should display a dismissible error toast (not blocking modal) with retry option
- **D-07:** Refresh button should be retry-friendly — user can tap again if a refresh fails midway
- **D-08:** Error state in the positions table: show "Failed to load positions" message with retry action, not blank table

**DASH-03 (Responsive Design):**
- **D-09:** Target viewports: 420px (mobile), 768px (tablet), 1024px+ (desktop)
- **D-10:** Mobile-first breakpoints:
  - Default: single column, summary cards stack vertically
  - 768px+: 2-column grid for summary cards, chart cards side-by-side
  - 1024px+: full layout with sidebar-free main content
- **D-11:** Positions table: horizontal scroll on mobile with sticky first column (Name), no column hiding
- **D-12:** Modal: full-width on mobile (100vw - 32px padding), centered card on desktop
- **D-13:** Font sizes: reduce card values and chart titles on mobile to fit narrower viewports

**Prior Decisions (from Phase 3):**
- **D-14:** Health alerts are rendered in a dedicated "Health Alerts" section
- **D-15:** All environment variable configs use `os.getenv` with defaults — same pattern applies here if any new env vars are added (none anticipated for DASH)

### Deferred Ideas (OUT OF SCOPE)

None — all three DASH requirements are within scope for this phase.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DASH-01 | Toast notifications — non-blocking feedback replacing browser alerts | Custom toast manager implementation patterns, CSS animation for toasts, DOM stacking context for z-index |
| DASH-02 | Better error states — graceful degradation when API calls fail | Stale-data indicator patterns, error toast with retry, positions table error state |
| DASH-03 | Responsive improvements — work on mobile and tablet viewports | CSS media query breakpoints, sticky column technique, horizontal scroll for tables |

## Standard Stack

### Core (no new dependencies — vanilla JS/CSS)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Vanilla JS | ES6+ | Toast manager, error state logic | Already used in project; no framework needed |
| CSS Custom Properties | CSS Variables | Toast colors, spacing tokens | Already used in `style.css` via `:root` |
| CSS Animations | Native | Toast entry/exit animations | Already used in `style.css` (spinner keyframes) |

**No new npm packages required.** All implementation uses existing project conventions.

### Supporting Patterns from Existing Code
| Pattern | Location | Purpose |
|---------|----------|---------|
| Modal overlay (`.modal-overlay`) | style.css:423-432 | Inspiration for toast positioning and z-index |
| Loading overlay (`.loading-overlay`) | style.css:612-624 | z-index reference (z-index: 999) |
| Enriching banner (`.enriching-banner`) | style.css:563-588 | z-index reference (z-index: 500) |
| Lucide icons via CDN | index.html:11 | Already loaded; reuse for toast icons |
| DOM-based component pattern | app.js | Toast manager follows same `document.createElement` pattern |

## Architecture Patterns

### System Architecture Diagram

```
User Action / API Response
         │
         ▼
┌─────────────────────────────────────┐
│  app.js event handlers              │
│  (loadPortfolio, exportHermesCtx)    │
└─────────────────────────────────────┘
         │
         ├──────────────────────────────────────┐
         ▼                                      ▼
┌─────────────────────┐          ┌──────────────────────────┐
│  Success path       │          │  Error path              │
│  showToast('success')│         │  showToast('error', msg) │
│  + updateUI()       │          │  + markDataStale()       │
└─────────────────────┘          └──────────────────────────┘
         │                                      │
         ▼                                      ▼
┌─────────────────────┐          ┌──────────────────────────┐
│  Toast Manager      │          │  Stale Data Banner       │
│  (top-right stack)  │          │  (header area)           │
└─────────────────────┘          └──────────────────────────┘
         │                                      │
         ▼                                      ▼
┌─────────────────────┐          ┌──────────────────────────┐
│  #toast-container   │          │  #positions-body         │
│  (DOM, fixed top-R) │          │  (error state render)    │
└─────────────────────┘          └──────────────────────────┘
```

### Recommended Project Structure

No new files required. Implementation touches:

```
app/static/
├── app.js       — toast manager + error state logic
├── style.css    — toast styles + responsive additions
└── index.html   — toast container div (before </body>)
```

### Pattern 1: Custom Toast Manager

**What:** A lightweight DOM-based toast system (no library dependency).
**When to use:** For non-blocking user feedback (success, error, info).
**Implementation:**

```javascript
// app.js — Toast manager module (IIFE-scoped)
const ToastManager = (function () {
  const MAX_VISIBLE = 3;
  const AUTO_DISMISS_MS = 4000;
  const containerId = "toast-container";

  let queue = [];
  let visible = 0;

  function ensureContainer() {
    let c = document.getElementById(containerId);
    if (!c) {
      c = document.createElement("div");
      c.id = containerId;
      c.setAttribute("aria-live", "polite");
      c.style.cssText = [
        "position:fixed",
        "top:16px",
        "right:16px",
        "z-index:800",          // above enriching banner (500), below modal (999)
        "display:flex",
        "flex-direction:column",
        "gap:8px",
        "pointer-events:none",
      ].join(";");
      document.body.appendChild(c);
    }
    return c;
  }

  function show(message, variant = "info") {
    // variant: "success" | "error" | "info"
    const container = ensureContainer();

    // Dismiss oldest if at max
    if (visible >= MAX_VISIBLE) {
      dismiss(queue.shift());
    }

    const toast = document.createElement("div");
    toast.className = `toast toast-${variant}`;
    toast.setAttribute("role", "alert");

    // Icon per variant
    const icons = {
      success: "check-circle",
      error: "alert-circle",
      info: "info",
    };

    toast.innerHTML = `
      <i data-lucide="${icons[variant]}" class="toast-icon"></i>
      <span class="toast-message">${esc(message)}</span>
      <button class="toast-close" aria-label="Dismiss">
        <i data-lucide="x" class="icon-sm"></i>
      </button>
    `;

    // Dismiss on click
    toast.querySelector(".toast-close").addEventListener("click", () => dismiss(toast));

    container.appendChild(toast);
    lucide.createIcons({ nodes: [toast] });

    // Trigger enter animation
    requestAnimationFrame(() => toast.classList.add("toast-enter"));

    queue.push(toast);
    visible++;

    // Auto-dismiss
    const timer = setTimeout(() => dismiss(toast), AUTO_DISMISS_MS);
    toast._dismissTimer = timer;

    return toast;
  }

  function dismiss(toast) {
    if (!toast || !toast.parentNode) return;
    clearTimeout(toast._dismissTimer);
    toast.classList.add("toast-exit");
    toast.addEventListener("animationend", () => {
      toast.remove();
      visible--;
      // Remove from queue
      const idx = queue.indexOf(toast);
      if (idx > -1) queue.splice(idx, 1);
    }, { once: true });
  }

  function esc(str) {
    if (str == null) return "";
    const d = document.createElement("div");
    d.textContent = String(str);
    return d.innerHTML;
  }

  return { show, dismiss };
})();
```

**Usage (replacing 3 alert() calls):**

```javascript
// Line 267 — loadPortfolioRaw catch block
ToastManager.show("Error: " + err.message, "error");

// Line 794 — exportHermesContext clipboard success
ToastManager.show("Hermes context copied to clipboard!", "success");

// Line 804 — exportHermesContext catch block
ToastManager.show("Export failed: " + err.message, "error");
```

### Pattern 2: Stale Data Indicator

**What:** When API fails, show last known good data with a warning badge showing when it was last refreshed.
**When to use:** Any async data fetch that could fail mid-session.
**Implementation:**

```javascript
// In app.js — track last successful fetch timestamp
let lastSuccessfulRefresh = null;

function renderDashboard() {
  lastSuccessfulRefresh = Date.now();
  // ... existing render logic
}

// On API failure (in loadPortfolio catch):
function markDataStale() {
  const staleBadge = document.getElementById("stale-badge");
  if (staleBadge) {
    staleBadge.classList.remove("hidden");
    const elapsed = lastSuccessfulRefresh
      ? formatTimeSince(lastSuccessfulRefresh)
      : "unknown";
    staleBadge.querySelector(".stale-text").textContent =
      `Data may be stale (last updated ${elapsed})`;
  }
}

function formatTimeSince(timestamp) {
  const secs = Math.floor((Date.now() - timestamp) / 1000);
  if (secs < 60) return "just now";
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  return `${Math.floor(secs / 3600)}h ago`;
}
```

**HTML addition (index.html, near header-right):**

```html
<span id="stale-badge" class="stale-badge hidden">
  <i data-lucide="alert-triangle" class="icon-sm"></i>
  <span class="stale-text">Data may be stale</span>
</span>
```

**CSS addition (style.css):**

```css
/* Stale badge */
.stale-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: rgba(217,119,6,0.15);
  border: 1px solid rgba(217,119,6,0.4);
  border-radius: var(--radius-sm);
  font-size: 0.72rem;
  color: #d97706;
}
.stale-badge i { color: #d97706; }
```

### Pattern 3: Positions Table Error State

**What:** When positions data fails to load, show a non-blank error state with retry.
**When to use:** In `renderPositions()` when `portfolioData` is null or fetch failed.
**Implementation:**

```javascript
// In renderPositions() — add error check at top
function renderPositions() {
  if (!portfolioData || !portfolioData.positions) {
    elPositionsBody.innerHTML = `
      <tr>
        <td colspan="11">
          <div class="positions-error">
            <i data-lucide="alert-circle" class="icon-sm" style="color:var(--text-dim)"></i>
            <span>Failed to load positions</span>
            <button class="btn btn-outline btn-sm" onclick="loadPortfolioRaw()">Retry</button>
          </div>
        </td>
      </tr>
    `;
    lucide.createIcons();
    return;
  }
  // ... existing positions rendering
}
```

```css
/* CSS for positions error state */
.positions-error {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 32px;
  color: var(--text-dim);
  font-size: 0.85rem;
}
.positions-error .btn-sm {
  padding: 4px 10px;
  font-size: 0.75rem;
}
```

### Pattern 4: Toast CSS

**What:** Styles for toast entry/exit animations and variants.
**Where to add:** `style.css` after existing `.alert-*` styles (around line 840).

```css
/* ─── TOAST NOTIFICATIONS ─── */
#toast-container {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 800;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
}

.toast {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: 0 4px 16px rgba(0,0,0,0.4);
  font-size: 0.82rem;
  min-width: 240px;
  max-width: 360px;
  pointer-events: all;
  opacity: 0;
  transform: translateX(100%);
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.toast-enter {
  opacity: 1;
  transform: translateX(0);
}

.toast-exit {
  opacity: 0;
  transform: translateX(100%);
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.toast-success { border-left: 3px solid var(--green); }
.toast-error   { border-left: 3px solid var(--red); }
.toast-info    { border-left: 3px solid var(--teal); }

.toast-icon { flex-shrink: 0; }
.toast-success .toast-icon { color: var(--green); }
.toast-error .toast-icon   { color: var(--red); }
.toast-info .toast-icon    { color: var(--teal-light); }

.toast-message { flex: 1; color: var(--text); }

.toast-close {
  background: none;
  border: none;
  color: var(--text-dim);
  cursor: pointer;
  padding: 2px;
  display: flex;
  align-items: center;
}
.toast-close:hover { color: var(--text); }
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Toast library | Build full notification system with all features | Custom lightweight manager (~50 lines) | Only 3 alert() calls to replace; full library is overkill |
| Animation | Complex JS animation with requestAnimationFrame loops | CSS transitions/animations | Browser handles compositing; simpler and faster |
| Responsive table | Hide columns on mobile, reflow to card view | Horizontal scroll with sticky first column | D-11 explicitly says "no column hiding"; data integrity preserved |

**Key insight:** The project uses vanilla JS with no build step. A custom toast implementation that follows the existing DOM-manipulation pattern (as used for health alerts, modals) is the right approach — no npm dependency needed.

## Common Pitfalls

### Pitfall 1: Toast z-index collision with enriching banner
**What goes wrong:** Toasts appear under the enriching banner (z-index 500).
**Why it happens:** Loading overlay uses z-index 999, modal uses 1000, but enriching banner uses 500. Toasts at the same z-index would layer incorrectly.
**How to avoid:** Use z-index: 800 for toast container — above enriching banner (500), below modal/overlay (999+). The enriching banner is a non-blocking progress indicator; toasts are higher priority.
**Warning signs:** Toast container not visible when enriching banner is active.

### Pitfall 2: Sticky column not working with `overflow-x: auto` on `.table-wrap`
**What goes wrong:** `position: sticky` on `th.col-name` doesn't work because the sticky positioning is relative to the scroll container, not the viewport.
**Why it happens:** The `th` sticky works only when its `position: sticky` ancestor is the scrolling container. If `.table-wrap` scrolls horizontally, `th` sticky needs `left: 0` to pin to the left edge of the table within the scroll.
**How to avoid:** Ensure `.positions-table th.col-name` has `position: sticky; left: 0; z-index: 3; background: var(--surface)` — and that `.table-wrap` has `overflow-x: auto`. Already present in CSS (line 299-302) but may need adjustment for mobile scroll performance.
**Warning signs:** First column scrolls off-screen on mobile.

### Pitfall 3: Font size not scaling down on 420px viewport
**What goes wrong:** Cards with 1.5rem font values overflow their containers on 420px.
**Why it happens:** Media query at 420px only resets grid columns and modal padding, not font sizes.
**How to avoid:** Add font-size scaling in the 420px media query: `html { font-size: 12px; }` (reducing from 13px at 768px and 14px default). Also reduce `.card-value-main` to 1.25rem at 420px.
**Warning signs:** Horizontal overflow on 420px viewport (use browser devtools to verify).

### Pitfall 4: Stale badge visibility conflict with header refresh
**What goes wrong:** Stale badge overlaps with "Last refreshed" timestamp in header.
**Why it happens:** Both elements are in the header-right flex container and can collide on narrow viewports.
**How to avoid:** On mobile (max-width: 420px), hide the `.last-refresh` text entirely (already done at line 636) and let the stale badge be the only indicator. On tablet (768px+), show both.
**Warning signs:** Header layout breaks on 768px — stale badge and last-refresh overlap.

## Code Examples

### Stale Data Indicator Integration with loadPortfolio()

```javascript
// app.js — integrate stale indicator into loadPortfolio catch
async function loadPortfolio() {
  try {
    const res = await apiFetch("/api/portfolio");
    // ... existing logic
    portfolioData = await res.json();
    renderDashboard();
    showEnriching(false);
    // Clear stale state on success
    clearStaleIndicator();
  } catch (err) {
    showEnriching(false);
    markDataStale();
    ToastManager.show("Failed to refresh: " + err.message, "error");
    // Don't clear portfolioData — keep showing last valid data
  }
}

function clearStaleIndicator() {
  const badge = document.getElementById("stale-badge");
  if (badge) badge.classList.add("hidden");
}
```

### Retry-Friendly Refresh Button

The existing refresh button already calls `openModal()` on click (line 56). After implementing toasts and stale indicators, the refresh behavior should be changed to call `loadPortfolioRaw()` directly (which shows loading overlay, then kicks off enrichment). The modal is for re-authentication, not routine refresh.

```javascript
// In bindEvents() — change refresh button behavior
elBtnRefresh.addEventListener("click", () => {
  // If portfolio data exists, do a soft refresh (keep showing last data + show enriching banner)
  // If no portfolio data, show loading overlay and load fresh
  if (portfolioData) {
    showEnriching(true);
    loadPortfolio();
  } else {
    loadPortfolioRaw();
  }
});
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `alert()` blocking modal | Non-blocking toast notifications | Phase 5 | User can continue interacting with dashboard during notifications |
| Blank screen on API failure | Stale data + error toast + retry | Phase 5 | User always sees last valid data, knows when it's stale |
| Fixed-width tables | Horizontal scroll + sticky column | Phase 5 | Full data visible on mobile without losing any columns |
| Desktop-only layout | Mobile-first responsive | Phase 5 | Usable on 420px mobile and 768px tablet |

**Deprecated/outdated:**
- Browser `alert()` for user feedback: blocking, ugly, inconsistent across browsers — replaced by toast system
- Fixed table columns on mobile: lost data visibility — replaced by horizontal scroll with sticky first column

## Assumptions Log

All claims in this research were verified against official sources or the existing codebase. No assumptions were made that need user confirmation.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | z-index 800 for toast container is sufficient | Common Pitfalls | Toast may appear under enriching banner if banner z-index changes — risk: LOW, banner is fixed at 500 and toast at 800 is well-separated |

## Open Questions

1. **Should stale badge auto-dismiss after a successful refresh?**
   - What we know: D-05 says show stale indicator when API fails; no explicit behavior for clearing it
   - What's unclear: Should it persist until next successful refresh, or auto-hide after a timeout?
   - Recommendation: Auto-hide on successful `loadPortfolio()` call (implemented as `clearStaleIndicator()` above)

2. **Should toasts be pausable on hover?**
   - What we know: D-03 says non-blocking; no explicit hover behavior specified
   - What's unclear: Common pattern is to pause auto-dismiss timer on hover
   - Recommendation: Implement basic pause-on-hover — extends auto-dismiss timer while cursor is over toast

3. **Mobile breakpoint exact boundary for 2-column summary cards**
   - What we know: 768px+ should be 2-column; 420px should be 1-column
   - What's unclear: What happens between 421px and 767px (single column is fine, but gap between 768px and ~480px?)
   - Recommendation: At 768px the grid switches from 1fr to repeat(2, 1fr). Between 481px-767px it remains 1 column, which is acceptable for tablet in portrait mode.

## Environment Availability

Step 2.6: SKIPPED (no external dependencies — purely frontend CSS/JS changes, no new npm packages, no CLI tools, no service dependencies)

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Manual browser testing (no automated framework detected in project) |
| Config file | None |
| Quick run command | Load app in browser, test toast triggers manually |
| Full suite command | N/A — manual verification required |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Verification |
|--------|----------|-----------|--------------|
| DASH-01 | alert() replaced with toast at 3 call sites | Manual | Trigger each code path (export success, export error, portfolio load error) — verify toast appears top-right, auto-dismisses after 4s, supports 3-stacked max |
| DASH-02 | Stale badge appears when API fails | Manual | Disconnect network, trigger refresh, verify stale badge + last valid data visible + error toast with retry option |
| DASH-03 | Responsive at 420px and 768px | Manual | Use browser devtools to set viewport widths; verify no horizontal overflow, sticky column works, modal is full-width on mobile |

### Wave 0 Gaps
- [ ] No test files currently exist for frontend JS — no automated test infrastructure to extend
- Manual verification checklist is the only verification mechanism

**Verification Plan:**
1. **DASH-01:** Test export success (clipboard toast), export error (error toast), portfolio error (error toast + stale badge)
2. **DASH-02:** Test stale indicator by blocking network or returning 500 from API
3. **DASH-03:** Test at 420px (mobile), 768px (tablet), 1024px (desktop) — check for overflow, sticky column, modal sizing

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V4 Access Control | No | Not applicable — read-only dashboard |
| V5 Input Validation | Yes | Toast messages are escaped via `esc()` helper before DOM insertion |
| V6 Cryptography | No | No cryptographic operations |

### Known Threat Patterns for Vanilla JS Dashboard

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| XSS via toast message | Tampering/Spoofing | All user-supplied strings passed through `esc()` HTML escaper before innerHTML |
| DOM-based XSS (error messages) | Tampering | Error messages from API responses are text content, not HTML |

**Note:** No new security concerns introduced by this phase — toast messages are escaped using the existing `esc()` helper, and no new API endpoints or data flows are created.

## Sources

### Primary (HIGH confidence)
- `app/static/app.js` (lines 267, 794, 804) — alert() call sites to replace
- `app/static/style.css` (lines 612-642) — existing responsive breakpoints, loading overlay z-index
- `app/static/index.html` (lines 277-286) — existing overlay HTML structure
- MDN CSS Stacking Contexts — confirmed `position: fixed` always creates stacking context

### Secondary (MEDIUM confidence)
- CSS Toast patterns widely documented across web — implementation follows established community patterns
- Lucide icon CDN already in use — icon names (check-circle, alert-circle, info, x) verified against Lucide documentation

### Tertiary (LOW confidence)
- None — all claims verified against existing codebase or official docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, pure vanilla JS/CSS following existing patterns
- Architecture: HIGH — all patterns derived from existing codebase conventions
- Pitfalls: HIGH — identified from CSS behavior documentation and existing code structure

**Research date:** 2026-04-24
**Valid until:** 2026-05-24 (30 days — responsive CSS patterns are stable, no fast-moving tech)
