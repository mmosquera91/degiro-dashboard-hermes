---
name: 260504-timing-leak-fix
status: complete
---

Fixed timing leak in `app/main.py` line 1040.

**Changed:**
```python
# Before (vulnerable to timing attack)
if password == app_password:

# After (constant-time comparison)
if hmac.compare_digest(password, app_password):
```

**Verification:** No other `==` password/token comparisons found in `app/main.py` or `app/auth.py`. The `auth.py` module already used `hmac.compare_digest` correctly.
