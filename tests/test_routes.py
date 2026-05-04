"""Tests for API routes — Phase 12 (ROUTES-01 to ROUTES-12)."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Clear rate limiter state before each test to prevent cross-test pollution."""
    import app.rate_limiter as rl
    with rl._store_lock:
        rl._rate_limit_store.clear()
    yield


@pytest.fixture
def with_auth_env(monkeypatch):
    """Set required env vars for route tests."""
    monkeypatch.setenv("APP_PASSWORD", "testpassword123")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-hmac")
    monkeypatch.setenv("BROKR_AUTH_TOKEN", "test-bearer-token-12345")
    monkeypatch.setenv("DEBUG", "false")


@pytest.fixture
def client(with_auth_env):
    """Return TestClient with env vars set and lifespan overridden."""
    from app.main import app
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    app.router.lifespan_context = noop_lifespan
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


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
        response = client.post("/login", data={"password": "wrongpassword"}, follow_redirects=False)
        assert response.status_code == 303
        assert "/login?failedattempt=yes" in response.headers["location"]


class TestHealthRoute:
    """ROUTES-11: GET /health returns status without auth."""

    def test_health_returns_ok(self, client):
        """ROUTES-11: GET /health returns 200 with {"status": "ok"}."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestApiAuthRoute:
    """ROUTES-03, ROUTES-04, ROUTES-05: POST /api/auth."""

    def _auth_headers(self, client):
        """Return headers with valid session cookie and bearer token."""
        from app.auth import make_session_cookie
        token, _ = make_session_cookie()
        return {
            "cookies": {"brokr_session": token},
            "headers": {"Authorization": "Bearer test-bearer-token-12345"},
        }

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


class TestApiSessionRoute:
    """ROUTES-06, ROUTES-07: POST /api/session."""

    def _session_headers(self, client):
        """Return headers with valid session cookie and bearer token."""
        from app.auth import make_session_cookie
        token, _ = make_session_cookie()
        return {
            "cookies": {"brokr_session": token},
            "headers": {"Authorization": "Bearer test-bearer-token-12345"},
        }

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


class TestSessionTokenRoute:
    """ROUTES-09, ROUTES-10: GET /api/session-token behavior."""

    def test_with_valid_session_cookie_returns_token(self, client, with_auth_env):
        """ROUTES-09: Valid session cookie returns BROKR_AUTH_TOKEN."""
        from app.auth import make_session_cookie
        token, _ = make_session_cookie()
        response = client.get("/api/session-token", cookies={"brokr_session": token})
        assert response.status_code == 200
        assert response.json() == {"token": "test-bearer-token-12345"}

    def test_without_session_cookie_redirects_to_login(self, client):
        """ROUTES-10: No session cookie returns 303 redirect to /login."""
        response = client.get("/api/session-token", follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers["location"]


class TestApiLogoutRoute:
    """ROUTES-08: POST /api/logout."""

    def test_logout_clears_session_and_returns_logged_out(self, client, with_auth_env):
        """ROUTES-08: Valid Bearer token clears session and returns {"status": "logged_out"}."""
        from app.auth import make_session_cookie
        token, _ = make_session_cookie()
        response = client.post(
            "/api/logout",
            headers={"Authorization": "Bearer test-bearer-token-12345"},
            cookies={"brokr_session": token},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "logged_out"}


class TestApiPortfolioRoute:
    """ROUTES-12: GET /api/portfolio auth behavior."""

    def test_without_bearer_token_returns_401(self, client, with_auth_env):
        """ROUTES-12: No Authorization header returns 401 (verify_brok_token rejects)."""
        from app.auth import make_session_cookie
        token, _ = make_session_cookie()
        response = client.get("/api/portfolio", cookies={"brokr_session": token})
        assert response.status_code == 401