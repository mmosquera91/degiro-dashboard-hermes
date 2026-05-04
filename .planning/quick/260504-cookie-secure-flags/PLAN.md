Add Secure/HttpOnly/SameSite cookie flags

**Issue:** Session cookies lack the `Secure` flag (HTTPS-only), leaving them
vulnerable to being sent over unencrypted connections.

**Current state:**
- `make_session_cookie()` in app/auth.py: `httponly=True`, `samesite="lax"` — no `secure`
- `clear_session_cookie()` in app/auth.py: same flags — no `secure`
- `/logout` endpoint in app/main.py: `httponly=True`, `samesite="lax"` — no `secure`

**Fix:**
1. Add `secure` flag to `make_session_cookie()` — conditional on `DEBUG=False` or
   `COOKIE_SECURE=true` env var, since local development may run over HTTP
2. Add `secure` flag to `clear_session_cookie()` — same conditional
3. Add `secure` flag to logout response in app/main.py — same conditional
4. Keep `httponly=True` and `samesite="Lax"` on all cookie responses

**Verification:**
- grep for `secure=` in auth.py and main.py confirms all cookie responses updated
- login.html is a template (HTML form) — no Set-Cookie header set there