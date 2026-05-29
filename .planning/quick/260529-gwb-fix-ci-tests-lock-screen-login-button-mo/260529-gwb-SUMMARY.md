---
quick_id: 260529-gwb
phase: quick
plan: 260529-gwb
subsystem: tests, css
tags: [ci-fix, mobile, security, css]
key_files:
  modified:
    - tests/test_integration.py
    - tests/test_routes.py
    - app/static/style.css
decisions:
  - "Assert 303 -> /login for all no-cookie and expired-cookie cases on /api/session-token; never revert the app/main.py security fix"
  - "Use :not([aria-busy='true']) selector to keep login label visible on mobile while preserving spinner-loading behavior"
  - "margin-left: auto on #btn-privacy anchors privacy+lock to far right independent of DeGiro/Indexa button visibility"
metrics:
  duration: "~10 min"
  completed: "2026-05-29"
  tasks_completed: 2
  files_changed: 3
---

# Quick Task 260529-gwb Summary

**One-liner:** Fixed four stale CI test assertions from insecure 200 to secure 303-to-login, made the mobile lock-screen "Unlock" button visible, and anchored privacy/lock header controls to the right on mobile.

## Tasks Completed

### Task A — Update stale CI tests (commit: 5255f24)

Four tests were asserting the old insecure behavior (`status_code == 200`, "middleware-exempt") for `/api/session-token`. Commit `979fd56` (security fix) removed the endpoint from the auth-exempt list so it now correctly returns 303 for unauthenticated/expired requests. Updated:

- `TestUnauthorizedRedirect` — renamed `test_api_request_without_cookie_returns_200` -> `test_api_request_without_cookie_redirects_to_login`; asserts `303` + `location == "/login"`.
- `TestExpiredCookie` — updated class docstring; renamed `test_expired_cookie_returns_200` -> `test_expired_cookie_redirects_to_login`; updated `test_expired_cookie_does_not_grant_access` — both assert `303` + `location == "/login"`.
- `TestSessionTokenRoute::test_without_session_cookie_redirects_to_login` — body previously asserted `200`; now asserts `303` + `location == "/login"`.

`app/main.py` untouched (security fix preserved). Valid-cookie tests continue to assert 200.

**Full suite result:** 22 passed, 1 warning (targeted run). All full-suite runs exit 0.

### Task B — Mobile CSS fixes (commit: fe6a739)

Two scoped CSS changes in `app/static/style.css`, no template changes, no inline JS (CSP respected):

**Fix 1 — Login button invisible on mobile:** The global `@media (max-width: 768px)` and `@max-width: 420px` blocks set `.btn-label { display: none }`. The login submit button has only a `.spinner` + `.btn-label` ("Unlock") — no icon. This made the button render empty/invisible on mobile. Added:
```css
.login-submit:not([aria-busy="true"]) .btn-label { display: inline !important; }
```
Placed alongside the existing spinner/busy-state rules. The `aria-busy="true"` exclusion preserves the spinner animation during form submission.

**Fix 2 — Right-anchor privacy/lock buttons on mobile:** Added inside `@media (max-width: 768px)`:
```css
#btn-privacy { margin-left: auto; }
```
Also added `justify-content: flex-end` to the 768px `.header-right` rule (already present at 420px). Together these push `#btn-privacy` and the following `.lock-btn` to the far right edge of `.header-right` regardless of which DeGiro vs Indexa buttons are toggled visible. Desktop layout (`> 768px`) unchanged.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

- [x] `tests/test_integration.py` modified: 4 test assertions updated
- [x] `tests/test_routes.py` modified: 1 test assertion updated
- [x] `app/static/style.css` modified: login-label override + header right-anchor rules added
- [x] `app/main.py` unmodified (confirmed via `git diff`)
- [x] Commits 5255f24 and fe6a739 verified in git log
- [x] Full pytest suite: exit code 0 (all passes)

## Self-Check: PASSED
