# Testing

## Current State

### Formal Tests: NONE
- No test framework is installed (no pytest, unittest, or similar in `requirements.txt`)
- No test directory exists
- No CI/CD pipeline configured
- No test configuration files (`pytest.ini`, `conftest.py`, `tox.ini`, `pyproject.toml`)

### Debug/Manual Test Scripts
Several standalone scripts in `app/` used for manual debugging during development:

| File | Purpose |
|------|---------|
| `debug_portfolio.py` | Debug portfolio fetching |
| `debug_raw_portfolio.py` | Debug raw portfolio data |
| `debug_from_session.py` | Debug session-based auth |
| `debug_int_account.py` | Debug intAccount retrieval |
| `test_auth_methods.py` | Manual auth method testing |
| `test_login.py` | Manual login testing |

These are **not automated tests** — they are interactive scripts that require manual execution with real credentials.

### Testing Gaps

#### Critical (no coverage)
- **Authentication flow:** DeGiro login success/failure paths, 2FA, captcha handling
- **Portfolio parsing:** Position extraction from various DeGiro response formats (flat dict, key-value list, different field names)
- **FX conversion:** Currency pair resolution, rate caching, fallback behavior
- **Scoring logic:** Momentum score, value score, buy priority calculations, normalization edge cases
- **RSI computation:** Correctness of Wilder's smoothing implementation

#### High (minimal coverage)
- **API endpoints:** Request validation, error responses, caching behavior, session expiry
- **Data pipeline:** End-to-end from DeGiro fetch through enrichment to JSON response
- **Frontend:** DOM rendering, chart creation, modal interactions, filter/sort behavior

#### Medium
- **Edge cases:** Empty portfolio, single position, all same-asset-type, missing yfinance data
- **Concurrency:** Thread-safety of session cache under concurrent requests
- **Container:** Docker build, healthcheck endpoint, environment variable handling

## Recommendations

### Framework
- Add `pytest` and `pytest-asyncio` to `requirements.txt`
- Create `tests/` directory with `conftest.py`

### Priority Test Targets
1. **`scoring.py`** — Pure functions, easy to unit test, high business value
2. **`market_data.py`** — RSI calculation, performance computation, FX rate logic
3. **`degiro_client.py`** — Mock DeGiro API responses, test parsing robustness
4. **`main.py`** — FastAPI `TestClient` for endpoint integration tests

### Test Types to Add
- Unit tests for scoring/metrics calculations
- Integration tests with mocked DeGiro and yfinance responses
- Contract tests for API endpoint request/response shapes
- Frontend not tested (vanilla JS, would need Playwright/Cypress — low priority for current scope)
