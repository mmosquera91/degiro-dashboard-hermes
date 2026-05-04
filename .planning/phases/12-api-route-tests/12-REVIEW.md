---
phase: 12-api-route-tests
reviewed: 2026-05-04T00:00:00Z
depth: standard
files_reviewed: 1
files_reviewed_list:
  - tests/test_routes.py
findings:
  critical: 0
  warning: 1
  info: 2
  total: 3
status: issues_found
---

# Phase 12: Code Review Report

**Reviewed:** 2026-05-04
**Depth:** standard
**Files Reviewed:** 1
**Status:** issues_found

## Summary

Reviewed `tests/test_routes.py` which contains 12 route tests covering login, health, auth, session, session-token, logout, and portfolio endpoints. Tests are generally well-structured with correct patch targets, proper status code assertions, and appropriate use of TestClient. One structural quality issue and two minor style observations were found.

## Warnings

### WR-01: Unused helper methods create dead code

**File:** `tests/test_routes.py:70-77` and `tests/test_routes.py:126-133`

Two helper methods are defined but never called:

- `TestApiAuthRoute._auth_headers(self, client)` (lines 70-77)
- `TestApiSessionRoute._session_headers(self, client)` (lines 126-133)

Both are superseded by inline token creation within each test method. The helpers accept `client` as a parameter but never use it, and all tests in these classes construct tokens directly rather than via the helpers.

**Fix:** Remove `_auth_headers` and `_session_headers` methods entirely. If helper methods are needed in the future, ensure they are actually called by tests.

```python
# Remove these two methods:
def _auth_headers(self, client):
    """Return headers with valid session cookie and bearer token."""
    ...

def _session_headers(self, client):
    """Return headers with valid session cookie and bearer token."""
    ...
```

## Info

### IN-01: Direct access to private module-level lock

**File:** `tests/test_routes.py:11-12`

The reset fixture accesses the rate limiter's private internals:

```python
with rl._store_lock:
    rl._rate_limit_store.clear()
```

This is necessary for test isolation but couples tests to internal implementation details. If `rate_limiter.py` is refactored (e.g., lock renamed or removed), tests will break. Consider adding a public `reset()` function to the rate limiter module:

```python
def reset_for_testing():
    """Clear rate limiter state for test isolation."""
    with _store_lock:
        _rate_limit_store.clear()
```

### IN-02: Override of private FastAPI lifespan attribute

**File:** `tests/test_routes.py:31-35`

The test client overrides `app.router.lifespan_context` to suppress the application lifespan:

```python
app.router.lifespan_context = noop_lifespan
```

This uses FastAPI's private API which may break across versions. A more portable approach is to pass the lifespan directly to `TestClient` via the app constructor, or to use `pytest-anyio` with proper lifespan fixtures.

**Note:** This pattern appears in multiple phase-12 test files. If there is a shared test fixture library being used across phases, centralize this there to contain the version-specific workaround in one place.

---

_Reviewed: 2026-05-04_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_