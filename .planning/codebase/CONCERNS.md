# Codebase Concerns

**Analysis Date:** 2026-04-23

---

## CRITICAL Severity

### C-01: Debug Endpoint Exposes User Passwords in HTTP Response

- **Issue:** The `/api/debug-login` endpoint calls `debug_login_variants()` which returns the full `request_payload` dict containing plaintext `username` and `password` in every variant result. These payloads are sent back in the HTTP JSON response.
- **Files:**
  - `app/main.py` line 378-394 (the endpoint)
  - `app/degiro_client.py` line 118, 128, 138, 262, 278, 351 (`request_payload` included in results)
  - `app/degiro_client.py` line 87-94 (payload contains `password` field)
- **Impact:** Anyone who can reach the debug endpoint (including network attackers if not behind auth) receives the user's DeGiro password in the response body. This is a direct credential exposure vulnerability.
- **Current mitigation:** None. The endpoint has no authentication guard.
- **Fix approach:** Remove `request_payload` from all debug result dicts, or better, remove or gate the entire `/api/debug-login` endpoint behind an environment flag that defaults to disabled. At minimum, redact `password` and `oneTimePassword` fields before returning.

### C-02: Debug Endpoint Exposes DeGiro Session IDs in HTTP Response

- **Issue:** When the debug login succeeds, `parsed_success` contains the full `LoginSuccess` model dump which includes the `session_id`. Variant F also exposes cookies from the login page GET request.
- **Files:**
  - `app/degiro_client.py` line 146 (parsed_success with session_id)
  - `app/degiro_client.py` line 321-322 (cookies from login page)
  - `app/degiro_client.py` line 356-357 (session_id exposed in variant F)
- **Impact:** A network observer or anyone calling the endpoint obtains a valid DeGiro session ID, granting full account access.
- **Fix approach:** Redact or omit `session_id` from debug results. Gate the endpoint behind a disabled-by-default environment variable.

### C-03: No Authentication on Any API Endpoint

- **Issue:** None of the API endpoints (`/api/auth`, `/api/portfolio`, `/api/hermes-context`, etc.) require any form of authentication to call. Anyone with network access to the server can authenticate with DeGiro, fetch portfolio data, and export the Hermes context.
- **Files:** `app/main.py` lines 216-394 (all route handlers)
- **Impact:** If the app is exposed beyond localhost (e.g., on a network, via port mapping), any user on that network can access the full DeGiro portfolio, trigger logins, and extract credentials via the debug endpoint.
- **Current mitigation:** Docker port mapping defaults to HOST_PORT=8000. The `.env` file only contains `HOST_PORT=8000`.
- **Fix approach:** Add session-based or token-based auth to the web app itself. Consider binding to 127.0.0.1 by default. Add a `BROKR_AUTH_TOKEN` environment variable for API access.

### C-04: Plaintext Credentials Transmitted Over HTTP

- **Issue:** The frontend sends DeGiro username and password to `/api/auth` over plain HTTP (no TLS enforcement). The FastAPI/Uvicorn server has no HTTPS configuration.
- **Files:**
  - `app/static/app.js` line 127-131 (fetch POST to `/api/auth` with credentials)
  - `app/main.py` line 216-237 (receives credentials)
  - `Dockerfile` line 18 (uvicorn binds plain HTTP)
  - `docker-compose.yml` line 6 (port mapping without TLS termination)
- **Impact:** DeGiro credentials can be intercepted by anyone on the same network segment.
- **Fix approach:** Add a reverse proxy (nginx/Caddy) with TLS in front of the app. Add HSTS and security headers. At minimum, bind to 127.0.0.1 and document that the app must not be exposed without TLS.

---

## HIGH Severity

### H-01: Blocking I/O Inside Async Endpoint (Event Loop Stall)

- **Issue:** The `enrich_positions()` function in `market_data.py` is declared `async` but internally calls synchronous `yf.Ticker()` lookups and `time.sleep()` for throttling. These block the entire asyncio event loop, making the server unresponsive during enrichment.
- **Files:**
  - `app/market_data.py` lines 207-280 (`enrich_position` is synchronous with `time.sleep`)
  - `app/market_data.py` line 283 (`async def enrich_positions` calls sync code)
  - `app/market_data.py` lines 22-28 (`_yf_throttle` uses `time.sleep`)
- **Impact:** While portfolio enrichment runs (potentially 30+ seconds for many positions), ALL other requests to the server are blocked. The health endpoint won't respond, the UI appears frozen.
- **Fix approach:** Run yfinance calls in a thread pool executor via `asyncio.get_event_loop().run_in_executor()`, or use `asyncio.to_thread()`. This allows the event loop to serve other requests during enrichment.

### H-02: No CORS Policy Configured

- **Issue:** The FastAPI app has no CORS middleware configured. Any website can make cross-origin requests to the API.
- **Files:** `app/main.py` (no `CORSMiddleware` added)
- **Impact:** A malicious website could make requests to the Brokr API if the user has it running locally, potentially extracting portfolio data or triggering actions.
- **Fix approach:** Add `fastapi.middleware.cors CORSMiddleware` with restricted origins (e.g., `["http://localhost:8000"]`).

### H-03: No Security Headers

- **Issue:** The application sets no security-related HTTP headers: no Content-Security-Policy, no X-Frame-Options, no X-Content-Type-Options, no Strict-Transport-Security.
- **Files:** `app/main.py` (no security header middleware)
- **Impact:** The app is vulnerable to clickjacking (X-Frame-Options missing), MIME-type sniffing attacks (X-Content-Type-Options missing), and has no defense-in-depth against XSS (Content-Security-Policy missing).
- **Fix approach:** Add security headers middleware. At minimum:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Content-Security-Policy: default-src 'self'; script-src 'self' https://cdn.jsdelivr.net https://unpkg.com; style-src 'self' 'unsafe-inline'; font-src https://fonts.gstatic.com`

### H-04: No Input Validation on Session ID and Credentials

- **Issue:** The `AuthRequest` and `SessionRequest` Pydantic models accept arbitrary-length strings with no format validation. The session ID could be any string, and credentials are passed directly to the DeGiro API without length or format checks.
- **Files:**
  - `app/main.py` lines 196-204 (model definitions)
- **Impact:** Malformed or extremely large inputs could cause unexpected behavior in downstream DeGiro API calls or log entries.
- **Fix approach:** Add `min_length`/`max_length` constraints to Pydantic models. Validate email format for username. Validate session ID format (known prefix patterns).

### H-05: Exception Messages Leak Internal Details to Client

- **Issue:** All exception handlers in `main.py` pass the raw exception string directly to the HTTP response via `str(e)`. This can expose internal paths, library error details, and API response fragments.
- **Files:**
  - `app/main.py` line 237: `detail=f"Authentication failed: {str(e)}"`
  - `app/main.py` line 264: `detail=f"Session authentication failed: {str(e)}"`
  - `app/main.py` line 313: `detail=f"Failed to fetch portfolio: {str(e)}"`
  - `app/main.py` line 346: `detail=f"Failed to fetch portfolio: {str(e)}"`
  - `app/main.py` line 394: `detail=str(e)` (debug endpoint)
- **Impact:** Internal error details (DeGiro API error responses, Python tracebacks, library internals) are exposed to the client, aiding potential attackers.
- **Fix approach:** Return generic user-facing error messages. Log the full exception server-side. Use a mapping from known error types to safe messages.

---

## MEDIUM Severity

### M-01: Debug/Test Scripts Shipped in Production Container

- **Issue:** Six debug and test scripts are included in the Docker image via `COPY app/ ./app/` in the Dockerfile. These scripts contain hardcoded patterns for credential handling and print session IDs to stdout.
- **Files:**
  - `app/debug_portfolio.py` (73 lines)
  - `app/debug_raw_portfolio.py` (51 lines)
  - `app/debug_from_session.py` (31 lines)
  - `app/debug_int_account.py` (40 lines)
  - `app/test_auth_methods.py` (107 lines)
  - `app/test_login.py` (34 lines)
  - `Dockerfile` line 10 (`COPY app/ ./app/` copies everything)
- **Impact:** These scripts can be executed inside the running container (`docker compose exec`) and print partial session IDs to stdout (e.g., `session_id[:15]`). They also accept credentials via command-line arguments which may appear in process listings.
- **Fix approach:** Move debug/test scripts to a separate directory not included in the Docker build. Add a `.dockerignore` entry for them. The `.dockerignore` file exists but only contains `__pycache__`.

### M-02: In-Memory Session Store Not Thread-Safe for Reads

- **Issue:** The `_session` dict is protected by `_session_lock` for writes but the `_is_session_valid()` and `_is_portfolio_fresh()` checks read from `_session` outside the lock in `get_portfolio()` at lines 282-287. The portfolio data is also returned by reference, meaning a concurrent write could mutate it during serialization.
- **Files:**
  - `app/main.py` lines 276-287 (reading `_is_session_valid()` outside lock)
  - `app/main.py` line 279 (returning `_session["portfolio"]` by reference)
- **Impact:** Race conditions under concurrent requests could return partially-written portfolio data or cause KeyError crashes.
- **Fix approach:** Wrap the entire read-check-return sequence in the lock. Return a deep copy of the portfolio data, or ensure the portfolio dict is never mutated after creation.

### M-03: FX Rate Cache Never Invalidates

- **Issue:** The `_fx_cache` dict in `market_data.py` caches FX rates indefinitely for the lifetime of the process. Rates from the first request persist forever.
- **Files:**
  - `app/market_data.py` line 15 (`_fx_cache: dict[str, float] = {}`)
  - `app/market_data.py` line 61-62 (cache write with no TTL)
- **Impact:** Stale FX rates cause incorrect EUR value calculations. If the app runs for days, rates can drift significantly from market reality.
- **Fix approach:** Add a TTL to the cache (e.g., 1 hour). Use a timestamp alongside each rate. Alternatively, invalidate the cache when a new portfolio is fetched.

### M-04: yfinance Rate Limiting Uses Global Mutable State

- **Issue:** The `_last_yf_request` global variable and `_yf_throttle()` function are not thread-safe. Under concurrent requests, multiple threads could bypass the throttle.
- **Files:**
  - `app/market_data.py` lines 19-28 (`_last_yf_request` global, `_yf_throttle`)
- **Impact:** Under concurrent load, yfinance rate limits could be exceeded, causing IP blocks or data fetch failures.
- **Fix approach:** Use a threading.Lock around the throttle logic, or use an asyncio.Lock if moving to async yfinance calls.

### M-05: Single-User Session Architecture

- **Issue:** The entire application stores one session in a module-level dict. Only one DeGiro account can be connected at a time. A second login overwrites the first without notification.
- **Files:**
  - `app/main.py` lines 22-27 (`_session` dict)
  - `app/main.py` lines 225-229 (session overwrite on new auth)
- **Impact:** If the app is accessible to multiple users, one user's authentication silently evicts another's session. The portfolio data from user A could briefly be visible to user B during the transition.
- **Fix approach:** Either document this as single-user only (and enforce localhost-only binding), or implement per-user session management using browser cookies or tokens.

### M-06: No CSRF Protection

- **Issue:** The POST endpoints (`/api/auth`, `/api/session`, `/api/logout`, `/api/debug-login`) accept requests from any origin without CSRF tokens. A malicious page could submit forged requests.
- **Files:** `app/main.py` lines 216, 240, 368, 378 (all POST routes)
- **Impact:** An attacker could trick a logged-in user's browser into submitting auth requests or logging out.
- **Fix approach:** Add CSRF token validation for state-changing endpoints. Since this is an API-first app with a SPA frontend, consider using the `SameSite` cookie attribute or custom header validation.

### M-07: Third-Party CDN Dependencies Without Integrity Checks

- **Issue:** The frontend loads Chart.js and Lucide icons from external CDNs (jsdelivr, unpkg) without Subresource Integrity (SRI) hashes. Google Fonts are also loaded cross-origin.
- **Files:**
  - `app/static/index.html` line 10 (`cdn.jsdelivr.net/npm/chart.js`)
  - `app/static/index.html` line 11 (`unpkg.com/lucide`)
  - `app/static/index.html` line 9 (`fonts.googleapis.com`, `fonts.gstatic.com`)
- **Impact:** If the CDN is compromised, arbitrary JavaScript could be injected into the app, potentially stealing DeGiro credentials entered in the modal.
- **Fix approach:** Add `integrity` and `crossorigin` attributes to CDN script tags. Alternatively, vendor these dependencies locally.

### M-08: No Structured Logging or Log Levels by Environment

- **Issue:** Logging is configured with `basicConfig(level=logging.INFO)` hardcoded in the app module. There is no way to adjust log verbosity via environment variable. Sensitive information patterns (partial usernames) are logged.
- **Files:**
  - `app/main.py` line 18 (hardcoded `logging.basicConfig(level=logging.INFO)`)
  - `app/degiro_client.py` line 393 (logs partial username: `username[:3] + "***"`)
- **Impact:** In production, verbose logging may fill disks. The partial username logging, while truncated, could still be identifying in small user bases.
- **Fix approach:** Use `os.getenv("LOG_LEVEL", "INFO")` for configuration. Remove partial username logging. Consider structured JSON logging for production.

### M-09: DeGiro Session ID Logged/Printed Partially in Debug Scripts

- **Issue:** Several debug scripts print partial session IDs to stdout. While truncated, session IDs often have predictable structures and partial exposure reduces the brute-force space.
- **Files:**
  - `app/test_login.py` line 27: `print(f"SUCCESS! session_id: {session_id[:10]}...")`
  - `app/test_auth_methods.py` line 21: `print(f"  [{label}] SUCCESS! session_id: {session_id[:15]}...")`
  - `app/debug_from_session.py` line 13: `print(f"Session ID set: {trading_api.connection_storage.session_id[:20]}...")`
- **Impact:** Session IDs in container logs could be accessed by anyone with `docker logs` access.
- **Fix approach:** Remove or mask session ID printing. Log only success/failure status.

---

## LOW Severity

### L-01: Duplicate Code Between `_build_raw_portfolio_summary` and `_build_portfolio_summary`

- **Issue:** These two functions in `main.py` share nearly identical logic for computing total values, P&L, allocations, and top winners/losers. Only the enrichment data differs.
- **Files:**
  - `app/main.py` lines 58-118 (`_build_raw_portfolio_summary`)
  - `app/main.py` lines 121-179 (`_build_portfolio_summary`)
- **Impact:** Bug fixes or changes to one must be replicated to the other. Divergence risk.
- **Fix approach:** Extract shared computation into a single function that accepts optional enrichment data.

### L-02: `_resolve_yf_symbol` Function Does Not Use Its `suffixes_to_try` List

- **Issue:** The function builds a `suffixes_to_try` list but never iterates over it. It always returns the base symbol unchanged.
- **Files:**
  - `app/market_data.py` lines 83-99 (`_resolve_yf_symbol`)
  - Line 97: `suffixes_to_try` is defined but unused
  - Line 99: returns `symbol` directly
- **Impact:** European stocks with symbols that lack exchange suffixes may fail to resolve on yfinance, leading to missing enrichment data.
- **Fix approach:** Either implement the suffix-try logic with fallback, or remove the dead code if it was intentionally abandoned.

### L-03: Typo in DeGiro API Payload (`queryTarams`)

- **Issue:** The DeGiro API payload uses the key `"queryTarams"` (with typo) instead of `"queryParams"`. This appears in multiple places.
- **Files:**
  - `app/degiro_client.py` line 93 (`"queryTarams": {}`)
  - `app/degiro_client.py` line 176, 253, 331, 387 (same typo repeated)
- **Impact:** Unknown -- this appears to match what the degiro-connector library sends, so it may be intentional to match the upstream API's actual field name. But it is suspicious and undocumented.
- **Fix approach:** Verify against DeGiro API documentation whether this is the correct field name. If it is a typo that happens to work because the API ignores unknown fields, switch to `"queryParams"`.

### L-04: No Automated Tests

- **Issue:** There are no automated test files in the project. The files named `test_*.py` are interactive manual testing scripts that prompt for real credentials, not unit/integration tests.
- **Files:** No `tests/` directory, no `pytest.ini`, no test configuration.
- **Impact:** Refactoring or feature changes have no safety net. Regressions will only be caught manually.
- **Fix approach:** Add pytest with unit tests for scoring logic, context builder, and FX rate computation. Add integration tests with mocked DeGiro responses for portfolio parsing.

### L-05: `p.asset_type` Used in innerHTML Without Escaping

- **Issue:** In `renderPositions()`, `p.asset_type` is interpolated directly into innerHTML without the `esc()` function. While this value is currently controlled (only "ETF" or "STOCK"), it originates from server data and the convention is inconsistent.
- **Files:**
  - `app/static/app.js` line 447: `<td>${p.asset_type || "---"}</td>`
- **Impact:** Low risk since the value comes from server-controlled `asset_type` field, but this breaks the defense-in-depth pattern used elsewhere (all other string fields use `esc()`).
- **Fix approach:** Apply `esc()` consistently to all interpolated values: `${esc(p.asset_type || "---")}`.

### L-06: Error Alerted via `alert()` in JavaScript

- **Issue:** Error messages from the backend are shown to the user via `window.alert()`, which is a poor UX pattern and can leak backend error details.
- **Files:**
  - `app/static/app.js` line 245: `alert("Error: " + err.message)`
  - `app/static/app.js` line 581: `alert("Hermes context copied to clipboard!")`
  - `app/static/app.js` line 590: `alert("Export failed: " + err.message)`
- **Impact:** Poor user experience. Alerts are blocking and modal. Backend error messages may contain sensitive details.
- **Fix approach:** Replace with a toast notification system. Sanitize error messages before displaying.

### L-07: `get_fx_rate` Silently Returns 1.0 on Failure

- **Issue:** When FX rate lookup fails, the function caches and returns 1.0 (a 1:1 rate). This silently produces incorrect EUR values for non-EUR positions.
- **Files:**
  - `app/market_data.py` line 79: `_fx_cache[key] = 1.0; return 1.0`
- **Impact:** Non-EUR positions (USD, GBP, etc.) will show incorrect values if yfinance fails, with no warning to the user.
- **Fix approach:** Return `None` on failure and handle the missing rate upstream. Show a warning in the UI when FX rates are unavailable. Do not cache failure results.

### L-08: No Request Timeout Configuration

- **Issue:** The yfinance and DeGiro API calls have no explicit timeout configuration. A hung external API call will block indefinitely.
- **Files:**
  - `app/market_data.py` (yfinance calls have no timeout)
  - `app/degiro_client.py` (requests library defaults used)
- **Impact:** If DeGiro or yfinance APIs are slow or unresponsive, the server hangs without returning to the user.
- **Fix approach:** Set explicit timeouts on all external HTTP calls (e.g., `requests.get(..., timeout=30)` for DeGiro, configure yfinance timeouts).

### L-09: No Health Check for External Dependencies

- **Issue:** The `/health` endpoint only returns `{"status": "ok"}` without checking if the DeGiro connection or yfinance are reachable.
- **Files:**
  - `app/main.py` lines 208-210
- **Impact:** The health check passes even when external services are down, making it useless for monitoring.
- **Fix approach:** Add optional dependency checks to the health endpoint (e.g., verify yfinance is reachable, check if a session exists).

---

## Test Coverage Gaps

### TG-01: No Unit Tests for Scoring Logic

- **What's not tested:** `compute_scores()`, `compute_momentum_score()`, `compute_value_score()`, `_min_max_normalize()`, `compute_portfolio_weights()`, `get_top_candidates()` in `app/scoring.py`
- **Files:** `app/scoring.py` (197 lines)
- **Risk:** Scoring formula errors could produce incorrect buy recommendations without detection. Edge cases like single-position portfolios, all-zero values, and None-heavy data are untested.
- **Priority:** High

### TG-02: No Unit Tests for Market Data Enrichment

- **What's not tested:** `enrich_position()`, `compute_rsi()`, `_compute_performance()`, `get_fx_rate()` in `app/market_data.py`
- **Files:** `app/market_data.py` (319 lines)
- **Risk:** RSI calculation bugs, performance period boundary errors, FX rate fallback behavior.
- **Priority:** Medium

### TG-03: No Unit Tests for Portfolio Parsing

- **What's not tested:** `DeGiroClient.fetch_portfolio()`, `_kv_list_to_dict()` in `app/degiro_client.py`
- **Files:** `app/degiro_client.py` lines 447-741
- **Risk:** DeGiro API format changes will silently break position parsing. The extensive defensive code (multiple fallback paths for data extraction) indicates the API format is unstable and needs regression tests.
- **Priority:** High

### TG-04: No Tests for Context Builder

- **What's not tested:** `build_hermes_context()`, `_build_plaintext()` in `app/context_builder.py`
- **Files:** `app/context_builder.py` (156 lines)
- **Risk:** Formatting errors in the Hermes plaintext export could produce misleading AI analysis.
- **Priority:** Low

---

*Concerns audit: 2026-04-23*
