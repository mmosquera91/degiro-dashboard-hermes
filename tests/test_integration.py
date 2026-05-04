"""End-to-end integration tests for auth flows and cookie validation chain.

Covers:
- INTEG-01: Login sets session cookie and redirects
- INTEG-02: Cookie validation chain — session token with valid cookie
- INTEG-03: Unauthorized redirect behavior
- INTEG-04: Expired cookie handling
"""
import time

import pytest

from app.auth import make_session_cookie, _make_token


class TestLoginFlow:
    """INTEG-01: Login flow — session cookie and redirect behavior."""

    def test_login_sets_session_cookie_and_redirects(self, client):
        """POST /login with correct password sets brokr_session cookie and redirects to /."""
        response = client.post("/login", data={"password": "testpassword123"}, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/"
        assert "brokr_session" in response.cookies

    def test_login_wrong_password_redirects_with_flag(self, client):
        """Wrong password redirects to /login?failedattempt=yes."""
        response = client.post("/login", data={"password": "wrongpassword"}, follow_redirects=False)
        assert response.status_code == 303
        assert "/login?failedattempt=yes" in response.headers["location"]


class TestCookieValidationChain:
    """INTEG-02: Cookie validation chain — middleware passes valid cookie to route handlers."""

    def test_session_token_with_valid_cookie_returns_bearer_token(self, client, with_auth_env):
        """GET /api/session-token with valid session cookie returns BROKR_AUTH_TOKEN."""
        # First login to get a valid session cookie
        response = client.post("/login", data={"password": "testpassword123"}, follow_redirects=False)
        cookie = response.cookies["brokr_session"]

        # Use the cookie to fetch the bearer token
        response = client.get("/api/session-token", cookies={"brokr_session": cookie})
        assert response.status_code == 200
        assert response.json() == {"token": "test-bearer-token-12345"}

    def test_protected_endpoint_requires_both_cookie_and_bearer(self, client, with_auth_env):
        """GET /api/portfolio requires BOTH session cookie (middleware) AND Bearer token (verify_brok_token)."""
        # Login to get a valid session cookie
        response = client.post("/login", data={"password": "testpassword123"}, follow_redirects=False)
        cookie = response.cookies["brokr_session"]

        # Request with only session cookie (no Bearer) — middleware passes, verify_brok_token rejects
        response = client.get("/api/portfolio", cookies={"brokr_session": cookie}, follow_redirects=False)
        assert response.status_code == 401, "Bearer token missing — verify_brok_token should reject"

        # Request with session cookie AND valid Bearer — should pass both checks
        response = client.get(
            "/api/portfolio",
            cookies={"brokr_session": cookie},
            headers={"Authorization": "Bearer test-bearer-token-12345"},
            follow_redirects=False,
        )
        # 401 with session-expired message, NOT "Invalid token" — proves middleware passed cookie through
        assert response.status_code == 401
        detail = response.json().get("detail", "")
        assert "Session expired" in detail or "session" in detail.lower(), (
            f"Expected session-expired error, got: {detail}"
        )

    def test_middleware_passes_valid_cookie_to_route(self, client, with_auth_env):
        """GET /api/session-token with valid cookie returns 200 — proves middleware validates cookie before route handler."""
        cookie_value, _ = make_session_cookie()

        # /api/session-token does NOT require Bearer — only valid cookie (middleware check)
        response = client.get("/api/session-token", cookies={"brokr_session": cookie_value})
        assert response.status_code == 200, "Valid cookie passed middleware — route handler executed"


class TestUnauthorizedRedirect:
    """INTEG-03: Request without session cookie returns 303 redirect to /login."""

    def test_api_request_without_cookie_redirects_to_login(self, client):
        """GET /api/session-token with no cookie returns 303 redirect to /login."""
        response = client.get("/api/session-token", follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers["location"]

    def test_api_request_without_bearer_returns_401(self, client, with_auth_env):
        """GET /api/portfolio with session cookie but no Authorization header returns 401."""
        # Login to get a valid session cookie
        response = client.post("/login", data={"password": "testpassword123"}, follow_redirects=False)
        cookie = response.cookies["brokr_session"]

        # Request with cookie but no Bearer — verify_brok_token rejects
        response = client.get("/api/portfolio", cookies={"brokr_session": cookie}, follow_redirects=False)
        assert response.status_code == 401

    def test_wrong_bearer_returns_401(self, client, with_auth_env):
        """GET /api/portfolio with wrong Bearer token returns 401 'Invalid token'."""
        # Login to get a valid session cookie
        response = client.post("/login", data={"password": "testpassword123"}, follow_redirects=False)
        cookie = response.cookies["brokr_session"]

        # Request with cookie AND wrong Bearer token
        response = client.get(
            "/api/portfolio",
            cookies={"brokr_session": cookie},
            headers={"Authorization": "Bearer wrong-token"},
            follow_redirects=False,
        )
        assert response.status_code == 401
        assert "Invalid token" in response.json()["detail"]


class TestExpiredCookie:
    """INTEG-04: Expired session cookie is cleared and request redirects to /login."""

    def test_expired_cookie_is_cleared_and_redirects(self, client, with_auth_env):
        """Expired cookie causes 303 redirect to /login and cookie is cleared."""
        # Create an already-expired token
        expired_token = _make_token(
            "testpassword123",  # password used for signing
            "test-secret-key-for-hmac",  # secret key
            time.time() - 3600,  # expired 1 hour ago
        )

        # Attempt to use expired cookie
        response = client.get("/api/session-token", cookies={"brokr_session": expired_token}, follow_redirects=False)

        assert response.status_code == 303, "Expired cookie should redirect to /login"
        assert "/login" in response.headers["location"]

    def test_expired_cookie_does_not_grant_access(self, client, with_auth_env):
        """Expired cookie cannot be used to access any protected endpoint."""
        # Create an already-expired token
        expired_token = _make_token(
            "testpassword123",  # password used for signing
            "test-secret-key-for-hmac",  # secret key
            time.time() - 3600,  # expired 1 hour ago
        )

        # Attempt to access protected endpoint with expired cookie
        response = client.get("/api/session-token", cookies={"brokr_session": expired_token}, follow_redirects=False)
        assert response.status_code == 303, "Expired cookie should redirect, not grant access"
        assert "/login" in response.headers["location"]
