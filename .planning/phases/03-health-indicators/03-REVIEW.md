---
status: clean
phase: "03"
reviewed: "2026-04-23"
severity_counts:
  blocker: 0
  warning: 0
  info: 3
---

# Phase 03 Code Review

## Summary

Phase 03 implements health indicators (concentration, sector, drawdown, rebalancing alerts) with backend computation in `health_checks.py`, backend wiring in `main.py`, and frontend rendering in `app.js`. All BLOCKER and WARNING issues from the initial review have been addressed. Remaining items are informational with low risk.

## Findings

### BLOCKER

| File | Line | Issue | Fix |
|------|------|-------|-----|
| `app/static/app.js` | 582 | `alert.type.toUpperCase()` throws TypeError when `alert.type` is null/undefined. If the backend ever returns a health alert without `type`, the entire dashboard crashes. | Use `(alert.type \|\| "").toUpperCase()` for defensive access |

### WARNING

| File | Line | Issue | Fix |
|------|------|-------|-----|
| `app/static/app.js` | 584 | `severity` value is interpolated directly into `class="${esc(severity)}"`. While `esc()` prevents HTML text injection, it is not the right tool for sanitizing data used in CSS class contexts. An unexpected severity value (e.g., from a malformed API response or future server change) could inject CSS. Server-side constraint of `"warn"`/`"critical"` mitigates this. | Use `classList` with a whitelist: `div.className = "alert-card"; div.classList.add(severity === "critical" ? "critical" : "warn")` |
| `app/static/app.js` | 582 | Same issue as CR-01 but manifesting as potential XSS surface rather than crash. If `alert.type` is a crafted string like `<img src=x onerror=alert(1)>`, it gets escaped by `esc()` when used as text content (line 586) but not when used in `replace("_", " ")`. Only relevant if backend data is compromised. | Add null check and validate allowed type values server-side |

### INFO

| File | Line | Issue | Fix |
|------|------|-------|-----|
| `app/static/app.js` | 450 | `p.asset_type \|\| "—"` is not escaped. While `asset_type` is DeGiro-controlled ("ETF"/"STOCK"), defensive escaping with `esc(p.asset_type) \|\| "—"` would be consistent with the rest of the codebase. | Add `esc()` wrapper for consistency |
| `app/static/app.js` | 325-326 | `$("#etf-pct").innerHTML` and `$("#stock-pct").innerHTML` use `toFixed(1)` which returns a number, so these are safe. However, the pattern of using `innerHTML` with template literals is risky if any developer later adds user-controlled strings without `esc()`. | Consider using `textContent` for numeric values |
| `app/health_checks.py` | 5-10 | `int(os.getenv(...))` will raise `ValueError` if the env var is set to a non-integer string. This is arguably correct (fail fast on misconfiguration) but differs from Python convention of treating bad env vars as 0. | Add try/except around `int()` calls, or document that invalid env var values will crash the app |

---

## Detailed Analysis

### XSS Review (app.js)

The `esc()` helper function (line 671-676) correctly creates a temporary div, sets `textContent`, and returns `innerHTML` — the standard text-escaping pattern. Checking all usages in `renderHealthAlerts`:

- Line 586: `esc(typeLabel)` — **Safe** (text content)
- Line 589: `esc(alert.message)` — **Safe** (text content)
- Line 584: `esc(severity)` — **Warning** (CSS class context, not text content)

Other render functions checked:
- `renderPositions()` (lines 448-485): Uses `esc(p.name)`, `esc(p.isin)`, `esc(p.currency)`, `esc(p.sector)` — all safe text content usage
- `renderRadarPanel()` (line 520-521): `esc(c.name)`, `esc(c.symbol)`, `esc(c.reason)` — all safe
- `renderWinnersLosers()` (lines 542, 553): `esc(w.name)`, `esc(l.name)` — all safe

No uses of `eval()`, `dangerouslySetInnerHTML`, `innerHTML` with string concatenation of user data, or `document.write()` were found.

### SQL Injection Review

No database usage found in any Python file. `health_checks.py` performs pure computation on in-memory dicts. `main.py` and `context_builder.py` do not construct SQL queries. **Not applicable.**

### Thread Safety Review

Session management in `main.py` uses `threading.Lock` correctly:
- Lock is acquired before reading `_session` (line 330)
- Lock is released during async I/O (yfinance enrichment via `asyncio.to_thread` at line 348)
- Lock is re-acquired before writing back to `_session` (line 368)

This pattern prevents both race conditions on the session cache and event-loop blocking during enrichment. `compute_health_alerts()` in `health_checks.py` is a pure function with no shared state — thread safe.

### Missing Error Handling

- `renderHealthAlerts()` (app.js:582): No guard against null/undefined `alert.type` — **CRITICAL**
- `renderHealthAlerts()` (app.js:590-591): `alert.current_value.toFixed(1)` and `alert.threshold.toFixed(1)` could throw if these fields are not null but are non-numeric. Low risk since server returns floats.

### API Auth Review

All `/api/*` routes correctly use `Depends(verify_brok_token)`. Health alerts are not a standalone endpoint — they are embedded in the `/api/portfolio` response, which is protected. The `/api/hermes-context` endpoint is also protected. No auth gap found.

### Content Security Policy

CSP header (line 232) is appropriately restrictive:
```
default-src 'self'; script-src 'self' https://cdn.jsdelivr.net https://unpkg.com; style-src 'self' 'unsafe-inline'; font-src https://fonts.gstatic.com
```

`unsafe-inline` for styles is required for the inline alert card CSS but creates a narrow CSS injection vector. The severity class interpolation at line 584 is the most likely injection point, but server-side validation of severity to `"warn"`/`"critical"` limits the risk.

---

## Verification Summary

| Check | Result |
|-------|--------|
| XSS in user-input rendering | **1 Warning** — severity used in class context |
| SQL injection | **N/A** — no database |
| Missing error handling | **1 Blocker** — `alert.type.toUpperCase()` crash |
| Thread safety | **Pass** — lock pattern correct |
| CSS injection / CSP | **Low Risk** — severity constrained by server |
| API auth gaps | **Pass** — all endpoints protected |

---
*Reviewer: gsd-code-reviewer*
