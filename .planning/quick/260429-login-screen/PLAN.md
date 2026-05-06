# Plan: Login Screen for Brokr

## Problem
App is accessible to anyone on the Tailscale network without authentication. Need a simple password-gated login screen.

## Changes

### Backend (app/main.py or new app/auth.py)

1. Add `APP_PASSWORD` to `.env` (document in `.env.example`)
2. FastAPI middleware: check every request for a valid signed session cookie
   - Cookie name: `brokr_session`
   - Value: HMAC-signed token using `APP_PASSWORD` + `SECRET_KEY` as seed
   - Expiry: 30 days
3. Unauthenticated requests to any route except `/login` and `/static/*` → redirect to `/login`
4. POST `/login`: accepts password form field
   - Match against `APP_PASSWORD`
   - On match: set signed cookie, redirect to `/`
   - On fail: return login page with "Incorrect password" message
5. GET `/logout`: clears cookie, redirects to `/login`

### Frontend (login page)

6. Clean, minimal login page — full viewport, centered card
   - App name/logo at top
   - Single password input + submit button
   - Error message slot below input (hidden unless failed attempt)
   - No username field
   - Consistent with app's existing visual style

### No changes to existing routes or portfolio logic

## Files to Modify
- `app/main.py` — add auth middleware and routes
- `app/auth.py` — new file for auth utilities
- `.env` — add APP_PASSWORD
- `.env.example` — document APP_PASSWORD
- `app/templates/login.html` — new login page template

## Verification
- App redirects unauthenticated users to /login
- Correct password sets cookie and redirects to /
- Incorrect password shows error on login page
- /logout clears cookie and redirects to /login
- Static assets remain accessible without auth
