# Quick Task 260504: Cookie Secure Flags

**Date:** 2026-05-04
**Status:** complete

## What Was Found

**app/auth.py - make_session_cookie():**
- Already had `httponly=True` and `samesite="lax"` (lowercase)
- Missing `secure` flag for HTTPS-only cookie transmission

**app/auth.py - clear_session_cookie():**
- Already had `httponly=True` and `samesite="lax"`
- Missing `secure` flag

**app/main.py - /logout endpoint:**
- Hardcoded `httponly=True`, `samesite="lax"` inline
- Missing `secure` flag

**app/templates/login.html:**
- Pure HTML form template — no Set-Cookie header setting
- No changes needed

**Other cookie locations:** None found.

## Changes Made

### app/auth.py

1. Added `_is_cookie_secure()` helper function:
   - Returns `True` by default (production HTTPS)
   - Returns `False` if `DEBUG=1/true/yes` or `COOKIE_SECURE=false`
   - Allows local HTTP development without cookie issues

2. Updated `make_session_cookie()`:
   - Added conditional `secure=True` when `_is_cookie_secure()` returns True
   - Fixed `samesite` capitalization to `"Lax"` (standard)

3. Updated `clear_session_cookie()`:
   - Added conditional `secure=True` when `_is_cookie_secure()` returns True
   - Fixed `samesite` capitalization to `"Lax"`

### app/main.py

4. Updated `/logout` endpoint:
   - Now uses `clear_session_cookie()` helper for consistent flags
   - Removed hardcoded inline cookie kwargs

## All Cookie Flags Now Set

| Location | HttpOnly | SameSite | Secure |
|----------|----------|----------|--------|
| `make_session_cookie()` | Yes | Lax | Conditional |
| `clear_session_cookie()` | Yes | Lax | Conditional |
| `/logout` delete_cookie | Yes | Lax | Conditional |

**Conditional Secure:** Enabled by default, disabled when `DEBUG=1` or `COOKIE_SECURE=false`.

## Commit

`fcd42b7` - fix(auth): add Secure/HttpOnly/SameSite cookie flags