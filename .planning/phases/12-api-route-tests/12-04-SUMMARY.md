---
phase: 12-api-route-tests
plan: "04"
subsystem: tests
tags: [routes, session, tdd]
dependency_graph:
  requires: ["12-03"]
  provides: ["ROUTES-06", "ROUTES-07"]
  affects: ["app/main.py"]
tech_stack:
  added: []
  patterns: [tdd, bearer-token-auth, session-cookie-auth, DeGiroClient-mock]
key_files:
  created: []
  modified:
    - tests/test_routes.py
decisions:
  - id: "session-auth-requires-cookie"
    description: "POST /api/session requires both session cookie (middleware) and bearer token (dependency) like /api/auth"
    rationale: "Middleware check_session_cookie redirects to /login if no cookie, even when bearer token is valid"
    outcome: "Tests pass when both session cookie and bearer token are included"
  - id: "rate-limiter-reset"
    description: "Added autouse fixture to reset rate_limiter._rate_limit_store before each test"
    rationale: "In-memory rate limiter store persisted between tests, causing 429 responses when tests ran in sequence"
    outcome: "All 10 tests pass reliably"
metrics:
  duration: "~5 minutes"
  completed_date: "2026-05-04"
---

# Phase 12 Plan 04 Summary: POST /api/session Route Tests

## One-liner

POST /api/session endpoint verified with 2 passing tests (ROUTES-06, ROUTES-07) covering valid session_id and ConnectionError paths.

## Tasks Executed

| # | Name | Type | Commit | Result |
|---|------|------|--------|--------|
| 1 | Write session route tests | tdd | 1372e03 | 2 tests added (route already implemented) |
| 2 | Fix rate limiter cross-test pollution | auto | 8f35fa2 | All 10 tests pass |

## Must-Haves: Verified

### Truths

- POST /api/session with valid session_id returns `{"status": "authenticated"}`
  - Route: `app/main.py:593-617` - `session_auth()` endpoint
  - Calls `DeGiroClient.from_session_id(session_id, int_account=int_account)`
  - Catches `ConnectionError` -> 401, generic `Exception` -> 500
  - Requires both session cookie (middleware) and bearer token (dependency)
- POST /api/session with ConnectionError returns 401
  - `DeGiroClient.from_session_id` raises `ConnectionError` when session is invalid/expired

### Artifacts

| Path | Provides | Lines Added |
|------|----------|-------------|
| tests/test_routes.py | API session route tests with DeGiroClient.from_session_id mocking | 42 |

## Test Results

```
tests/test_routes.py::TestApiSessionRoute::test_valid_session_id_returns_authenticated PASSED
tests/test_routes.py::TestApiSessionRoute::test_connection_error_returns_401 PASSED
======================== 10 passed, 8 warnings in 0.44s =========================
```

## Key Test Code

```python
class TestApiSessionRoute:
    """ROUTES-06, ROUTES-07: POST /api/session."""

    def test_valid_session_id_returns_authenticated(self, client, with_auth_env):
        """ROUTES-06: Valid session_id returns {"status": "authenticated"}."""
        from app.auth import make_session_cookie
        token, _ = make_session_cookie()
        with patch("app.main.DeGiroClient.from_session_id") as mock_session:
            mock_session.return_value = MagicMock()
            response = client.post(
                "/api/session",
                json={"session_id": "valid-session-123"},
                cookies={"brokr_session": token},
                headers={"Authorization": "Bearer test-bearer-token-12345"},
            )
            assert response.status_code == 200
            assert response.json() == {"status": "authenticated"}

    def test_connection_error_returns_401(self, client, with_auth_env):
        """ROUTES-07: ConnectionError from DeGiroClient.from_session_id returns 401."""
        from app.auth import make_session_cookie
        token, _ = make_session_cookie()
        with patch("app.main.DeGiroClient.from_session_id") as mock_session:
            mock_session.side_effect = ConnectionError("Session expired")
            response = client.post(
                "/api/session",
                json={"session_id": "invalid-session"},
                cookies={"brokr_session": token},
                headers={"Authorization": "Bearer test-bearer-token-12345"},
            )
            assert response.status_code == 401
```

## Deviations from Plan

**Rule 2 - Auto-added critical functionality:**
1. Tests required both session cookie AND bearer token to pass through middleware + dependency chain (same pattern as ROUTES-03 fix in plan 12-03)
2. Discovered rate limiter cross-test pollution (429 errors when tests ran together) — added `reset_rate_limiter` autouse fixture

**TDD Gate note:** The plan specified RED/GREEN pattern (tests must fail first, then pass). However, `session_auth` endpoint was already correctly implemented in `app/main.py`, so tests passed on first run. The TDD RED commit was skipped per the "tests must fail" gate enforcement rule — since tests passed without any implementation changes, proceeding to GREEN commit was appropriate.

## Deferred Issues

None.

## Threat Flags

None.

---

**Commits in this plan:**

| Hash | Message |
|------|---------|
| 1372e03 | feat(12-04): add POST /api/session route tests (ROUTES-06, ROUTES-07) |
| 8f35fa2 | fix(tests): add rate_limiter state reset to prevent cross-test pollution |

## Self-Check

- [x] tests/test_routes.py contains TestApiSessionRoute with 2 tests
- [x] All 10 tests in test_routes.py pass
- [x] Commits 1372e03 and 8f35fa2 exist in git log
- [x] SUMMARY.md created in .planning/phases/12-api-route-tests/

**Self-Check: PASSED**