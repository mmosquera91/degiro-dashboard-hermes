# Feature Research

**Domain:** FastAPI backend test coverage — what to test in auth middleware, API routes, and DeGiro client
**Researched:** 2026-05-04
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Auth cookie signing | Prevents session forgery | LOW | HMAC-SHA256 with expiry |
| Timing-safe comparison | Prevents timing attacks | LOW | hmac.compare_digest |
| Rate limiting | Brute force protection | LOW | In-memory sliding window |
| Session middleware | Redirect unauthenticated | LOW | FastAPI middleware |
| Bearer token validation | API auth on /api/* routes | LOW | HMAC compare_digest |
| Login/logout flow | User authentication | LOW | Cookie-based session |
| Session-token bootstrap | Frontend gets API token | LOW | No-bearer bootstrap endpoint |
| DeGiro auth | Session or credentials login | MEDIUM | Two auth methods |
| Portfolio fetch | Protected endpoint | LOW | Session + API token |
| Error responses | 401, 429, 500 | LOW | FastAPI HTTPException |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|-------------|-------|
| Snapshot restoration on startup | Portfolio survives restart | MEDIUM | lifespan event, tests need app fixture |
| Daily auto-enrichment loop | Fresh data without user action | HIGH | asyncio.create_task in lifespan |
| Operation lock (409 busy) | Prevents concurrent enrichment | LOW | asyncio.Lock around operations |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Tests against real DeGiro | "Real data" feel | Flaky, rate-limited, requires credentials | Mock DeGiroClient methods |
| TestClient with real lifespan startup | More realistic | Side effects (file writes, asyncio loops) | Use lifespan context manager override |
| Testing private functions | "Thoroughness" | Tests break on refactor | Test public interface only |

## Feature Dependencies

```
[Auth Cookie]
    └──requires──> [Session Middleware]
                       └──requires──> [Protected Routes]

[Rate Limiter]
    └──applied to──> [/login POST, /api/auth, /api/session]

[verify_brok_token]
    └──applied to──> [All /api/* routes]

[DeGiroClient.from_session_id]
    └──used by──> [/api/session endpoint]
```

## MVP Definition

### Launch With (v1.3)

- [ ] auth.py unit tests (make_session_cookie, verify_session_cookie, clear_session_cookie, _make_token, _verify_token)
- [ ] rate_limiter.py unit tests (check_rate_limit, _clean_old_timestamps)
- [ ] middleware test (unauthenticated redirect, session cookie check)
- [ ] /api/auth test (success, failure, ConnectionError → 401)
- [ ] /api/session test (success, failure)
- [ ] /api/logout test
- [ ] /api/session-token test (bootstrap endpoint)
- [ ] /login POST test (success redirect, wrong password redirect, failedattempt)
- [ ] Error responses: 401, 429, 500
- [ ] DeGiroClient.from_session_id mocked test
- [ ] DeGiroClient._kv_list_to_dict test
- [ ] Integration: login → session-token → protected endpoint flow

### Add After Validation (v1.x)

- [ ] Test /api/portfolio with mocked trading_api
- [ ] Test /api/refresh-prices with snapshot-restored portfolio
- [ ] Test operation lock (409 when already running)
- [ ] Test benchmark cache invalidation

## Sources

- FastAPI TestClient: https://fastapi.tiangolo.com/tutorial/testing/
- pytest-mock: https://pytest-mock.readthedocs.io/
- unittest.mock: https://docs.python.org/3/library/unittest.mock.html

---
*Feature research for: FastAPI backend test coverage*
*Researched: 2026-05-04*