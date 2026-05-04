"""Tests for API routes — Phase 12 (ROUTES-01 to ROUTES-12)."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


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