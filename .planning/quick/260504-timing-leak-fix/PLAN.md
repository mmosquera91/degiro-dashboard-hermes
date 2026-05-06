Fix timing leak in APP_PASSWORD comparison

**Issue:** `password == app_password` (line 1040) uses `==` which is vulnerable to timing attacks.

**Fix:** Replace with `hmac.compare_digest(password, app_password)` for constant-time comparison.

**Verification:** No other `==` password/token comparisons found in `app/main.py` or `app/auth.py`.
