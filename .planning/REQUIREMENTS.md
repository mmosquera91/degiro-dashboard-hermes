# Requirements: Brokr v1.3 Test Coverage Sprint

**Defined:** 2026-05-04
**Core Value:** Reliable portfolio health visibility — seeing risk and performance signals at a glance so you can make informed decisions without manually crunching numbers.

## v1 Requirements

### Auth & Middleware

- [ ] **AUTH-01**: auth.py `_make_token` creates HMAC-SHA256 signed token with expiry
- [ ] **AUTH-02**: auth.py `_verify_token` validates expiry and signature with timing-safe comparison
- [ ] **AUTH-03**: auth.py `make_session_cookie` returns token + cookie kwargs (Secure, HttpOnly, SameSite=Lax)
- [ ] **AUTH-04**: auth.py `verify_session_cookie` returns True for valid token, False for invalid/expired
- [ ] **AUTH-05**: auth.py `clear_session_cookie` returns correct delete_cookie kwargs
- [ ] **AUTH-06**: rate_limiter.py `check_rate_limit` allows up to MAX_ATTEMPTS (5) in WINDOW_SECONDS (60s)
- [ ] **AUTH-07**: rate_limiter.py `check_rate_limit` raises HTTPException 429 after limit exceeded
- [ ] **AUTH-08**: rate_limiter.py `_clean_old_timestamps` removes timestamps outside the window
- [ ] **AUTH-09**: main.py middleware `check_session_cookie` redirects unauthenticated requests to /login
- [ ] **AUTH-10**: main.py middleware `check_session_cookie` passes valid session cookie through
- [ ] **AUTH-11**: main.py `verify_brok_token` validates Bearer token, returns 401 on mismatch

### API Routes

- [ ] **ROUTES-01**: POST /login with correct password sets brokr_session cookie and redirects to /
- [ ] **ROUTES-02**: POST /login with wrong password redirects to /login?failedattempt=yes
- [ ] **ROUTES-03**: POST /api/auth with valid credentials returns {"status": "authenticated"}
- [ ] **ROUTES-04**: POST /api/auth with ConnectionError returns 401
- [ ] **ROUTES-05**: POST /api/auth with generic error returns 500
- [ ] **ROUTES-06**: POST /api/session with valid session_id returns {"status": "authenticated"}
- [ ] **ROUTES-07**: POST /api/session with ConnectionError returns 401
- [ ] **ROUTES-08**: POST /api/logout clears session and returns {"status": "logged_out"}
- [ ] **ROUTES-09**: GET /api/session-token returns BROKR_AUTH_TOKEN (bootstrap endpoint)
- [ ] **ROUTES-10**: GET /api/session-token without session cookie returns redirect to /login (middleware)
- [ ] **ROUTES-11**: GET /health returns {"status": "ok"} without auth
- [ ] **ROUTES-12**: GET /api/portfolio without auth token returns 401

### DeGiro Client (Mocked)

- [ ] **DEGIRO-01**: DeGiroClient `_kv_list_to_dict` converts list of {"key","value"} dicts to flat dict
- [ ] **DEGIRO-02**: DeGiroClient `from_session_id` accepts session_id + optional int_account, returns TradingAPI
- [ ] **DEGIRO-03**: DeGiroClient `from_session_id` raises ConnectionError on invalid session
- [ ] **DEGIRO-04**: DeGiroClient `fetch_portfolio` returns dict with positions and cash_available
- [ ] **DEGIRO-05**: DeGiroClient `fetch_portfolio` raises ConnectionError on session expired (2FA required, anti-bot)
- [ ] **DEGIRO-06**: Portfolio parsing handles empty positions list
- [ ] **DEGIRO-07**: Portfolio parsing handles missing optional fields gracefully

### Integration

- [ ] **INTEG-01**: login flow → session-token → protected endpoint works end-to-end with cookie
- [ ] **INTEG-02**: Cookie validation chain: middleware checks cookie → verify_brok_token checks Bearer
- [ ] **INTEG-03**: Unauthorized request to /api/* redirects to /login then returns 303
- [ ] **INTEG-04**: Expired cookie is cleared and redirect to /login occurs

## v2 Requirements

Deferred. Tracked but not in current roadmap.

### API Routes (Extended)

- **ROUTES-13**: GET /api/portfolio serves cached portfolio when session expired but cache exists
- **ROUTES-14**: POST /api/refresh-prices runs enrichment in background thread, returns immediately
- **ROUTES-15**: GET /api/benchmark returns cached series within TTL, fresh fetch outside TTL

### Error Handling

- **ERROR-01**: Rate limiter blocks IP after MAX_ATTEMPTS, unblocks after WINDOW_SECONDS
- **ERROR-02**: Operation lock returns 409 when enrichment already running
- **ERROR-03**: Benchmark cache invalidation on snapshot deletion

## Out of Scope

| Feature | Reason |
|---------|--------|
| Tests against real DeGiro API | Flaky, rate-limited, requires live credentials |
| Frontend JS tests | Backend coverage sprint only |
| TestClient lifespan startup (full) | Startup side effects (asyncio loops, file writes) make tests hang; override lifespan in tests |
| Performance/load testing | Out of scope for unit test sprint |
| Database integration tests | No database — in-memory only |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | Phase 11 | Pending |
| AUTH-02 | Phase 11 | Pending |
| AUTH-03 | Phase 11 | Pending |
| AUTH-04 | Phase 11 | Pending |
| AUTH-05 | Phase 11 | Pending |
| AUTH-06 | Phase 11 | Pending |
| AUTH-07 | Phase 11 | Pending |
| AUTH-08 | Phase 11 | Pending |
| AUTH-09 | Phase 11 | Pending |
| AUTH-10 | Phase 11 | Pending |
| AUTH-11 | Phase 11 | Pending |
| ROUTES-01 | Phase 12 | Pending |
| ROUTES-02 | Phase 12 | Pending |
| ROUTES-03 | Phase 12 | Pending |
| ROUTES-04 | Phase 12 | Pending |
| ROUTES-05 | Phase 12 | Pending |
| ROUTES-06 | Phase 12 | Pending |
| ROUTES-07 | Phase 12 | Pending |
| ROUTES-08 | Phase 12 | Pending |
| ROUTES-09 | Phase 12 | Pending |
| ROUTES-10 | Phase 12 | Pending |
| ROUTES-11 | Phase 12 | Pending |
| ROUTES-12 | Phase 12 | Pending |
| DEGIRO-01 | Phase 13 | Pending |
| DEGIRO-02 | Phase 13 | Pending |
| DEGIRO-03 | Phase 13 | Pending |
| DEGIRO-04 | Phase 13 | Pending |
| DEGIRO-05 | Phase 13 | Pending |
| DEGIRO-06 | Phase 13 | Pending |
| DEGIRO-07 | Phase 13 | Pending |
| INTEG-01 | Phase 14 | Pending |
| INTEG-02 | Phase 14 | Pending |
| INTEG-03 | Phase 14 | Pending |
| INTEG-04 | Phase 14 | Pending |

**Coverage:**
- v1 requirements: 33 total
- Mapped to phases: 33
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-04*
*Last updated: 2026-05-04 after roadmap creation (phase numbers 11-14)*