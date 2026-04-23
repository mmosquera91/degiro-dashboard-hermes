---
phase: 01
plan: 02
type: execute
wave: 1
autonomous: true
requirements:
  - SEC-01
  - SEC-02
  - SEC-03
  - SEC-06

tags:
  - security
  - fastapi
  - authentication
  - cors
  - headers

dependency_graph:
  requires: []
  provides:
    - auth-dependency
    - security-headers-middleware
    - cors-middleware
    - removed-debug-endpoint
    - sanitized-error-handlers
  affects:
    - app/main.py

tech_stack:
  added:
    - fastapi.middleware.cors.CORSMiddleware
    - hmac.compare_digest
    - fastapi.Request
    - fastapi.Depends
  patterns:
    - FastAPI dependency injection for auth
    - HTTP middleware for security headers
    - Environment-driven CORS configuration

key_files:
  created: []
  modified:
    - path: app/main.py
      description: Added auth dependency, security headers middleware, CORS middleware, removed debug endpoint, sanitized error handlers

decisions: []

metrics:
  duration: "~10 minutes"
  completed_date: "2026-04-23T17:43:34Z"

commits:
  - hash: 833309d
    message: "feat(01-02): add auth middleware, security headers, CORS, remove debug endpoint"
    files:
      - app/main.py
---

# Phase 01 Plan 02: Security Hardening Summary

## One-liner

JWT-style bearer token auth with hmac.compare_digest, security headers middleware, same-origin CORS policy, removed debug endpoint, sanitized error messages.

## Completed Tasks

| # | Name | Commit | Verification |
|---|------|--------|--------------|
| 1 | Add imports (hmac, os, Request, Depends, CORSMiddleware) | 833309d | `grep` found all imports |
| 2 | Add verify_brok_token auth dependency function | 833309d | `grep` found function with hmac.compare_digest |
| 3 | Add security headers and CORS middleware | 833309d | All 4 security headers + CORS found |
| 4 | Remove /api/debug-login endpoint | 833309d | `grep` confirms endpoint removed |
| 5 | Add auth dependency to all /api/* routes | 833309d | `grep -c` shows 6 routes |
| 6 | Sanitize exception handler error messages | 833309d | All detail fields use generic messages |

## Must-Haves Verification

| Truth | Status |
|-------|--------|
| /api/debug-login endpoint no longer exists | PASS |
| All /api/* routes require BROKR_AUTH_TOKEN bearer token | PASS (6 routes with Depends) |
| /health and /static/* remain unauthenticated | PASS (no Depends on these) |
| Security headers present on all HTTP responses | PASS (X-Content-Type-Options, X-Frame-Options, HSTS, CSP) |
| CORS policy enforced with same-origin default | PASS (CORSMiddleware with localhost:8000 default) |
| Exception handlers return generic messages only | PASS (6 sanitized handlers) |

## Artifacts Verified

| Artifact | Contains | Status |
|----------|----------|--------|
| app/main.py | verify_brok_token | FOUND |
| app/main.py | X-Content-Type-Options | FOUND |
| app/main.py | CORSMiddleware | FOUND |

## Implementation Details

### verify_brok_token Auth Dependency
- Reads `BROKR_AUTH_TOKEN` from environment via `os.getenv`
- Validates `Authorization: Bearer <token>` header format
- Uses `hmac.compare_digest` for timing-safe comparison (prevents timing attacks)
- Returns generic 401 messages without revealing whether token was missing or invalid
- Logs warning when token not configured

### Security Headers Middleware
Applied to all HTTP responses via `@app.middleware("http")`:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `Content-Security-Policy: default-src 'self'; script-src 'self' https://cdn.jsdelivr.net https://unpkg.com; style-src 'self' 'unsafe-inline'; font-src https://fonts.gstatic.com`

### CORS Middleware
- Default: `["http://localhost:8000"]` (same-origin when accessed locally)
- Configurable via `CORS_ALLOWED_ORIGINS` env var (comma-separated list for Hermes cross-origin)
- `allow_credentials=True`
- `allow_methods=["GET", "POST"]`
- `allow_headers=["Authorization"]`

### Routes Protected with `dependencies=[Depends(verify_brok_token)]`
1. `/api/auth` (POST)
2. `/api/session` (POST)
3. `/api/portfolio` (GET)
4. `/api/portfolio-raw` (GET)
5. `/api/hermes-context` (GET)
6. `/api/logout` (POST)

### Routes NOT Protected (per D-03)
- `/health` - remains open for monitoring
- `/static/*` - remains open for assets

### Error Message Sanitization (D-10)
All `HTTPException` handlers now return generic client-facing messages:
- `detail="Authentication failed"` / `detail="Session authentication failed"` / `detail="Failed to fetch portfolio"`
- Actual exception details logged server-side via `logger.error`

## Deviations from Plan

None - plan executed exactly as written.

## Threat Flags

None - all security changes were in the plan's threat_model scope.

## Self-Check

- [x] app/main.py exists and was committed
- [x] Commit 833309d exists in git log
- [x] All 6 tasks completed and verified
- [x] All must-haves verified
- [x] No deviations documented (none occurred)

## CHECKPOINT REACHED

**Type:** complete
**Plan:** 01-02
**Tasks:** 6/6
**SUMMARY:** .planning/phases/01-security-hardening/01-02-SUMMARY.md

**Commit:**
- 833309d: feat(01-02): add auth middleware, security headers, CORS, remove debug endpoint

**Duration:** ~10 minutes
