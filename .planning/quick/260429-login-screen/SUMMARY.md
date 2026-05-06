---
name: 260429-login-screen
description: Password-gated login screen with HMAC-signed session cookies
status: complete
---

## What

Added password-gated login screen to protect the app from unauthorized access on Tailscale network.

## Changes

- **app/auth.py** — New module with HMAC-signed session cookie utilities
- **app/templates/login.html** — Minimal centered login page
- **app/main.py** — Added auth middleware, /login GET/POST, /logout routes
- **.env** — Added APP_PASSWORD and SECRET_KEY
- **.env.example** — Documented APP_PASSWORD and SECRET_KEY

## How it works

1. Middleware checks every request for valid `brokr_session` cookie (HMAC-SHA256 signed)
2. Unauthenticated requests redirect to /login
3. POST /login validates password against APP_PASSWORD env var
4. Success sets a 30-day signed cookie; failure redirects with ?failedattempt=yes
5. /logout clears the cookie and redirects to /login
6. /health, /login, /static/* remain open (no auth required)

## Commits

- [quick] feat: add password-gated login screen with HMAC-signed session cookies
