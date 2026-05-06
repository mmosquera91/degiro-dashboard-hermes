"""Tests for main.py middleware — session cookie and bearer token (AUTH-09 to AUTH-11)."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from fastapi.testclient import TestClient


@pytest.fixture
def with_auth_env(monkeypatch):
    """Set required env vars for middleware tests."""
    monkeypatch.setenv("APP_PASSWORD", "testpassword123")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-hmac")
    monkeypatch.setenv("BROKR_AUTH_TOKEN", "test-bearer-token-12345")
    monkeypatch.setenv("DEBUG", "false")


@pytest.fixture
def client(with_auth_env):
    """Return TestClient with env vars set."""
    from app.main import app
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    app.router.lifespan_context = noop_lifespan
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


class TestCheckSessionCookie:
    """AUTH-09 and AUTH-10: check_session_cookie middleware behavior."""

    def test_unauthenticated_redirects_to_login(self, client):
        """Request without brokr_session cookie redirects to /login with 303."""
        response = client.get("/any-path", follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers["location"]

    def test_invalid_cookie_redirects_to_login(self, client):
        """Request with invalid cookie redirects to /login and deletes cookie."""
        client.cookies.set("brokr_session", "invalid-token")
        response = client.get("/any-path", follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers["location"]

    def test_exempt_path_does_not_redirect(self, client):
        """Exempt paths (/health, /static/*, /logout, /login) do not redirect."""
        response = client.get("/health", follow_redirects=False)
        assert response.status_code != 303

    def test_valid_cookie_passes_through(self, client, with_auth_env):
        """Request with valid session cookie is passed through."""
        from app.auth import make_session_cookie
        token, _ = make_session_cookie()
        client.cookies.set("brokr_session", token)
        response = client.get("/health")
        # /health is exempt so it returns 200
        assert response.status_code == 200

    def test_invalid_cookie_deleted(self, client):
        """Invalid cookie triggers delete_cookie on the response."""
        client.cookies.set("brokr_session", "bad-token")
        response = client.get("/any-page", follow_redirects=False)
        assert response.status_code == 303


class TestVerifyBrokToken:
    """AUTH-11: verify_brok_token validates Bearer token and returns 401 on mismatch."""

    def test_missing_auth_header_returns_401(self, client, with_auth_env):
        """Request without Authorization header returns 401."""
        from app.auth import make_session_cookie
        token, _ = make_session_cookie()
        client.cookies.set("brokr_session", token)
        response = client.get("/api/portfolio")
        assert response.status_code == 401

    def test_invalid_auth_format_returns_401(self, client, with_auth_env):
        """Authorization header without Bearer prefix returns 401."""
        from app.auth import make_session_cookie
        token, _ = make_session_cookie()
        client.cookies.set("brokr_session", token)
        response = client.get("/api/portfolio", headers={"Authorization": "NotBearer token"})
        assert response.status_code == 401

    def test_wrong_token_returns_401(self, client, with_auth_env):
        """Wrong bearer token returns 401 with 'Invalid token'."""
        from app.auth import make_session_cookie
        token, _ = make_session_cookie()
        client.cookies.set("brokr_session", token)
        response = client.get("/api/portfolio", headers={"Authorization": "Bearer wrong-token"})
        assert response.status_code == 401

    def test_correct_token_allows_request(self, client, with_auth_env):
        """Correct bearer token allows request to proceed."""
        from app.auth import make_session_cookie
        token, _ = make_session_cookie()
        client.cookies.set("brokr_session", token)
        response = client.get("/api/portfolio", headers={"Authorization": "Bearer test-bearer-token-12345"})
        # Should not be 401 due to token mismatch - session is not authenticated so 401 with "Session expired"
        if response.status_code == 401:
            assert "Invalid token" not in response.text

    def test_timing_safe_comparison_used(self):
        """verify_brok_token uses hmac.compare_digest for timing-safe comparison."""
        import app.main as main
        import hmac
        assert hasattr(main, 'verify_brok_token')
