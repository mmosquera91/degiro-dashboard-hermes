# Architecture Research

**Domain:** FastAPI backend test architecture — how to structure tests for app/main.py, app/auth.py, app/rate_limiter.py, app/degiro_client.py
**Researched:** 2026-05-04
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────┐
│              FastAPI Application                     │
├──────────────────────────────────────────────────────┤
│  Middleware Stack (bottom to top):                   │
│    1. check_session_cookie → Redirect or continue    │
│    2. add_security_headers → Add headers             │
│    3. CORS middleware → CORS headers                  │
├──────────────────────────────────────────────────────┤
│  Routes:                                             │
│    /login, /logout, /static/*, /health → open        │
│    /api/* → verify_brok_token + check_rate_limit     │
└──────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Testing Approach |
|-----------|----------------|------------------|
| auth.py | HMAC cookie signing/verification | Pure unit tests with monkeypatch |
| rate_limiter.py | IP-based rate limiting | Unit tests with fake time |
| main.py middleware | Session cookie check, security headers | TestClient with cookies |
| main.py routes | API endpoints | TestClient with mocked DeGiro |
| degiro_client.py | DeGiro API calls | Mocked unit tests |

## Recommended Project Structure

```
tests/
├── conftest.py           # Shared pytest fixtures (app, client)
├── test_auth.py          # auth.py unit tests
├── test_rate_limiter.py  # rate_limiter.py unit tests
├── test_middleware.py    # check_session_cookie middleware
├── test_routes_auth.py   # /login, /logout, /api/auth, /api/session
├── test_routes_api.py    # /api/portfolio, /api/benchmark, etc.
├── test_degiro_client.py # degiro_client.py mocked tests
├── test_integration.py   # End-to-end flows
└── fixtures/
    ├── degiro_portfolio.json  # Sample portfolio data
    ├── degiro_session.json   # Sample session data
    └── ...
```

## Test Fixtures

### conftest.py
```python
import os
import pytest
from fastapi.testclient import TestClient

os.environ["APP_PASSWORD"] = "testpassword"
os.environ["SECRET_KEY"] = "testsecretkey12345678901234567890123456789012"
os.environ["BROKR_AUTH_TOKEN"] = "testauthtoken"

@pytest.fixture
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c
```

### Mocking DeGiroClient
```python
@pytest.fixture
def mock_degiro(monkeypatch):
    mock = MagicMock()
    mock.authenticate.return_value = MagicMock()
    mock.from_session_id.return_value = MagicMock()
    mock.fetch_portfolio.return_value = {"positions": [], "cash_available": 0}
    monkeypatch.setattr("app.main.DeGiroClient", mock)
    return mock
```

## Data Flow

### Auth Flow (Login → Session Cookie)
```
POST /login (form password)
    ↓
hmac.compare_digest with APP_PASSWORD
    ↓ [success]
make_session_cookie() → HMAC-signed token
    ↓
RedirectResponse + set_cookie(brokr_session, token)
```

### API Auth Flow
```
GET /api/portfolio
    ↓
verify_brok_token: check Authorization: Bearer BROKR_AUTH_TOKEN
    ↓ [success]
check_session_cookie: check brokr_session cookie
    ↓ [valid]
route handler
```

## Sources

- FastAPI Testing: https://fastapi.tiangolo.com/tutorial/testing/
- pytest fixtures: https://docs.pytest.org/en/stable/fixture.html

---
*Architecture research for: FastAPI backend test architecture*
*Researched: 2026-05-04*
