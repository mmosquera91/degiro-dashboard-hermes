# Phase 12: API Route Tests - Research

**Researched:** 2026-05-04
**Domain:** FastAPI route testing with TestClient, session cookies, bearer token auth
**Confidence:** HIGH

## Summary

Phase 12 tests all API endpoints in main.py for correct response to valid/invalid requests and error conditions. The application uses FastAPI's TestClient with a noop lifespan override to avoid snapshot restore side effects. Routes require either session cookie auth (browser flow via middleware) or Bearer token auth (API flow via dependency). Key testing patterns: mocking DeGiroClient errors, checking redirect behavior, validating JSON responses, and testing error conditions (401/500).

**Primary recommendation:** Use TestClient with lifespan override pattern established in Phase 11 test_middleware.py. Create `tests/test_routes.py` organized by route group (auth, session, health, portfolio). Mock DeGiroClient at the import level to test error paths.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| POST /login | API/Backend | — | Session cookie creation, HTTP redirect |
| POST /api/auth | API/Backend | — | DeGiro auth, returns JSON status |
| POST /api/session | API/Backend | — | Session validation, returns JSON status |
| POST /api/logout | API/Backend | — | Session clearing, returns JSON status |
| GET /api/session-token | API/Backend | — | Returns token JSON, relies on middleware |
| GET /health | API/Backend | — | Open endpoint, no auth |
| GET /api/portfolio | API/Backend | — | Requires Bearer token, returns portfolio JSON |

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ROUTES-01 | POST /login with correct password sets brokr_session cookie and redirects to / | TestClient POST with form data, check cookies + redirect |
| ROUTES-02 | POST /login with wrong password redirects to /login?failedattempt=yes | TestClient POST with wrong password, check redirect URL |
| ROUTES-03 | POST /api/auth with valid credentials returns {"status": "authenticated"} | Mock DeGiroClient.authenticate, test JSON response |
| ROUTES-04 | POST /api/auth with ConnectionError returns 401 | Mock DeGiroClient.authenticate to raise ConnectionError |
| ROUTES-05 | POST /api/auth with generic error returns 500 | Mock DeGiroClient.authenticate to raise generic Exception |
| ROUTES-06 | POST /api/session with valid session_id returns {"status": "authenticated"} | Mock DeGiroClient.from_session_id |
| ROUTES-07 | POST /api/session with ConnectionError returns 401 | Mock DeGiroClient.from_session_id to raise ConnectionError |
| ROUTES-08 | POST /api/logout clears session and returns {"status": "logged_out"} | TestClient post, verify JSON response |
| ROUTES-09 | GET /api/session-token returns BROKR_AUTH_TOKEN (bootstrap endpoint) | TestClient GET with valid session cookie, check token in response |
| ROUTES-10 | GET /api/session-token without session cookie returns redirect to /login | TestClient GET without cookie, check 303 redirect |
| ROUTES-11 | GET /health returns {"status": "ok"} without auth | TestClient GET, no auth needed (exempt path) |
| ROUTES-12 | GET /api/portfolio without auth token returns 401 | TestClient GET without Bearer header, check 401 |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | latest | Test framework | Project standard |
| fastapi.testclient.TestClient | bundled with FastAPI | HTTP route testing | Project standard (used in test_middleware.py) |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| unittest.mock.patch | stdlib | Mocking DeGiroClient methods | Testing error paths (ROUTES-04, ROUTES-05, ROUTES-07) |
| contextlib.asynccontextmanager | stdlib | Lifespan override | Prevent snapshot restore during tests |

**Installation:** No new packages needed — all available in project.

## Architecture Patterns

### System Architecture Diagram

```
Browser/Client
     │
     ▼ POST /login (form) or GET /health
FastAPI App (main.py)
     │
     ├── check_session_cookie middleware (redirects unauthenticated to /login)
     │        │
     │        ▼ Session cookie valid ──► call_next
     │
     ├── verify_brok_token dependency (checks Bearer token on /api/*)
     │        │
     │        ▼ Token valid ──► route handler
     │
     └── Route handlers
              ├── /login POST ──► RedirectResponse (303)
              ├── /api/auth POST ──► DeGiroClient.authenticate
              ├── /api/session POST ──► DeGiroClient.from_session_id
              ├── /api/logout POST ──► clear session, return JSON
              ├── /api/session-token GET ──► return token (middleware auth)
              ├── /health GET ──► return JSON (no auth)
              └── /api/portfolio GET ──► return portfolio (Bearer auth)
```

### Recommended Project Structure

```
tests/
├── conftest.py           # Existing fixtures (auth_module, sample_token, etc.)
├── test_routes.py        # NEW: API route tests for ROUTES-01 to ROUTES-12
├── test_middleware.py    # Existing: middleware tests
└── test_auth.py          # Existing: auth unit tests
```

### Pattern 1: TestClient with Lifespan Override

From test_middleware.py:

```python
from contextlib import asynccontextmanager

@pytest.fixture
def client(with_auth_env):
    """Return TestClient with env vars set and lifespan overridden."""
    from app.main import app

    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    app.router.lifespan_context = noop_lifespan
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
```

**Why:** Prevents snapshot restore side effects from executing during tests. Required for all route tests.

### Pattern 2: Route Test Structure

```python
class TestLoginRoute:
    """ROUTES-01, ROUTES-02: POST /login behavior."""

    def test_correct_password_redirects_to_home(self, client):
        """ROUTES-01: Correct password sets cookie and redirects to /."""
        response = client.post("/login", data={"password": "testpassword123"}, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/"
        assert "brokr_session" in response.cookies

    def test_wrong_password_redirects_with_flag(self, client):
        """ROUTES-02: Wrong password redirects to /login?failedattempt=yes."""
        response = client.post("/login", data={"password": "wrong"}, follow_redirects=False)
        assert response.status_code == 303
        assert "/login?failedattempt=yes" in response.headers["location"]
```

### Pattern 3: API Error Path Testing

```python
class TestApiAuthRoute:
    """ROUTES-03, ROUTES-04, ROUTES-05: POST /api/auth."""

    def test_valid_credentials_returns_authenticated(self, client, with_auth_env):
        """ROUTES-03: Valid credentials return status authenticated."""
        with patch("app.main.DeGiroClient.authenticate") as mock_auth:
            mock_auth.return_value = MagicMock()
            response = client.post("/api/auth", json={"username": "user", "password": "pass"})
            assert response.status_code == 200
            assert response.json() == {"status": "authenticated"}

    def test_connection_error_returns_401(self, client, with_auth_env):
        """ROUTES-04: ConnectionError from DeGiroClient returns 401."""
        with patch("app.main.DeGiroClient.authenticate") as mock_auth:
            mock_auth.side_effect = ConnectionError("Failed")
            response = client.post("/api/auth", json={"username": "user", "password": "pass"})
            assert response.status_code == 401

    def test_generic_error_returns_500(self, client, with_auth_env):
        """ROUTES-05: Generic exception returns 500."""
        with patch("app.main.DeGiroClient.authenticate") as mock_auth:
            mock_auth.side_effect = RuntimeError("Unexpected")
            response = client.post("/api/auth", json={"username": "user", "password": "pass"})
            assert response.status_code == 500
```

### Pattern 4: Session Cookie Auth Test

```python
class TestSessionTokenRoute:
    """ROUTES-09, ROUTES-10: GET /api/session-token."""

    def test_with_valid_session_cookie_returns_token(self, client, with_auth_env):
        """ROUTES-09: Valid session cookie returns BROKR_AUTH_TOKEN."""
        from app.auth import make_session_cookie
        token, _ = make_session_cookie()
        response = client.get("/api/session-token", cookies={"brokr_session": token})
        assert response.status_code == 200
        assert "token" in response.json()

    def test_without_session_cookie_redirects_to_login(self, client):
        """ROUTES-10: No session cookie returns 303 redirect to /login."""
        response = client.get("/api/session-token", follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers["location"]
```

### Pattern 5: Bearer Token Auth Test

```python
class TestPortfolioRoute:
    """ROUTES-12: GET /api/portfolio auth behavior."""

    def test_without_bearer_token_returns_401(self, client, with_auth_env):
        """ROUTES-12: No Authorization header returns 401."""
        # Session cookie present but no Bearer token
        from app.auth import make_session_cookie
        session_token, _ = make_session_cookie()
        response = client.get("/api/portfolio", cookies={"brokr_session": session_token})
        assert response.status_code == 401
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|------------|-------------|-----|
| Session mocking | Build fake session storage | Use actual in-memory _session dict | Already in-memory, no setup needed |
| DeGiro error paths | Call real DeGiroClient | unittest.mock.patch | Real calls need live credentials |
| Lifespan side effects | Try to stop lifespan | Override lifespan_context | Verified pattern from Phase 11 |

## Common Pitfalls

### Pitfall 1: TestClient lifespan startup side effects
**What goes wrong:** TestClient launches app lifespan, which runs `_restore_portfolio_from_snapshot()` causing file I/O errors in tests.
**Why it happens:** Tests don't have snapshot files, lifespan still tries to restore.
**How to avoid:** Always override `app.router.lifespan_context` with noop as shown in Pattern 1.
**Warning signs:** `FileNotFoundError`, `JSONDecodeError` in test output, tests hang.

### Pitfall 2: Auth dependency ordering
**What goes wrong:** `check_session_cookie` middleware runs before route-level `Depends(verify_brok_token)`, so route tests with session cookie but no Bearer get past middleware but fail at dependency.
**How to avoid:** Use session cookie fixture for middleware-tested routes, use Bearer header for dependency-tested routes separately.
**Warning signs:** 401 from session cookie middleware when testing API routes with session cookie.

### Pitfall 3: Form data vs JSON body
**What goes wrong:** POST /login expects form data (`request.form()`), but test sends JSON.
**How to avoid:** Use `client.post("/login", data={...})` not `client.post("/login", json={...})`.
**Warning signs:** `422 Unprocessable Entity` on /login tests.

### Pitfall 4: Port conflict with real running server
**What goes wrong:** Tests fail because port 8000 already in use by running `uvicorn app.main:app`.
**How to avoid:** TestClient binds to random port by default; ensure no conflicting server running.
**Warning signs:** `OSError: [Errno 98] Address already in use`.

## Code Examples

### Minimal route test setup:
```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

@pytest.fixture
def client(with_auth_env):
    from app.main import app
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    app.router.lifespan_context = noop_lifespan
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Real HTTP client (requests) | FastAPI TestClient | FastAPI adoption | Test isolation, no server needed |
| Manual session management | In-memory _session dict | Phase 8 | Simple testing, no DB |
| Live DeGiro calls in tests | Mock with patch | Phase 11 | Fast, deterministic tests |

**Deprecated/outdated:**
- pytest-flask (replaced by TestClient)
- unittest2 (replaced by pytest)

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.x | Runtime | ✓ | 3.x | — |
| pytest | Testing | ✓ | latest | — |
| FastAPI TestClient | Route testing | ✓ | bundled | — |
| DeGiroClient | Auth route tests | ✓ | app.degiro_client | Mock with patch |

**Missing dependencies with no fallback:**
- None — all needed tools available.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Session cookie + Bearer token (tested by routes) |
| V3 Session Management | yes | Cookie attributes, session clearing |
| V4 Access Control | yes | 401 on missing/invalid auth |
| V5 Input Validation | yes | FastAPI Pydantic models (AuthRequest, SessionRequest) |

### Known Threat Patterns for FastAPI Routes

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Brute force /login | Information Disclosure | Rate limiting (check_rate_limit dependency) |
| Invalid bearer token | Spoofing | 401 returned, hmac.compare_digest timing-safe |
| Session cookie tampering | Tampering | HMAC signature verification in verify_session_cookie |
| Missing auth on protected route | Information Disclosure | verify_brok_token dependency, middleware redirect |

## Sources

### Primary (HIGH confidence)
- Phase 11 test_middleware.py — confirmed lifespan override pattern
- app/main.py — route implementations, dependencies, middleware chain
- tests/conftest.py — existing fixtures (auth_module, sample_token, mock_auth_env)

### Secondary (MEDIUM confidence)
- FastAPI TestClient documentation — testing patterns
- app/auth.py — session cookie creation/verification

### Tertiary (LOW confidence)
- None — all key patterns verified from existing project code.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — pytest and TestClient are project standard
- Architecture: HIGH — pattern confirmed in test_middleware.py
- Pitfalls: HIGH — all pitfalls identified from project-specific issues (lifespan, form vs json)

**Research date:** 2026-05-04
**Valid until:** 30 days (stable domain)