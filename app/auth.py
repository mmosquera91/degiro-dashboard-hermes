"""Auth utilities: HMAC-signed session cookies."""

import hashlib
import hmac
import os
import time
from typing import Optional


SESSION_COOKIE = "brokr_session"
SESSION_TTL_DAYS = 30


def _get_secret() -> tuple[str, str]:
    """Return (APP_PASSWORD, SECRET_KEY) tuple. Raises if either is missing."""
    app_password = os.getenv("APP_PASSWORD", "")
    secret_key = os.getenv("SECRET_KEY", "")
    if not app_password or not secret_key:
        raise RuntimeError("APP_PASSWORD and SECRET_KEY must be set in environment")
    return app_password, secret_key


def _make_token(password: str, secret_key: str, expires_at: float) -> str:
    """Create HMAC-signed token: f"{expires_at}.{hmac_sha256(password, expires_at, secret_key)}"."""
    payload = f"{expires_at:.0f}"
    sig = hmac.new(
        secret_key.encode(),
        (payload + password).encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{expires_at:.0f}.{sig}"


def _verify_token(password: str, secret_key: str, token: str) -> bool:
    """Verify a signed token hasn't expired and matches the password."""
    try:
        expires_at_str, sig = token.rsplit(".", 1)
        expires_at = float(expires_at_str)
    except ValueError:
        return False

    if time.time() > expires_at:
        return False

    expected_sig = hmac.new(
        secret_key.encode(),
        (f"{expires_at:.0f}" + password).encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(sig, expected_sig)


def make_session_cookie() -> tuple[str, dict]:
    """Create a new signed session cookie value and cookie kwargs dict.

    Returns (cookie_value, cookie_kwargs) — cookie_kwargs includes expires and path.
    """
    app_password, secret_key = _get_secret()
    expires_at = time.time() + (SESSION_TTL_DAYS * 86400)
    token = _make_token(app_password, secret_key, expires_at)
    cookie_kwargs = {
        "path": "/",
        "httponly": True,
        "samesite": "lax",
        "max_age": SESSION_TTL_DAYS * 86400,
    }
    return token, cookie_kwargs


def verify_session_cookie(cookie_value: Optional[str]) -> bool:
    """Return True if the cookie value is a valid, non-expired session token."""
    if not cookie_value:
        return False
    try:
        app_password, secret_key = _get_secret()
    except RuntimeError:
        return False
    return _verify_token(app_password, secret_key, cookie_value)


def clear_session_cookie() -> dict:
    """Return cookie kwargs to clear the session cookie."""
    return {
        "path": "/",
        "httponly": True,
        "samesite": "lax",
        "max_age": 0,
        "expires": "Thu, 01 Jan 1970 00:00:00 GMT",
    }
