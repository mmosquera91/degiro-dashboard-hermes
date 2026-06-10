"""Tests for app.auth — HMAC session cookies (AUTH-01 to AUTH-05)."""

import pytest
import time


class TestMakeToken:
    """AUTH-01: _make_token creates HMAC-SHA256 signed token with expiry."""

    def test_token_format_contains_dot_separator(self, auth_module):
        token = auth_module._make_token("password", "secret", time.time() + 3600)
        assert "." in token
        parts = token.split(".")
        assert len(parts) == 2

    def test_signature_is_64_char_hex(self, auth_module):
        token = auth_module._make_token("password", "secret", time.time() + 3600)
        _, sig = token.rsplit(".", 1)
        assert len(sig) == 64
        assert all(c in "0123456789abcdef" for c in sig)

    def test_same_args_produces_identical_token(self, auth_module):
        expires = time.time() + 3600
        token1 = auth_module._make_token("pw", "sk", expires)
        token2 = auth_module._make_token("pw", "sk", expires)
        assert token1 == token2

    def test_different_password_produces_different_token(self, auth_module):
        expires = time.time() + 3600
        token1 = auth_module._make_token("pw1", "sk", expires)
        token2 = auth_module._make_token("pw2", "sk", expires)
        assert token1 != token2


class TestVerifyToken:
    """AUTH-02: _verify_token validates expiry and signature with timing-safe comparison."""

    def test_verify_valid_token_returns_true(self, auth_module):
        expires = time.time() + 3600
        token = auth_module._make_token("pw", "sk", expires)
        assert auth_module._verify_token("pw", "sk", token) is True

    def test_verify_expired_token_returns_false(self, auth_module):
        expires = time.time() - 1  # already expired
        token = auth_module._make_token("pw", "sk", expires)
        assert auth_module._verify_token("pw", "sk", token) is False

    def test_verify_tampered_signature_returns_false(self, auth_module):
        expires = time.time() + 3600
        token = auth_module._make_token("pw", "sk", expires)
        prefix, sig = token.rsplit(".", 1)
        tampered = prefix + "." + sig[:-1] + ("f" if sig[-1] != "f" else "e")
        assert auth_module._verify_token("pw", "sk", tampered) is False

    def test_verify_malformed_token_returns_false(self, auth_module):
        assert auth_module._verify_token("pw", "sk", "no-dot-here") is False
        assert auth_module._verify_token("pw", "sk", "") is False

    def test_verify_wrong_password_returns_false(self, auth_module):
        expires = time.time() + 3600
        token = auth_module._make_token("correctpw", "sk", expires)
        assert auth_module._verify_token("wrongpw", "sk", token) is False


class TestMakeSessionCookie:
    """AUTH-03: make_session_cookie returns token + cookie kwargs with correct attributes."""

    def test_returns_tuple_of_token_and_kwargs(self, auth_module):
        result = auth_module.make_session_cookie()
        assert isinstance(result, tuple)
        assert len(result) == 2
        token, kwargs = result
        assert isinstance(token, str)
        assert isinstance(kwargs, dict)

    def test_kwargs_contains_httponly_true(self, auth_module):
        _, kwargs = auth_module.make_session_cookie()
        assert kwargs.get("httponly") is True

    def test_kwargs_contains_samesite_lax(self, auth_module):
        _, kwargs = auth_module.make_session_cookie()
        assert kwargs.get("samesite") == "Lax"

    def test_kwargs_contains_max_age(self, auth_module):
        _, kwargs = auth_module.make_session_cookie()
        assert "max_age" in kwargs
        assert kwargs["max_age"] == auth_module.SESSION_TTL_DAYS * 86400

    def test_kwargs_contains_path_slash(self, auth_module):
        _, kwargs = auth_module.make_session_cookie()
        assert kwargs.get("path") == "/"

    def test_kwargs_no_secure_by_default(self, auth_module, monkeypatch):
        """Default is Secure=False — HTTP deployments must work out of the box."""
        monkeypatch.setenv("DEBUG", "")
        monkeypatch.setenv("COOKIE_SECURE", "")
        import importlib
        import app.auth as auth
        importlib.reload(auth)
        _, kwargs = auth.make_session_cookie()
        assert "secure" not in kwargs

    def test_kwargs_contains_secure_when_opt_in(self, auth_module, monkeypatch):
        """COOKIE_SECURE=true explicitly enables the Secure flag (HTTPS)."""
        monkeypatch.setenv("DEBUG", "")
        monkeypatch.setenv("COOKIE_SECURE", "true")
        import importlib
        import app.auth as auth
        importlib.reload(auth)
        _, kwargs = auth.make_session_cookie()
        assert kwargs.get("secure") is True


class TestVerifySessionCookie:
    """AUTH-04: verify_session_cookie returns True for valid token, False for invalid."""

    def test_valid_token_returns_true(self, auth_module, sample_token):
        assert auth_module.verify_session_cookie(sample_token) is True

    def test_none_returns_false(self, auth_module):
        assert auth_module.verify_session_cookie(None) is False

    def test_empty_string_returns_false(self, auth_module):
        assert auth_module.verify_session_cookie("") is False

    def test_tampered_token_returns_false(self, auth_module, sample_token):
        tampered = sample_token[:-5] + "xxxxx"
        assert auth_module.verify_session_cookie(tampered) is False


class TestClearSessionCookie:
    """AUTH-05: clear_session_cookie returns correct delete_cookie kwargs."""

    def test_returns_path_slash(self, auth_module):
        kwargs = auth_module.clear_session_cookie()
        assert kwargs.get("path") == "/"

    def test_returns_httponly_true(self, auth_module):
        kwargs = auth_module.clear_session_cookie()
        assert kwargs.get("httponly") is True

    def test_returns_samesite_lax(self, auth_module):
        kwargs = auth_module.clear_session_cookie()
        assert kwargs.get("samesite") == "Lax"

    def test_no_secure_by_default(self, auth_module, monkeypatch):
        """Default is Secure=False — HTTP deployments must work out of the box."""
        monkeypatch.setenv("DEBUG", "")
        monkeypatch.setenv("COOKIE_SECURE", "")
        import importlib
        import app.auth as auth
        importlib.reload(auth)
        kwargs = auth.clear_session_cookie()
        assert "secure" not in kwargs

    def test_secure_true_when_opt_in(self, auth_module, monkeypatch):
        """COOKIE_SECURE=true explicitly enables the Secure flag (HTTPS)."""
        monkeypatch.setenv("DEBUG", "")
        monkeypatch.setenv("COOKIE_SECURE", "true")
        import importlib
        import app.auth as auth
        importlib.reload(auth)
        kwargs = auth.clear_session_cookie()
        assert kwargs.get("secure") is True