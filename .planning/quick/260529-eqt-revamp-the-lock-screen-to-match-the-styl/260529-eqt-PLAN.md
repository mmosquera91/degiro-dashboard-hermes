---
phase: quick-260529-eqt
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - app/templates/login.html
  - app/static/style.css
autonomous: false
requirements: [QUICK-LOCKSCREEN-REVAMP]
must_haves:
  truths:
    - "Lock screen uses the same design tokens, fonts, colors, and dark surface as the dashboard"
    - "Lock screen displays the same Brokr logo (/static/logo.svg) used in the dashboard header"
    - "Unlock button uses the canonical .btn .btn-primary styling and shows a loading/disabled state on submit"
    - "Password field, button, and error message are keyboard-accessible with visible :focus-visible rings and correct ARIA"
    - "Lock card is responsive and centered on mobile and desktop"
    - "Incorrect-password error renders in the canonical error style and is announced to screen readers"
  artifacts:
    - path: "app/templates/login.html"
      provides: "Revamped lock screen markup linking canonical stylesheet and logo"
      contains: "/static/style.css"
    - path: "app/static/style.css"
      provides: "Login/lock-screen component styles using existing design tokens"
      contains: ".login-"
  key_links:
    - from: "app/templates/login.html"
      to: "app/static/style.css"
      via: "link rel=stylesheet href=/static/style.css"
      pattern: "static/style\\.css"
    - from: "app/templates/login.html"
      to: "app/static/logo.svg"
      via: "img src=/static/logo.svg"
      pattern: "static/logo\\.svg"
---

<objective>
Revamp the lock/login screen (`app/templates/login.html`) so it matches the visual
language, branding, and interaction polish established in the recent dashboard UI
revamp (commit fa8471f). Today the login page carries a hand-rolled, drifted copy of
the design tokens in an inline `<style>` block and uses a one-off inline SVG mark
instead of the real Brokr wordmark — so it looks inconsistent with the rest of the app.

Purpose: Brand and visual consistency across every screen the user sees, plus the
accessibility and interaction quality (focus rings, ARIA, loading state) the dashboard
already has.

Output: A login page that links the canonical `/static/style.css`, renders the real
`/static/logo.svg`, uses the existing `.btn .btn-primary` / `.spinner` / `:focus-visible`
patterns, and a small `.login-*` component block added to `style.css`.

Scope guard: ONLY the lock screen. Do not modify dashboard markup (`app/static/index.html`),
`app/static/app.js`, or any Python route. The `/login` and `/static/*` paths are already
exempt from auth middleware (`app/main.py:534-538`), so linking the shared stylesheet and
logo works for unauthenticated visitors.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md

<interfaces>
<!-- Real, verified artifacts from the codebase. Use these directly. -->

Canonical design tokens already defined in app/static/style.css :root —
  --bg:#0f0f0f  --surface:#1a1a1a  --surface-offset:#222222  --border:#2a2a2a
  --text:#e8e8e8  --text-dim:#888888  --text-muted:#6b6b6b
  --teal:#01696f  --teal-light:#028a92  --teal-dim:rgba(1,105,111,0.15)
  --red:#ef4444  --red-dim:rgba(239,68,68,0.12)
  --font:'Inter',-apple-system,BlinkMacSystemFont,sans-serif
  --radius:8px  --radius-sm:4px  --radius-lg:12px
  --space-1..8 (4/8/12/16/20/24/32px)  --shadow-md:0 4px 12px rgba(0,0,0,0.4)
  type scale: --text-xs .72rem / --text-sm .78rem / --text-base .85rem / --text-md .95rem / --text-lg 1.1rem / --text-xl 1.4rem

Canonical button classes (app/static/style.css:179-210):
  .btn            display:inline-flex; align-items:center; gap:var(--space-1);
                  padding:7px 14px; border-radius:var(--radius-sm);
                  font:var(--font)/var(--text-base)/500; transition (background,color,border,transform,opacity)
  .btn-primary    background:var(--teal); color:#fff;
                  :hover background:var(--teal-light) + translateY(-1px);
                  :active translateY(0) opacity .9;
                  :disabled opacity .5; cursor:not-allowed; transform:none
  .btn-block      width:100%; justify-content:center

Canonical spinner + keyframes (app/static/style.css:893-900,950):
  .spinner        16x16; border:2px solid rgba(255,255,255,.3); border-top-color:#fff; border-radius:50%; animation:spin .6s linear infinite
  @keyframes spin { to { transform:rotate(360deg); } }

Canonical accessible focus (app/static/style.css:968-971):
  :focus-visible  outline:2px solid var(--teal-light); outline-offset:2px

Canonical reduced-motion guard already present (app/static/style.css:50-55).

Real logo wordmark — app/static/logo.svg (Brokr / PORTFOLIO INTELLIGENCE, teal #01696f).
  Dashboard renders it as: <img src="/static/logo.svg" alt="Brokr" class="header-logo">  (index.html:20)

How the dashboard loads fonts + favicon (app/static/index.html:7-13) — mirror for parity:
  preconnect googleapis/gstatic, Inter 300;400;500;600;700, favicon /static/favicon.ico

Login route serves the template unchanged (app/main.py:1231-1259):
  GET /login            -> TemplateResponse("login.html", {"request": request})
  POST /login (fail)    -> RedirectResponse "/login?failedattempt=yes" (303)
  POST /login (fail alt)-> TemplateResponse("login.html", {..., possibly "error"})
  Template already reads {{ error }} and renders the failedattempt=yes query param via inline JS.
  Form posts to action="/login" method="POST" with field name="password". DO NOT change these contracts.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add login/lock-screen component styles to the canonical stylesheet</name>
  <files>app/static/style.css</files>
  <action>
    Append a new "LOGIN / LOCK SCREEN" section to the end of app/static/style.css. Use ONLY
    the existing design tokens listed in the interfaces block — do not introduce new hex values
    or new token names. Define these classes:

    - `.login-body` — full-viewport centering: min-height:100vh; display:flex;
      align-items:center; justify-content:center; padding:var(--space-4);
      background:var(--bg). (The shared `body` rule already sets font/background/color; this
      class adds centering only and is applied to the login page's body via class attribute.)
    - `.login-card` — background:var(--surface); border:1px solid var(--border);
      border-radius:var(--radius-lg); padding:var(--space-8) 36px; width:100%;
      max-width:360px; box-shadow:var(--shadow-md). (Matches dashboard surface treatment;
      uses --radius-lg to read as a focal panel.)
    - `.login-logo-row` — display:flex; justify-content:center; margin-bottom:var(--space-6).
    - `.login-logo` — height:64px; width:auto; display:block. (Renders /static/logo.svg, the
      real wordmark — no separate app-name text needed since the wordmark includes "Brokr".)
    - `.login-form-group` — margin-bottom:var(--space-4).
    - `.login-label` — display:block; font-size:var(--text-sm); font-weight:500;
      color:var(--text-dim); margin-bottom:var(--space-1); letter-spacing:.3px;
      text-transform:uppercase.
    - `.login-input` — width:100%; padding:10px 12px; background:var(--bg);
      border:1px solid var(--border); border-radius:var(--radius-sm); color:var(--text);
      font-size:var(--text-md); font-family:var(--font); outline:none;
      transition:border-color .15s ease. `.login-input:focus { border-color:var(--teal); }`
      (The global `:focus-visible` rule already adds the accessible teal ring — do not suppress it.)
    - `.login-error` — background:var(--red-dim); color:var(--red);
      border:1px solid rgba(239,68,68,0.25); border-radius:var(--radius-sm);
      padding:var(--space-2) var(--space-3); font-size:var(--text-base);
      margin-bottom:var(--space-4); display:none.
      `.login-error.visible { display:block; }`
    - A submit-loading affordance reusing the canonical spinner: define
      `.login-submit[aria-busy="true"] .btn-label { display:none; }` and
      `.login-submit .spinner { display:none; }` /
      `.login-submit[aria-busy="true"] .spinner { display:inline-block; }`
      so the existing `.spinner` + `@keyframes spin` show while the form submits.
    - Responsive: inside an existing-style `@media (max-width:480px)` block, reduce
      `.login-card` padding to var(--space-6) var(--space-5) and keep it centered.

    Do not duplicate the `:root` tokens, `@keyframes spin`, reduced-motion guard, `.btn*`,
    `.spinner`, or `:focus-visible` — they already exist and will apply to the login page once
    it links this stylesheet.
  </action>
  <verify>
    <automated>grep -v '^[[:space:]]*/\*' app/static/style.css | grep -Ec '\.login-card|\.login-input|\.login-error|\.login-logo|\.login-submit' | grep -qx 5 && echo TOKENS_OK</automated>
  </verify>
  <done>style.css contains a login section defining .login-card, .login-input, .login-error, .login-logo, and .login-submit using only existing tokens; no token/keyframe/btn duplication introduced.</done>
</task>

<task type="auto">
  <name>Task 2: Rewrite login.html to use the canonical stylesheet, logo, and component classes</name>
  <files>app/templates/login.html</files>
  <action>
    Replace the inline `<style>` block and one-off inline-SVG logo in app/templates/login.html
    with references to the shared design system. Preserve the existing server contracts exactly:
    form `method="POST" action="/login"`, input `name="password"`, the `{{ (error or "Incorrect
    password") | e }}` rendering, the `{% if error %}visible{% endif %}` class toggle, and the
    `failedattempt=yes` query-param JS behavior.

    In <head>:
    - Keep <meta charset> and viewport.
    - Keep <title>Brokr — Login</title>.
    - Mirror the dashboard font preconnect + Inter stylesheet links (index.html:7-9).
    - Add `<link rel="stylesheet" href="/static/style.css">`.
    - Add `<link rel="icon" type="image/x-icon" href="/static/favicon.ico">`.
    - Remove the entire inline `<style>` block.

    In <body>:
    - Add class="login-body" to the <body> tag.
    - Replace `.card` with `<div class="login-card">`.
    - Replace the `.logo-row` + inline `<svg>` + `<span>Brokr</span>` with a single
      `<div class="login-logo-row"><img src="/static/logo.svg" alt="Brokr" class="login-logo"></div>`.
    - Error element: `<div id="error-msg" class="login-error {% if error %}visible{% endif %}"
      role="alert" aria-live="assertive">{{ (error or "Incorrect password") | e }}</div>`.
    - Form: keep method/action. Wrap in `.login-form-group`:
      `<label class="login-label" for="password">Password</label>` and
      `<input class="login-input" type="password" id="password" name="password"
      placeholder="Enter password" autocomplete="current-password"
      autofocus required aria-describedby="error-msg">`.
    - Submit button uses the canonical classes plus the loading hook:
      `<button type="submit" class="btn btn-primary btn-block login-submit">
      <span class="spinner" aria-hidden="true"></span><span class="btn-label">Unlock</span></button>`.
    - Inline JS: keep the failedattempt=yes handling (add .visible to #error-msg and focus
      #password). Additionally, on form `submit`, set the button to a busy state for the
      loading affordance: add `aria-busy="true"` and `disabled` to the submit button so the
      canonical spinner shows during navigation. Guard with a `submit` listener on the form;
      do not preventDefault (the native POST must proceed).

    Keep the label text as "Password" and button label "Unlock" (lock-screen framing,
    consistent with the dashboard's "Lock session" control).
  </action>
  <verify>
    <automated>grep -q '/static/style.css' app/templates/login.html && grep -q '/static/logo.svg' app/templates/login.html && grep -q 'name="password"' app/templates/login.html && grep -q 'action="/login"' app/templates/login.html && ! grep -q '<style' app/templates/login.html && echo LOGIN_OK</automated>
  </verify>
  <done>login.html links /static/style.css and /static/logo.svg, has no inline style block, preserves the POST /login + name="password" + {{ error }} + failedattempt=yes contracts, and uses .btn .btn-primary .btn-block with a spinner loading state and role="alert" error.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>
    Revamped lock/login screen now sharing the dashboard design system: canonical
    /static/style.css tokens, real /static/logo.svg wordmark, .btn-primary unlock button
    with a spinner loading state, accessible :focus-visible rings, ARIA-announced error,
    and responsive centered card.
  </what-built>
  <how-to-verify>
    1. Rebuild/restart with the dev compose file (per project memory):
       `docker compose -f docker-compose.dev.yml up -d --build` (or restart the app service).
    2. Visit `/login` in a browser (open in a private window so you are logged out).
    3. Confirm visual parity with the dashboard: same dark background (#0f0f0f), Inter font,
       teal accents, and the SAME "Brokr / PORTFOLIO INTELLIGENCE" wordmark logo as the header.
    4. Tab through the page with the keyboard — confirm the password field and Unlock button
       show the teal :focus-visible ring.
    5. Enter a wrong password and submit — confirm the unlock button briefly shows the spinner,
       then the page returns showing the styled red error message ("Incorrect password").
    6. Enter the correct password — confirm it unlocks and lands on the dashboard.
    7. Narrow the window to phone width — confirm the card stays centered and padding tightens.
  </how-to-verify>
  <resume-signal>Type "approved" or describe any visual/behavioral issues to fix.</resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| unauthenticated browser → /login | Untrusted visitor renders the login template and submits a password |
| browser → /static/* | Public static assets (style.css, logo.svg) served without auth |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-eqt-01 | Tampering/XSS | login.html error rendering | mitigate | Keep Jinja autoescape on the `{{ (error or "Incorrect password") | e }}` expression; do not introduce `| safe` or inject query params into innerHTML |
| T-eqt-02 | Information disclosure | login error copy | accept | Generic "Incorrect password" message is retained; no username/account enumeration introduced |
| T-eqt-03 | Spoofing/DoS | POST /login rate limit | accept | Rate limiting via existing `Depends(check_rate_limit)` on the route is unchanged by this plan |
| T-eqt-SC | Tampering | dependency installs | accept | No package installs — pure HTML/CSS edits to existing files |
</threat_model>

<verification>
- `/login` renders with the dashboard's visual language (tokens, font, logo, teal accents).
- No inline `<style>` remains in login.html; styling comes from /static/style.css.
- Server contracts unchanged: POST /login, name="password", {{ error }}, failedattempt=yes.
- Keyboard focus shows the teal :focus-visible ring; error has role="alert".
- Submit shows the canonical spinner; reduced-motion users are covered by the existing guard.
- Card is centered and responsive at mobile width.
</verification>

<success_criteria>
- Lock screen is visually consistent with the revamped dashboard (logo, fonts, colors, spacing, dark mode).
- Unlock button uses .btn .btn-primary .btn-block with a spinner loading state.
- Accessibility parity: focus rings, ARIA-announced error, autocomplete hint, autofocus retained.
- Responsive centered layout on mobile and desktop.
- No dashboard files or Python routes modified.
</success_criteria>

<output>
Create `.planning/quick/260529-eqt-revamp-the-lock-screen-to-match-the-styl/260529-eqt-SUMMARY.md` when done
</output>
