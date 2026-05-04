# Roadmap: Brokr v1.3 Test Coverage Sprint

## Overview

Bump backend test coverage from ~30% to ~75-80%, targeting auth middleware, API routes, DeGiro client mocking, and integration flows. Start at Phase 11 (continuing from v1.1's last phase 10).

## Phases

- [ ] **Phase 11: Auth Infrastructure Tests** - conftest.py, auth.py unit tests, rate_limiter.py unit tests, middleware tests
- [ ] **Phase 12: API Route Tests** - login/logout, session-token bootstrap, error responses, auth endpoints
- [ ] **Phase 13: DeGiro Client Tests** - mocked client tests, portfolio parsing edge cases
- [ ] **Phase 14: Integration Tests** - end-to-end flows, cookie validation chain, unauthorized redirect chain

## Phase Details

### Phase 11: Auth Infrastructure Tests
**Goal**: auth.py HMAC signing, rate limiting logic, and session middleware work correctly
**Depends on**: Nothing (first phase of this milestone)
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06, AUTH-07, AUTH-08, AUTH-09, AUTH-10, AUTH-11
**Success Criteria** (what must be TRUE):
  1. auth.py creates HMAC-SHA256 signed tokens with expiry that verify correctly
  2. auth.py rejects expired tokens and invalid signatures using timing-safe comparison
  3. auth.py sets Secure, HttpOnly, SameSite=Lax cookie attributes correctly
  4. auth.py clears session cookies with correct delete_cookie kwargs
  5. rate_limiter.py allows up to 5 requests per 60 seconds per IP
  6. rate_limiter.py returns 429 after limit exceeded with correct headers
  7. rate_limiter.py cleans timestamps outside the sliding window
  8. check_session_cookie middleware redirects unauthenticated requests to /login
  9. check_session_cookie middleware passes valid session cookies through
  10. verify_brok_token validates Bearer tokens and returns 401 on mismatch
**Plans**: TBD

### Phase 12: API Route Tests
**Goal**: All API endpoints respond correctly to valid/invalid requests and error conditions
**Depends on**: Phase 11
**Requirements**: ROUTES-01, ROUTES-02, ROUTES-03, ROUTES-04, ROUTES-05, ROUTES-06, ROUTES-07, ROUTES-08, ROUTES-09, ROUTES-10, ROUTES-11, ROUTES-12
**Success Criteria** (what must be TRUE):
  1. POST /login with correct password sets brokr_session cookie and redirects to /
  2. POST /login with wrong password redirects to /login?failedattempt=yes
  3. POST /api/auth returns authenticated status with valid credentials
  4. POST /api/auth returns 401 on ConnectionError from DeGiro
  5. POST /api/auth returns 500 on generic errors
  6. POST /api/session validates session_id and returns authenticated status
  7. POST /api/session returns 401 on ConnectionError
  8. POST /api/logout clears session and returns logged_out status
  9. GET /api/session-token returns BROKR_AUTH_TOKEN when session cookie present
  10. GET /api/session-token redirects to /login when no session cookie
  11. GET /health returns {"status": "ok"} without requiring auth
  12. GET /api/portfolio returns 401 when no auth token provided
**Plans**: TBD

### Phase 13: DeGiro Client Tests
**Goal**: DeGiroClient methods handle edge cases and errors correctly with mocked HTTP
**Depends on**: Phase 12
**Requirements**: DEGIRO-01, DEGIRO-02, DEGIRO-03, DEGIRO-04, DEGIRO-05, DEGIRO-06, DEGIRO-07
**Success Criteria** (what must be TRUE):
  1. _kv_list_to_dict converts {"key", "value"} list format to flat dict correctly
  2. from_session_id accepts session_id + optional int_account and returns TradingAPI
  3. from_session_id raises ConnectionError on invalid session
  4. fetch_portfolio returns dict with positions and cash_available
  5. fetch_portfolio raises ConnectionError when session expired (2FA/anti-bot)
  6. Portfolio parsing handles empty positions list without crashing
  7. Portfolio parsing handles missing optional fields gracefully
**Plans**: TBD

### Phase 14: Integration Tests
**Goal**: End-to-end auth flows and cookie validation chain work correctly
**Depends on**: Phase 13
**Requirements**: INTEG-01, INTEG-02, INTEG-03, INTEG-04
**Success Criteria** (what must be TRUE):
  1. login flow -> session-token -> protected endpoint works end-to-end with cookie
  2. Cookie validation chain: middleware checks cookie -> verify_brok_token checks Bearer token
  3. Unauthorized request to /api/* redirects to /login returning 303
  4. Expired cookie is cleared and redirect to /login occurs
**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 11. Auth Infrastructure Tests | 0/? | Not started | - |
| 12. API Route Tests | 0/? | Not started | - |
| 13. DeGiro Client Tests | 0/? | Not started | - |
| 14. Integration Tests | 0/? | Not started | - |

---

*Roadmap created: 2026-05-04*
*Granularity: coarse*