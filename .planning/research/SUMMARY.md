# Project Research Summary

**Project:** brokr v1.3 Test Coverage Sprint
**Domain:** FastAPI backend test infrastructure
**Researched:** 2026-05-04
**Confidence:** HIGH

## Executive Summary

This is a FastAPI backend application (brokr) that manages portfolio data with DeGiro integration, requiring comprehensive test coverage across auth middleware, API routes, and external API clients. The recommended approach is to build test infrastructure using pytest with FastAPI TestClient, mocking external dependencies (DeGiro) while testing real authentication logic.

The core testing challenge is the lifespan startup side effects: `TestClient(app)` triggers asyncio loops (daily_enrichment_loop, daily_eod_loop) and file writes that cause tests to hang. The solution is to override the lifespan context manager or use `app.dependency_overrides` to prevent real startup code from running during tests.

Key risks: (1) Auth cookie verification requires environment variables set before app import, (2) Rate limiter tests are timing-dependent and require `monkeypatch.setattr("time.time", ...)` for deterministic behavior, (3) Middleware runs before route handlers so testing 401 responses requires separate approaches for middleware redirect vs route-level auth failures.

## Key Findings

### Recommended Stack

The testing stack uses industry-standard Python tools. pytest is the test runner with fixtures for setup/teardown. pytest-asyncio handles async route testing. FastAPI TestClient (backed by httpx) provides request simulation. unittest.mock patches external dependencies. pytest-mock provides cleaner mockito-style access. pytest-cov generates coverage reports. responses library mocks HTTP calls for external services like yfinance.

**Core technologies:**
- pytest 7+: Test runner with fixtures, parametrization, industry standard
- pytest-asyncio 0.23+: Required for testing FastAPI async routes
- httpx 0.27+: HTTP client, TestClient uses httpx under the hood
- unittest.mock: stdlib mocking, no extra install, patch decorators work well
- pytest-mock 3.12+: Cleaner mockito-like mock fixture access
- pytest-cov 4+: Coverage reporting with `--cov=app --cov-report=term-missing`

### Expected Features

**Must have (table stakes):**
- Auth cookie signing with HMAC-SHA256 and expiry — prevents session forgery
- Timing-safe comparison with hmac.compare_digest — prevents timing attacks
- Rate limiting with in-memory sliding window — brute force protection
- Session middleware for redirecting unauthenticated users — FastAPI middleware
- Bearer token validation on /api/* routes — HMAC compare_digest
- Login/logout flow with cookie-based session — standard auth pattern
- Session-token bootstrap endpoint — frontend API token acquisition
- Error responses (401, 429, 500) — proper HTTPException handling

**Should have (competitive):**
- Snapshot restoration on startup — portfolio survives restart (MEDIUM complexity)
- Operation lock (409 busy) — prevents concurrent enrichment

**Defer (v2+):**
- Daily auto-enrichment loop testing — HIGH complexity, requires asyncio task mocking
- Testing /api/portfolio with real trading_api — requires deeper mock setup
- Benchmark cache invalidation — secondary feature

### Architecture Approach

The application uses a middleware stack (bottom to top): check_session_cookie, add_security_headers, CORS middleware. Routes are split by auth level: open routes (/login, /logout, /static/*, /health) vs protected routes (/api/* with verify_brok_token and check_rate_limit).

**Major components:**
1. **auth.py** — HMAC cookie signing/verification, pure unit tests with monkeypatch
2. **rate_limiter.py** — IP-based rate limiting, unit tests with fake time
3. **main.py middleware** — Session cookie check, security headers, TestClient with cookies
4. **main.py routes** — API endpoints, TestClient with mocked DeGiro
5. **degiro_client.py** — DeGiro API calls, fully mocked unit tests

### Critical Pitfalls

1. **TestClient with app.lifecycle events** — Triggers lifespan asyncio tasks that hang tests. Use lifespan context manager override or `app.dependency_overrides[get_portfolio] = mock_get_portfolio`.
2. **Auth cookie environment variables not set** — verify_session_cookie calls _get_secret() which reads APP_PASSWORD and SECRET_KEY. Set in conftest.py before importing app.
3. **Timing-dependent rate limiter tests** — _clean_old_timestamps uses time.time(), tests fail with timing variance. Patch with `monkeypatch.setattr("time.time", fake_time)`.
4. **Middleware with TestClient path order** — check_session_cookie runs before route, can't test route-level 401 via middleware redirect. Test middleware redirect separately from route auth errors.
5. **DeGiroClient methods called during test setup** — Module-level import of DeGiroClient causes side effects. Mock at the right level with `monkeypatch.setattr("app.main.DeGiroClient", mock)`.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Auth Infrastructure Tests
**Rationale:** Auth and rate limiting are foundational — all other tests depend on correct environment setup. These tests expose critical pitfalls around lifespan startup, env vars, and timing.
**Delivers:** conftest.py with env vars, test_auth.py unit tests, test_rate_limiter.py unit tests, test_middleware.py
**Addresses:** Auth cookie signing, timing-safe comparison, rate limiting, session middleware
**Avoids:** Pitfall 1 (lifespan override), Pitfall 2 (env vars), Pitfall 3 (monkeypatch time)

### Phase 2: API Route Tests
**Rationale:** Routes depend on auth infrastructure being tested first. This phase tests the actual endpoints users interact with.
**Delivers:** test_routes_auth.py (/login, /logout), test_routes_api.py (/api/auth, /api/session, /api/session-token), integration test for login -> session-token -> protected endpoint
**Addresses:** Bearer token validation, login/logout flow, session-token bootstrap, error responses 401/429/500
**Avoids:** Pitfall 4 (middleware redirect vs route auth separation)

### Phase 3: External Client Tests
**Rationale:** DeGiroClient testing requires deeper mocking setup and is less critical for launch. Operation lock tests can be added here.
**Delivers:** test_degiro_client.py with mocked methods, test_operation_lock
**Addresses:** DeGiro auth, portfolio fetch mocking
**Avoids:** Pitfall 5 (mock at correct level)

### Phase Ordering Rationale

- Auth infrastructure must be tested first because all routes depend on it
- Routes must be tested before external clients since routes use those clients
- Daily enrichment loop and snapshot restoration deferred due to HIGH complexity and asyncio task mocking requirements
- Integration tests run last after all components are individually tested

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (External Client Tests):** DeGiroClient has module-level side effects, may need additional mock setup research

Phases with standard patterns (skip research-phase):
- **Phase 1 (Auth Infrastructure):** Well-documented FastAPI testing patterns, pytest fixtures
- **Phase 2 (API Route Tests):** Standard TestClient patterns, covered by FastAPI docs

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Based on FastAPI official testing docs and pytest documentation |
| Features | HIGH | Based on existing codebase analysis and feature landscape |
| Architecture | HIGH | Based on FastAPI testing patterns and codebase structure |
| Pitfalls | HIGH | Based on FastAPI known issues and pytest-asyncio known issues |

**Overall confidence:** HIGH

### Gaps to Address

- **asyncio task mocking in lifespan:** How to properly mock asyncio.create_task for daily_enrichment_loop and daily_eod_loop — may need research-phase during Phase 3 planning
- **responses library for yfinance:** If yfinance is used in production, how responses library handles async HTTP calls needs validation

## Sources

### Primary (HIGH confidence)
- FastAPI Testing docs — https://fastapi.tiangolo.com/tutorial/testing/
- pytest-asyncio known issues — https://github.com/pytest-dev/pytest-asyncio
- pytest fixtures — https://docs.pytest.org/en/stable/fixture.html

### Secondary (MEDIUM confidence)
- pytest-mock — https://pytest-mock.readthedocs.io/
- unittest.mock — https://docs.python.org/3/library/unittest.mock.html
- responses library — https://github.com/getsentry/responses

### Tertiary (LOW confidence)
- DeGiroClient module-level side effects — inferred, needs validation during Phase 3 implementation

---
*Research completed: 2026-05-04*
*Ready for roadmap: yes*
