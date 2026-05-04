---
phase: 11-auth-infrastructure-tests
reviewed: 2026-05-04T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - tests/conftest.py
  - tests/test_auth.py
  - tests/test_rate_limiter.py
  - tests/test_middleware.py
findings:
  critical: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
---

# Phase 11: Code Review Report

**Reviewed:** 2026-05-04
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed the four test files in `tests/` for auth infrastructure. The tests cover HMAC session cookies (`test_auth.py`), IP-based rate limiting (`test_rate_limiter.py`), and FastAPI middleware behavior (`test_middleware.py`). Two test files (`conftest.py` and `test_middleware.py`) import the `market_data` module to access `_fx_cache` — a fixture and import that are present but unused by any test in those files, indicating dead code. One test has a conditional assertion that can silently pass with no assertion at all.

---

## Warnings

### WR-01: Unused `market_data` import and fixture in `test_middleware.py`

**File:** `tests/test_middleware.py:6`
**Issue:** The file imports `market_data` and has an `autouse` fixture that clears `_fx_cache`, but no test in this file uses `market_data` or the fixture. This is dead code that adds test startup overhead and misleading noise.
**Fix:** Remove the `import market_data` on line 6, and remove the `fx_rate_cache` fixture on lines 9-14. The `market_data` module is only needed by other test files (e.g., those that test enrichment).

---

### WR-02: Conditional assertion can silently pass without verifying anything in `test_correct_token_allows_request`

**File:** `tests/test_auth.py:91-98`
**Issue:** The test body is entirely wrapped in `if response.status_code == 401:`. When the request succeeds (status 200), the `assert` inside the `if` block never runs, so the test passes without asserting anything meaningful about the happy path. The test name and docstring imply "correct token allows request" but the assertion is only that a 401 response does not contain "Invalid token".

```python
def test_correct_token_allows_request(self, client, with_auth_env):
    """Correct bearer token allows request to proceed."""
    from app.auth import make_session_cookie
    token, _ = make_session_cookie()
    response = client.get("/api/portfolio", cookies={"brokr_session": token}, headers={"Authorization": "Bearer test-bearer-token-12345"})
    # Should not be 401 due to token mismatch - session is not authenticated so 401 with "Session expired"
    if response.status_code == 401:
        assert "Invalid token" not in response.text
```

**Fix:** Replace with a direct assertion on the expected success:

```python
def test_correct_token_allows_request(self, client, with_auth_env):
    """Correct bearer token allows request to proceed."""
    from app.auth import make_session_cookie
    token, _ = make_session_cookie()
    response = client.get("/api/portfolio", cookies={"brokr_session": token}, headers={"Authorization": "Bearer test-bearer-token-12345"})
    assert response.status_code == 200
```

---

## Info

### IN-01: Unused `market_data` import and fixture in `tests/conftest.py`

**File:** `tests/conftest.py:8, 9-14`
**Issue:** `conftest.py` imports `market_data` and defines `fx_rate_cache` that clears the FX rate cache before and after each test. However, no test file in this review (and likely no test file at all) uses this fixture — the auth tests and middleware tests do not exercise market data.
**Fix:** Remove `import market_data` and the `fx_rate_cache` fixture from `conftest.py`, or move them to a separate `conftest.py` in the module that actually tests market data functionality.

---

### IN-02: `TestCheckRateLimit` tests do not verify actual rate limit behavior for repeated requests from same IP

**File:** `tests/test_rate_limiter.py:24-39`
**Issue:** `test_fifth_request_succeeds` calls `rl._rate_limit_store.clear()` before the loop, making it independent from `test_first_request_succeeds`. Each test clears the store entirely. There is no test that verifies the actual sliding window behavior across sequential requests without explicit `clear()` calls. The tests confirm individual request behavior in isolation but do not validate the integration scenario (5 requests over time from the same IP without manual store clearing).
**Fix:** This is informational — the existing tests are valid unit tests for the module. A higher-level integration test (not in this file) would be the appropriate place to validate the full sliding window without explicit store manipulation. No change required to these tests.

---

_Reviewed: 2026-05-04_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
