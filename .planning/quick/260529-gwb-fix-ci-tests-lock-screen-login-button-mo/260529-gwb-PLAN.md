---
quick_id: 260529-gwb
type: execute
wave: 1
autonomous: true
files_modified:
  - tests/test_integration.py
  - tests/test_routes.py
  - app/static/style.css
must_haves:
  truths:
    - "Full local pytest suite passes (no stale assertions of old insecure behavior)"
    - "Unauthenticated/expired requests to /api/session-token are asserted to return 303 -> /login"
    - "The lock/login screen 'Unlock' submit button is visible on mobile viewports"
    - "On mobile, the privacy-mode toggle and lock-portfolio button are anchored to the right of the header"
    - "Desktop layout is unchanged"
  artifacts:
    - path: "tests/test_integration.py"
      provides: "Updated TestUnauthorizedRedirect + TestExpiredCookie asserting secure 303 behavior"
    - path: "tests/test_routes.py"
      provides: "Updated TestSessionTokenRoute::test_without_session_cookie_redirects_to_login asserting 303"
    - path: "app/static/style.css"
      provides: "Mobile-visible login submit label + right-anchored header controls"
  key_links:
    - from: "tests/*"
      to: "app/main.py check_session_cookie middleware"
      via: "assertions on /api/session-token status code"
      pattern: "status_code == 303"
    - from: "app/static/style.css .login-submit .btn-label"
      to: "global mobile .btn-label { display: none }"
      via: "override keeping login label visible"
      pattern: "login-submit .btn-label"
---

<objective>
Fix three issues in one focused quick task:

1. CI test failures — four tests still assert the OLD insecure behavior of `/api/session-token` (200, "middleware-exempt"). Commit 979fd56 intentionally removed that endpoint from the auth-exempt list (security fix: it leaked BROKR_AUTH_TOKEN to unauthenticated callers). The endpoint now correctly returns 303 -> /login for unauthenticated/expired requests. Update the stale tests to assert the NEW secure behavior. DO NOT revert the security fix in app/main.py.

2. Mobile lock/login screen: the "Unlock" submit button is invisible on mobile. Root cause confirmed: the button (app/templates/login.html lines 37-39) has only a `.spinner` + `.btn-label` ("Unlock") and NO icon. The global mobile media queries (style.css line 997 `@max-width:768px` and line 1042 `@max-width:420px`) set `.btn-label { display: none; }` to hide dashboard button text (those buttons keep their icons). With the label hidden and no icon, the login button renders empty/invisible. Fix: keep the login submit label visible at all viewports.

3. Mobile header: anchor the privacy-mode toggle (`#btn-privacy`) and lock-portfolio button (`.lock-btn`) to the right on mobile. They are the last two children of `.header-right`; ensure they reliably sit at the far right regardless of which other header buttons are shown (the DeGiro vs Indexa views toggle different buttons).

Purpose: Green CI + correct mobile UX on the lock screen and dashboard header.
Output: Updated test assertions and scoped CSS overrides; full pytest suite green.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@./CLAUDE.md
@.planning/STATE.md

<interfaces>
<!-- Confirmed current behavior — executor should NOT re-diagnose. -->

app/main.py check_session_cookie middleware (lines 556-580):
  - Exempt paths: /login, /static/*, /health, /logout, /api/hermes-context, /api/indexa/*
  - /api/session-token is NOT exempt (security fix 979fd56).
  - No cookie -> RedirectResponse("/login", status_code=303)
  - Invalid/expired cookie -> 303 -> /login (also deletes cookie)

Test command (this environment has `python3`, not `python`):
  python3 -m pytest

Login button markup (app/templates/login.html lines 37-39):
  <button type="submit" class="btn btn-primary btn-block login-submit">
    <span class="spinner" aria-hidden="true"></span><span class="btn-label">Unlock</span>
  </button>

Header controls markup (app/index.html lines 48-56):
  <button id="btn-privacy" ...><i data-lucide="eye" .../></button>
  <a href="/logout" class="lock-btn" ...><svg.../></a>
  Both are the last two children of <div class="header-right">.

style.css relevant rules:
  - line 135 .header-right { display:flex; align-items:center; gap:10px; }
  - line 997 (inside @max-width:768px) .btn-label { display: none; }
  - line 1042 (inside @max-width:420px) .btn-label { display: none; }
  - line 985 (inside @max-width:768px) .header-right { gap: 6px; flex: 0 0 auto; }
  - line 1040 (inside @max-width:420px) .header-right { flex: 0 0 auto; justify-content: flex-end; gap: var(--space-1); }
  - login styles start at line 1487; existing @max-width:480px login override at line 1579.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task A: Update stale CI tests to assert secure /api/session-token behavior</name>
  <files>tests/test_integration.py, tests/test_routes.py</files>
  <action>
Update four tests to assert the NEW secure behavior (303 redirect to /login) for unauthenticated/expired requests to /api/session-token. Read the files first to confirm exact current line numbers (they may have shifted). Use follow_redirects=False so the 303 is observable.

In tests/test_integration.py:
- TestUnauthorizedRedirect (class around line 83): update the class docstring — /api/session-token is NO LONGER middleware-exempt. In test_api_request_without_cookie_returns_200 (around line 86): rename to test_api_request_without_cookie_redirects_to_login, update docstring, and assert response.status_code == 303 and response.headers["location"] == "/login".
- TestExpiredCookie (class around line 119): update class docstring (expired cookie now redirects). In test_expired_cookie_returns_200 (around line 122): rename to test_expired_cookie_redirects_to_login, update docstring, assert status_code == 303 and location == "/login". In test_expired_cookie_does_not_grant_access (around line 137): keep the intent (expired cookie grants no access) but assert status_code == 303 (redirect, not 200), and update docstring/inline comment accordingly.

In tests/test_routes.py:
- TestSessionTokenRoute::test_without_session_cookie_redirects_to_login (around line 177): the test name already says "redirects_to_login" but the body asserts 200. Update the docstring to reflect ROUTES-10 secure behavior and assert status_code == 303 and location == "/login".

Do NOT modify app/main.py. Do NOT touch tests that legitimately use a valid cookie (those still expect 200 — e.g. test_session_token_with_valid_cookie_returns_token, test_middleware_passes_valid_cookie_to_route, test_with_valid_session_cookie_returns_token). Only the no-cookie / expired-cookie cases change.
  </action>
  <verify>
    <automated>python3 -m pytest tests/test_integration.py tests/test_routes.py -q 2>&1 | tail -5</automated>
  </verify>
  <done>tests/test_integration.py and tests/test_routes.py pass; the four updated tests assert 303 -> /login; no app/main.py changes; renamed tests have matching docstrings.</done>
</task>

<task type="auto">
  <name>Task B: Fix mobile lock-screen button visibility + right-anchor header controls (CSS only)</name>
  <files>app/static/style.css</files>
  <action>
Two scoped CSS changes. No inline JS, no inline styles in templates (respect strict CSP). Edit only app/static/style.css.

Fix 1 (Task 2 — login button invisible on mobile): The login submit button has no icon, so the global mobile `.btn-label { display: none; }` rules (lines ~997 and ~1042) hide its only visible content. Add an override so the login submit label always shows. In the LOGIN section (near the existing `.login-submit` rules around lines 1566-1577, or inside/after the existing `@media (max-width: 480px)` login block at line ~1579), add a rule with sufficient specificity to beat the bare `.btn-label` selector:
  .login-submit .btn-label { display: inline !important; }
Use `!important` because the global `.btn-label { display: none }` lives inside media queries and the override must win at all widths. Keep the existing aria-busy spinner behavior intact (when aria-busy="true" the label SHOULD hide and spinner show — that override at line ~1571 must still take effect, so do NOT force the label visible when aria-busy is true). Scope the always-visible rule to the non-busy state, e.g.:
  .login-submit:not([aria-busy="true"]) .btn-label { display: inline !important; }
This ensures the "Unlock" text is visible on mobile and still hides during the loading state.

Fix 2 (Task 3 — anchor privacy + lock buttons to the right on mobile): `.header` is `justify-content: space-between` and `.header-right` already right-aligns on mobile, but ensure `#btn-privacy` and `.lock-btn` sit at the far right of the row independent of which other (degiro-only / indexa-only) buttons are visible. Inside the existing `@media (max-width: 768px)` block (around lines 980-1004) add:
  #btn-privacy { margin-left: auto; }
This pushes the privacy toggle (and the lock-btn that follows it) to the far right edge of `.header-right`. Also confirm/keep `.header-right { justify-content: flex-end; }` for mobile — it is already present at line ~1040 for 420px; add `justify-content: flex-end;` to the 768px `.header-right` rule at line ~985 if not already effective. Do NOT change the desktop (`> 768px`) layout. Keep changes inside existing mobile media queries so desktop is untouched.
  </action>
  <verify>
    <automated>grep -v '^[[:space:]]*/\*' app/static/style.css | grep -c 'login-submit:not(\[aria-busy="true"\]) .btn-label' | grep -qx 1 && grep -c 'margin-left: auto' app/static/style.css | grep -q '[1-9]' && echo OK</automated>
  </verify>
  <done>style.css contains a `.login-submit:not([aria-busy="true"]) .btn-label { display: inline !important; }` rule and a `#btn-privacy { margin-left: auto; }` rule inside the 768px mobile media query; the aria-busy spinner toggle still hides the label during loading; desktop rules unchanged.</done>
</task>

</tasks>

<verification>
Full suite green and CSS overrides present:

```
python3 -m pytest -q 2>&1 | tail -5
```

Manual structural check (no browser required): confirm style.css has the login-label override and the `#btn-privacy { margin-left: auto; }` inside `@media (max-width: 768px)`. Confirm app/main.py is unmodified (`git diff --stat app/main.py` shows nothing).
</verification>

<success_criteria>
- `python3 -m pytest` passes the full suite (0 failures).
- The four /api/session-token tests assert 303 -> /login for no-cookie / expired-cookie cases; valid-cookie tests still assert 200.
- app/main.py is unchanged (security fix preserved).
- style.css keeps the login "Unlock" label visible on mobile (except during aria-busy loading) and anchors `#btn-privacy` + `.lock-btn` to the right on mobile, with desktop layout untouched.
- No new inline JS or inline template styles introduced (CSP respected).
</success_criteria>

<output>
Create `.planning/quick/260529-gwb-fix-ci-tests-lock-screen-login-button-mo/260529-gwb-SUMMARY.md` when done.

Suggested commits (atomic):
1. `fix(260529-gwb): update stale /api/session-token tests to assert secure 303 redirect`
2. `fix(260529-gwb): make lock-screen login button visible and right-anchor header controls on mobile`
</output>
