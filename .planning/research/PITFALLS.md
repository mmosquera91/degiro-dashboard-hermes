# Pitfalls Research

**Domain:** Common mistakes when writing FastAPI backend tests
**Researched:** 2026-05-04
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: TestClient with app.lifecycle events

**What goes wrong:** `TestClient(app)` triggers `lifespan` events which start asyncio tasks (daily_enrichment_loop, daily_eod_loop), file writes, and symbol cache loading. Tests hang or fail due to side effects.

**How to avoid:** Use lifespan context manager override in tests:
```python
from contextlib import asynccontextmanager
async def mock_lifespan(app):
    yield
app.dependency_overrides[get_portfolio] = mock_get_portfolio
# OR
with TestClient(app, raise_server_exceptions=False) as client:
    ...
```

**Phase to address:** Phase 1 (Auth & Middleware)

---

### Pitfall 2: Auth cookie environment variables not set

**What goes wrong:** `verify_session_cookie` calls `_get_secret()` which reads APP_PASSWORD and SECRET_KEY from env. Tests fail with RuntimeError if not set.

**How to avoid:** Set env vars in conftest.py before importing app:
```python
import os
os.environ["APP_PASSWORD"] = "testpassword"
os.environ["SECRET_KEY"] = "testsecretkey12345678901234567890123456789012"
os.environ["BROKR_AUTH_TOKEN"] = "testauthtoken"
```

**Phase to address:** Phase 1

---

### Pitfall 3: Timing-dependent rate limiter tests

**What goes wrong:** `_clean_old_timestamps` uses `time.time()` — tests that check rate limiting across time boundaries fail if tests run too slowly or too fast.

**How to avoid:** Patch `time.time()` with `monkeypatch.setattr`:
```python
def test_rate_limit_expires(monkeypatch, client):
    call_time = 0
    def fake_time():
        nonlocal call_time
        call_time += 1
        return call_time * 60  # 60-second increments
    monkeypatch.setattr("time.time", fake_time)
```

**Phase to address:** Phase 1

---

### Pitfall 4: Testing middleware with TestClient — path order matters

**What goes wrong:** `check_session_cookie` middleware runs on every request. If you call `/api/portfolio` without a cookie, the middleware redirects to /login before the route handler runs. Can't test route-level auth errors this way.

**How to avoid:** Test middleware redirect behavior separately from route-level error responses. For 401 from route handlers, test the `verify_brok_token` dependency separately.

**Phase to address:** Phase 1

---

### Pitfall 5: DeGiroClient methods called during test setup

**What goes wrong:** `app/main.py` imports DeGiroClient at module level. When test imports app.main, it also imports degiro_client which may have module-level side effects (symbol cache loading).

**How to avoid:** Use monkeypatch to prevent real DeGiro calls. Mock at the right level:
```python
monkeypatch.setattr("app.degiro_client.DeGiroClient.authenticate", lambda *a, **k: MagicMock())
```

**Phase to address:** Phase 3

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| `pytest.raises` for all errors | Easy to write | Brittle — implementation changes break tests | NEVER — test behavior, not implementation |
| Mock everything deeply | Fast tests | Tests pass even when real code breaks | Only for isolation, not for correctness |
| Test without assertions | "Runs without error" | No verification | Never acceptable |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| FastAPI TestClient + cookies | Forgetting to set cookies on subsequent requests | Use `client.cookies.set()` for session cookies |
| Middleware + TestClient | Middleware runs before route, can't test route-level 401 | Test middleware redirect first, then verify route behavior with valid session |
| asyncio.Lock in code | Blocking in async tests | Use `asyncio.run()` for async code, or mock the lock |

## "Looks Done But Isn't" Checklist

- [ ] **Rate limiter cleanup:** Tests that add entries to `_rate_limit_store` must clean up after themselves (or use function-level patches)
- [ ] **Session state:** Tests that modify `_session` dict must restore original state (or use monkeypatch to isolate)
- [ ] **Operation lock:** Tests that acquire `_operation_lock` must release it even on failure (use try/finally or mocks)
- [ ] **Benchmark cache:** Tests that modify `_benchmark_cache` must reset it

## Sources

- FastAPI Testing Pitfalls: https://fastapi.tiangolo.com/tutorial/testing/
- pytest-asyncio known issues: https://github.com/pytest-dev/pytest-asyncio

---
*Pitfalls research for: FastAPI backend testing*
*Researched: 2026-05-04*