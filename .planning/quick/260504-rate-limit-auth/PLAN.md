# Rate Limit Auth Endpoints

Add in-memory rate limiting on `/login` and `/api/auth` and `/api/session` to prevent brute force attacks.

## Implementation

- **File:** `app/rate_limiter.py`
  - Dict `IP -> [timestamps]` stored in memory
  - 5 attempts per IP per 60-second window
  - FastAPI `Depends()` dependency — `check_rate_limit(request)`
  - Returns 429 Too Many Requests when limit exceeded
  - Thread-safe with `threading.Lock`
  - Extracts client IP from `X-Forwarded-For` header (proxy-aware) or `request.client.host`

- **File:** `app/main.py`
  - Import `check_rate_limit` from `rate_limiter`
  - Add `Depends(check_rate_limit)` to `POST /login`
  - Add `Depends(check_rate_limit)` to `POST /api/auth`
  - Add `Depends(check_rate_limit)` to `POST /api/session`

## Verification

- Start server, make 5 rapid POST requests to `/login` or `/api/auth` — 6th returns 429
- Wait 60s, counter resets, requests succeed again
- Behind proxy (X-Forwarded-For), rate limit applies per original IP