---
phase: quick-260529-eqt
plan: 01
subsystem: frontend/login
tags: [login, lock-screen, design-system, accessibility, responsive]
dependency_graph:
  requires: []
  provides: [QUICK-LOCKSCREEN-REVAMP]
  affects: [app/templates/login.html, app/static/style.css]
tech_stack:
  added: []
  patterns: [design-token-driven CSS, canonical btn/spinner reuse, ARIA live region]
key_files:
  created: []
  modified:
    - app/static/style.css
    - app/templates/login.html
decisions:
  - "Use .login-* namespace to scope lock-screen styles without polluting shared classes"
  - "Reuse canonical .btn .btn-primary .btn-block rather than duplicating button styles"
  - "aria-busy + disabled on submit button triggers canonical .spinner via CSS attribute selector"
metrics:
  duration: "~5 min"
  completed: "2026-05-29T08:41:46Z"
  tasks_completed: 2
  tasks_total: 2
---

# Phase quick-260529-eqt Plan 01: Lock-Screen Revamp Summary

**One-liner:** Lock/login screen redesigned with canonical design-system tokens, real Brokr SVG wordmark, .btn-primary unlock button with spinner, ARIA-announced error, and responsive centered card matching dashboard visual language.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Add login/lock-screen component styles to canonical stylesheet | ac94932 | app/static/style.css |
| 2 | Rewrite login.html to use canonical stylesheet, logo, and component classes | 53c75ef | app/templates/login.html |

## What Was Built

**Task 1 — `app/static/style.css`**

Appended a `/* ─── LOGIN / LOCK SCREEN ─── */` section (98 lines) using only the existing design tokens already defined in `:root`. Classes defined:

- `.login-body` — full-viewport flex centering with `var(--bg)` background
- `.login-card` — `var(--surface)` panel with `var(--radius-lg)`, `var(--shadow-md)`, max-width 360px
- `.login-logo-row` — flex-centered logo mount, `var(--space-6)` bottom margin
- `.login-logo` — 64px height, auto width
- `.login-form-group` / `.login-label` / `.login-input` — form field using `var(--text-sm)`, `var(--text-dim)`, `var(--text-md)`, `var(--bg)`, `var(--border)`, `var(--teal)` focus border
- `.login-error` / `.login-error.visible` — `var(--red-dim)` background, `var(--red)` text, `display:none` toggled to `display:block`
- `.login-submit` loading affordance — `.spinner { display:none }` default; `[aria-busy="true"] .spinner { display:inline-block }` + `[aria-busy="true"] .btn-label { display:none }` to reuse the canonical `@keyframes spin` spinner during POST navigation
- `@media (max-width:480px)` — `.login-card` padding tightened to `var(--space-6) var(--space-5)`

No token, keyframe, `.btn*`, `.spinner`, or `:focus-visible` duplication introduced.

**Task 2 — `app/templates/login.html`**

Replaced the 105-line hand-rolled inline `<style>` block and one-off inline SVG with references to the shared design system:

- `<head>`: Links Inter font (preconnect + stylesheet), `/static/style.css`, `/static/favicon.ico`; no inline style block
- `<body class="login-body">`: activates full-viewport centering
- Logo: `<img src="/static/logo.svg" alt="Brokr" class="login-logo">` — real "Brokr / PORTFOLIO INTELLIGENCE" teal wordmark
- Error: `<div id="error-msg" class="login-error ... " role="alert" aria-live="assertive">{{ (error or "Incorrect password") | e }}</div>` — ARIA-announced, Jinja autoescaped
- Password field: `class="login-input"`, `autocomplete="current-password"`, `aria-describedby="error-msg"`, `autofocus`, `required`
- Submit: `<button class="btn btn-primary btn-block login-submit">` with `<span class="spinner" aria-hidden="true">` + `<span class="btn-label">Unlock</span>`
- JS: preserved `failedattempt=yes` param handler; added `submit` event listener that sets `aria-busy="true"` and `disabled` on the button (native POST proceeds, spinner shows during navigation)

Server contracts unchanged: `method="POST" action="/login"`, `name="password"`, `{{ (error or "Incorrect password") | e }}`, `{% if error %}visible{% endif %}` class toggle.

## Deviations from Plan

None — plan executed exactly as written.

## Human Verification Required

The checkpoint task (Task 3) requires visual and functional verification. Instructions:

1. Rebuild/restart the app with the dev compose file:
   ```
   docker compose -f docker-compose.dev.yml up -d --build
   ```
   (or restart just the app service if CSS/HTML changes don't require a full rebuild)

2. Visit `/login` in a browser (private/incognito window to ensure you are logged out).

3. **Visual parity check:** Confirm the page shows the same dark `#0f0f0f` background, Inter font, teal accents, and the "Brokr / PORTFOLIO INTELLIGENCE" SVG wordmark (not the old inline geometric icon + "Brokr" text).

4. **Keyboard accessibility:** Tab through — the password field and Unlock button should show the teal `:focus-visible` outline ring (2px teal, 2px offset).

5. **Error state:** Enter a wrong password and submit — the Unlock button should briefly show the spinner (white rotating arc), then the page returns showing the styled red error box ("Incorrect password").

6. **Correct password:** Confirm it unlocks and lands on the dashboard.

7. **Responsive:** Narrow the browser to phone width (~375px) — the card should stay centered and its padding should tighten.

## Known Stubs

None — all styling is wired to the canonical design system.

## Threat Flags

None — no new trust boundaries introduced. XSS mitigation (T-eqt-01) preserved via `{{ (error or "Incorrect password") | e }}` Jinja autoescaping; no `| safe` or `innerHTML` injection added.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| app/static/style.css | FOUND |
| app/templates/login.html | FOUND |
| 260529-eqt-SUMMARY.md | FOUND |
| Commit ac94932 (style.css) | FOUND |
| Commit 53c75ef (login.html) | FOUND |
