# Stack Research

**Domain:** Python FastAPI backend testing with FastAPI TestClient and unittest.mock
**Researched:** 2026-05-04
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| pytest | 7+ | Test runner | Industry standard, fixtures, parametrization |
| pytest-asyncio | 0.23+ | Async test support | Required for testing FastAPI async routes |
| httpx | 0.27+ | HTTP client | TestClient in FastAPI uses httpx under the hood |
| unittest.mock | stdlib | Mocking | Built-in, no extra install, patch decorators work well |
| pytest-mock | 3.12+ | Mock fixtures | `pytest-mock` fixture gives cleaner mockito-like access |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|--------|---------|---------|-------------|
| pytest-cov | 4+ | Coverage reporting | `--cov=app --cov-report=term-missing` |
| responses | 0.25+ | Mock HTTP responses | For testing code that makes real HTTP calls (yfinance) |
| pytest-asyncio | | Async fixtures | `@pytest.fixture` with `async def` |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `PYTHONPATH=app pytest` | Run with correct import path | Tests must run from repo root with app/ on path |
| `--tb=short` | Shorter tracebacks | Faster debugging |
| `-x` | Stop on first failure | Faster red-green cycle |
| `-k "test_name"` | Run single test |快速 iteration |

## FastAPI TestClient Patterns

```python
from fastapi.testclient import TestClient
from app.main import app

def test_protected_endpoint(client):
    # With mocked session cookie
    client.cookies.set("brokr_session", "valid_token")
    response = client.get("/api/portfolio")
    assert response.status_code == 200
```

```python
# For routes with Depends(verify_brok_token), need to mock env var
def test_with_auth_token(monkeypatch):
    monkeypatch.setenv("BROKR_AUTH_TOKEN", "test-token")
    # Also set APP_PASSWORD, SECRET_KEY for session cookie
```

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| unittest.TestCase style | pytest fixtures are more powerful | Module-level `def test_` functions |
| MagicMock without spec | Allows arbitrary attributes | `@patch('module.Class', spec=Class)` |
| Real network calls in tests | Slow, flaky | `responses` library or `unittest.mock.patch` |

## Sources

- FastAPI Testing docs: https://fastapi.tiangolo.com/tutorial/testing/
- pytest-asyncio: https://pytest-asyncio.readthedocs.io/
- pytest-mock: https://pytest-mock.readthedocs.io/

---
*Stack research for: FastAPI backend testing*
*Researched: 2026-05-04*