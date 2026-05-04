---
phase: 12-api-route-tests
plan: "03"
subsystem: tests
tags: [routes, auth, tdd]
dependency_graph:
  requires: ["12-01", "12-02"]
  provides: ["ROUTES-03", "ROUTES-04", "ROUTES-05"]
  affects: ["app/main.py"]
tech_stack:
  added: []
  patterns: [tdd, bearer-token-auth, session-cookie-auth, DeGiroClient-mock]
key_files:
  created: []
  modified:
    - tests/test_routes.py
decisions:
  - id: "auth-header-fix"
    description: "Added both session cookie and bearer token to test requests — /api/auth requires verify_brok_token dependency AND check_session_cookie middleware"
    rationale: "Middleware checks for session cookie; verify_brok_token dependency checks Authorization header"
    outcome: "Tests pass with both auth mechanisms present"
metrics:
  duration: "~5 minutes"
  completed_date: "2026-05-04"
---

# Phase 12 Plan 03 Summary: POST /api/auth Route Tests

## One-liner

POST /api/auth endpoint verified with 3 passing tests (ROUTES-03, ROUTES-04, ROUTES-05) covering valid credentials, ConnectionError, and generic error paths.

## Tasks Executed

| # | Name | Type | Commit | Result |
|---|------|------|--------|--------|
| 1 | Write auth route tests (RED) | tdd | 2f9c949 | 3 tests added (failing) |
| 2 | Fix auth headers, verify tests pass (GREEN) | auto | 8dabb2f | 3 tests pass |

## Must-Haves: Verified

### Truths

- POST /api/auth with valid credentials returns `{"status": "authenticated"}`
  - Route: `app/main.py:569` - `auth()` endpoint
  - Catches `ConnectionError` -> 401, generic `Exception` -> 500
  - Requires both session cookie (middleware) and bearer token (dependency)
- POST /api/auth with ConnectionError returns 401
  - `DeGiroClient.authenticate` raises `ConnectionError` when DeGiro is unreachable
- POST /api/auth with generic RuntimeError returns 500
  - Catches all other exceptions as fallback error handling

### Artifacts

| Path | Provides | Lines Added |
|------|----------|-------------|
| tests/test_routes.py | API auth route tests with DeGiroClient mocking | 33 |

## TDD Gate Compliance

- `test(12-03)` RED commit: 2f9c949
- `feat(12-03)` GREEN commit: 8dabb2f
- Both commits present in git log

## Test Results

```
tests/test_routes.py::TestApiAuthRoute::test_valid_credentials_returns_authenticated PASSED
tests/test_routes.py::TestApiAuthRoute::test_connection_error_returns_401 PASSED
tests/test_routes.py::TestApiAuthRoute::test_generic_error_returns_500 PASSED
======================== 8 passed, 6 warnings in 0.43s =========================
```

## Key Test Code

```python
class TestApiAuthRoute:
    """ROUTES-03, ROUTES-04, ROUTES-05: POST /api/auth."""

    def test_valid_credentials_returns_authenticated(self, client, with_auth_env):
        """ROUTES-03: Valid credentials return {"status": "authenticated"}."""
        from app.auth import make_session_cookie
        token, _ = make_session_cookie()
        with patch("app.main.DeGiroClient.authenticate") as mock_auth:
            mock_auth.return_value = MagicMock()
            response = client.post(
                "/api/auth",
                json={"username": "user", "password": "pass"},
                cookies={"brokr_session": token},
                headers={"Authorization": "Bearer test-bearer-token-12345"},
            )
            assert response.status_code == 200
            assert response.json() == {"status": "authenticated"}

    def test_connection_error_returns_401(self, client, with_auth_env):
        """ROUTES-04: ConnectionError from DeGiroClient returns 401."""
        from app.auth import make_session_cookie
        token, _ = make_session_cookie()
        with patch("app.main.DeGiroClient.authenticate") as mock_auth:
            mock_auth.side_effect = ConnectionError("DeGiro connection failed")
            response = client.post(
                "/api/auth",
                json={"username": "user", "password": "pass"},
                cookies={"brokr_session": token},
                headers={"Authorization": "Bearer test-bearer-token-12345"},
            )
            assert response.status_code == 401

    def test_generic_error_returns_500(self, client, with_auth_env):
        """ROUTES-05: Generic exception returns 500."""
        from app.auth import make_session_cookie
        token, _ = make_session_cookie()
        with patch("app.main.DeGiroClient.authenticate") as mock_auth:
            mock_auth.side_effect = RuntimeError("Unexpected error")
            response = client.post(
                "/api/auth",
                json={"username": "user", "password": "pass"},
                cookies={"brokr_session": token},
                headers={"Authorization": "Bearer test-bearer-token-12345"},
            )
            assert response.status_code == 500
```

## Deviations from Plan

**Rule 2 - Auto-added critical functionality:** Tests required both session cookie and bearer token to pass through middleware + dependency chain.

## Deferred Issues

None.

## Threat Flags

None.

---

**Commits in this plan:**

| Hash | Message |
|------|---------|
| 2f9c949 | test(12-03): add failing tests for POST /api/auth route (ROUTES-03, ROUTES-04, ROUTES-05) |
| 8dabb2f | feat(12-03): POST /api/auth route tests passing (ROUTES-03, ROUTES-04, ROUTES-05) |

## Self-Check

- [x] tests/test_routes.py contains TestApiAuthRoute with 3 tests
- [x] All 3 tests pass
- [x] Commits 2f9c949 and 8dabb2f exist in git log
- [x] SUMMARY.md created in .planning/phases/12-api-route-tests/

**Self-Check: PASSED**