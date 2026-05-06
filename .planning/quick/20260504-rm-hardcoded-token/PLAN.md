# Remove hardcoded BROK_TOKEN from frontend JS

## Problem
The frontend `app.js` embeds a hardcoded bearer token (`dev-secret-change-in-production`) used for API authentication. This is a security risk since:
1. The token is visible in client-side source code
2. Anyone can extract it and make authenticated API calls
3. The token never rotates

## Solution
The backend already has `BROKR_AUTH_TOKEN` set via environment. The frontend currently uses a separate hardcoded dev token. Instead, the frontend should receive the token from the backend after password login.

Two options were considered:
1. **Cookie-based**: Backend sets `brokr_token` HttpOnly cookie on `/login` success. Frontend reads it via `document.cookie` and injects into Authorization headers. Cookie is `httponly` so JS cannot read it directly (prevents XSS theft), but we need to inject it.
2. **Session endpoint**: Add `GET /api/session-token` that returns the token to authenticated sessions. Frontend calls it after login to get the token for subsequent API calls.

Option 1 (cookie) is cleaner — no extra round-trip, token never exposed to JS beyond the cookie header. However, since the cookie is HttpOnly, we need a way to inject the token into the Authorization header. The cleanest approach is:

- On login success, the backend ALSO sets a non-HttpOnly cookie `brokr_token` with the same value for reading via JS
- Frontend reads `brokr_token` from `document.cookie`, stores it in memory, uses it for API calls

Actually, since the session cookie is already set and verified, we can simplify: instead of passing the raw `BROKR_AUTH_TOKEN` to the frontend, we can create a session-scoped token that the backend can verify. But this adds complexity.

**Simplest fix**: Add a `GET /api/session-token` endpoint that returns the `BROKR_AUTH_TOKEN` to authenticated sessions. The frontend stores it in memory (not localStorage) after calling this endpoint on page load.

But wait — the `verify_brok_token` dependency reads `BROKR_AUTH_TOKEN` from the environment variable. If we return it from an endpoint, the frontend gets the same token. This works.

## Implementation

### Files to change:
1. `app/main.py` — Add `GET /api/session-token` endpoint
2. `app/static/app.js` — Remove hardcoded `AUTH_TOKEN`, fetch from `/api/session-token` on init

### Changes

#### `app/main.py`
Add new endpoint after existing auth endpoints:

```python
@app.get("/api/session-token", dependencies=[Depends(verify_brok_token)])
async def get_session_token():
    """Return the BROKR_AUTH_TOKEN for the current authenticated session.
    
    The frontend uses this token for subsequent API calls instead of
    hardcoding it in JavaScript.
    """
    token = os.getenv("BROKR_AUTH_TOKEN", "")
    if not token:
        raise HTTPException(status_code=500, detail="BROKR_AUTH_TOKEN not configured")
    return {"token": token}
```

#### `app/static/app.js`
- Remove `const AUTH_TOKEN = "dev-secret-change-in-production";` (line 29)
- Add `let _authToken = null;` state variable
- Add `async function fetchAuthToken()` that calls `GET /api/session-token` and stores the result in `_authToken`
- Update `apiFetch()` to use `_authToken` from memory
- Call `fetchAuthToken()` on `DOMContentLoaded` before making any API calls

### Sequence:
1. User logs in via `/login` → session cookie set
2. `app.js` loads, calls `fetchAuthToken()` on init
3. `/api/session-token` validates session cookie, returns `BROKR_AUTH_TOKEN`
4. `app.js` stores token in `_authToken` memory variable
5. All `apiFetch()` calls use `_authToken`

### Security considerations:
- Token travels over HTTPS (enforced by HSTS header)
- Session cookie validates user before returning token
- Token stored in memory (not localStorage), so it dies when tab closes
- Attacker with XSS can still steal the token — to fully mitigate, use HttpOnly cookie and have backend inject the token into responses (more complex)