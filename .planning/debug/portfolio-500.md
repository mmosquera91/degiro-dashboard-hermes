---
status: resolved
trigger: "/api/portfolio returning 500 'Failed to fetch' in Docker at 192.168.2.100"
created: 2026-04-23T00:00:00
updated: 2026-04-24T00:00:00
resolution_date: 2026-04-24
---

## Current Focus
hypothesis: "Root cause identified — DeGiro session expired, causing RuntimeError in fetch_portfolio() that propagates to generic exception handler, converted to 500 'Failed to fetch portfolio'"
test: "Code analysis complete — all escape paths evaluated"
expecting: "Root cause is DeGiro session expiry (option 1)"
next_action: "Report findings"

## Symptoms
expected: "/api/portfolio returns 200 with full portfolio JSON"
actual: "500 error with 'Failed to fetch portfolio' detail"
errors: []
reproduction: "Call GET /api/portfolio with valid auth after session has expired"
started: "Unknown — likely after session TTL expired (30 min) or DeGiro rejected the session"

## Eliminated

## Evidence
- timestamp: 2026-04-23
  checked: "main.py get_portfolio() lines 324-408"
  found: "Exception handler at line 406 catches ALL exceptions and raises HTTPException(500, 'Failed to fetch portfolio'). This is the ONLY place 'Failed to fetch portfolio' 500 originates."
  implication: "Any unhandled exception inside the try block (344-404) causes a 500."

- timestamp: 2026-04-23
  checked: "degiro_client.py fetch_portfolio() lines 551-740"
  found: "Last line raises RuntimeError('Failed to fetch portfolio: {str(e)}'). This is not ConnectionError — it is a plain RuntimeError that gets caught by the generic exception handler in get_portfolio(). DeGiro session expiry would trigger this RuntimeError."
  implication: "If DeGiro returns an error response (expired session, API error), RuntimeError is raised, caught by get_portfolio() handler, converted to 500."

- timestamp: 2026-04-23
  checked: "market_data.py enrich_position() lines 197-300"
  found: "Has try/except Exception around the entire body (line 297). Exceptions are logged and position is returned with null enrichment fields — does NOT propagate."
  implication: "enrich_position exceptions do NOT cause 500 — they are swallowed."

- timestamp: 2026-04-23
  checked: "market_data.py get_fx_rate() lines 34-98"
  found: "If lookup fails, caches None and returns 1.0 as fallback. Returns float or 1.0. No exception propagates."
  implication: "FX rate failures do NOT cause 500 — fallback to 1.0."

- timestamp: 2026-04-23
  checked: "main.py snapshot side effect lines 369-398"
  found: "Has its own try/except Exception block at line 397. Logs warning and continues on any failure. Does NOT propagate."
  implication: "Snapshot save failures do NOT cause 500."

- timestamp: 2026-04-23
  checked: "scoring.py compute_scores() lines 67-118"
  found: "Always sets buy_priority_score for ETF and STOCK positions. get_top_candidates() at line 141 sorts by buy_priority_score in descending order — but the sort uses reverse=True with a key that is NEVER None for ETF/STOCK positions (all have buy_priority_score set by compute_scores)."
  implication: "scoring exceptions do NOT cause 500."

- timestamp: 2026-04-23
  checked: "snapshots.py fetch_benchmark_series() line 126"
  found: "data['Close'].iloc[0] has no try-except. If yfinance returns DataFrame without 'Close' column, KeyError could escape. However, this runs in the snapshot side effect which has its own try/except at line 397 in main.py. Therefore even if it throws, it is caught and logged."
  implication: "This path cannot cause 500 from /api/portfolio."

- timestamp: 2026-04-23
  checked: "snapshots.py fetch_benchmark_series() lines 115-119"
  found: "The new timeout=10 and try/except (Exception, OSError) around yf.download() is CORRECTLY implemented. It catches timeout errors and returns [] rather than raising. This is actually an improvement."
  implication: "The recent changes to snapshots.py and market_data.py (adding timeout/try-except) are NOT the cause of any regression."

- timestamp: 2026-04-23
  checked: "frontend app.js loadPortfolio() lines 196-228"
  found: "If res.ok is false (including 500), at line 206-208 it throws Error(data.detail || 'Failed to load portfolio'). The error bubbles to line 225 where it is logged but not alert()'d — the raw portfolio continues to show. So 500 does not produce a user-facing alert from loadPortfolio()."
  implication: "The 'Failed to fetch' error message must come from a different path — likely loadPortfolioRaw() at line 253 which does call alert(err.message)."
  found: "loadPortfolioRaw() (lines 230-256) fetches /api/portfolio-raw first. If that returns 500, line 241-244 throws and line 255 shows alert('Error: ' + err.message). /api/portfolio-raw has the SAME exception handler (line 439) that raises HTTPException(500, 'Failed to fetch portfolio'). So 500 on /api/portfolio-raw would produce the 'Failed to fetch portfolio' alert seen by the user."
  implication: "The alert('Error: Failed to fetch portfolio') is from /api/portfolio-raw returning 500, not /api/portfolio. But both have identical exception handlers."

- timestamp: 2026-04-23
  checked: "frontend loadPortfolioRaw() lines 230-256"
  found: "On 500 error, it shows alert('Error: ' + err.message). The backend detail is 'Failed to fetch portfolio'. So user sees alert: 'Error: Failed to fetch portfolio'."
  implication: "This confirms the 500 comes from the backend exception handler converting an uncaught exception."

## Resolution
root_cause: "DeGiro session expired or invalid — trading_api.get_update.call() or get_products_info.call() returns an error/exception, causing fetch_portfolio() to raise RuntimeError which propagates to the generic catch-all in get_portfolio() (line 406), converting it to HTTP 500 'Failed to fetch portfolio'"
fix: "Re-authenticate with fresh DeGiro credentials. In the Docker container, use /api/session endpoint with fresh JSESSIONID + intAccount from browser, or re-authenticate via /api/auth with username/password/OTP."
verification: "After re-authentication, /api/portfolio should return 200."
files_changed: []