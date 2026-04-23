# Phase 1: Security Hardening - Research

**Researched:** 2026-04-23
**Domain:** FastAPI authentication, security headers, credential exposure mitigation
**Confidence:** HIGH

## Summary

Phase 1 addresses four critical security vulnerabilities (C-01 through C-04) and implements three hardening measures. The primary mechanism for API protection is a static bearer token (`BROKR_AUTH_TOKEN`) validated via FastAPI dependency middleware applied to all `/api/*` routes. The debug endpoint and six debug scripts are deleted entirely rather than gated or redacted, eliminating attack surface completely. FastAPI binds to `127.0.0.1` by default with `HOST` environment variable override. Security headers and CORS are added via middleware, with CORS defaulting to same-origin and configurable via environment for Hermes integration.

**Primary recommendation:** Implement auth middleware first (SEC-03), as it gates all other API endpoints and must be in place before testing other changes.

---

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** `BROKR_AUTH_TOKEN` is a static bearer token — random string set via env var, no signature, no expiry, no session storage
- **D-02:** Auth token validation via FastAPI dependency middleware — single point, applied to all `/api/*` routes
- **D-03:** Token protects API endpoints only (`/api/*`). `/health` and `/static/*` remain open for monitoring and assets
- **D-04:** `/api/debug-login` is removed entirely — not gated, not redacted
- **D-05:** Debug scripts deleted from `app/` — not relocated, not dockerignored
- **D-06:** Development utility scripts needed should go in `scripts/` directory excluded from Docker via `.dockerignore`
- **D-07:** FastAPI binds to `127.0.0.1` by default, configurable via `HOST` environment variable
- **D-08:** Security headers added via middleware: `X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security`, `Content-Security-Policy`
- **D-09:** CORS defaults to same-origin, configurable via environment variable for Hermes integration
- **D-10:** Exception handlers return generic user-facing messages — internal details logged server-side only

### Claude's Discretion

CORS configuration details (specific header values, which exact headers for HSTS) are deferred to the planner.

### Deferred Ideas (OUT OF SCOPE)

CORS configuration deferred to planner — defaults to same-origin with `CORS_CONFIG` env for Hermes cross-origin calls.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| API authentication | API/Backend | — | FastAPI middleware validates `BROKR_AUTH_TOKEN` on all `/api/*` routes |
| Bind address control | API/Backend | — | `HOST` env var controls uvicorn bind address |
| Security headers | API/Backend | — | Middleware adds headers to all responses |
| CORS policy | API/Backend | — | FastAPI CORSMiddleware with env-driven configuration |
| Debug endpoint removal | API/Backend | — | Delete endpoint from `main.py` |
| Debug script removal | Build/Docker | — | Delete from `app/`, update `.dockerignore` |
| Error message sanitization | API/Backend | — | Replace `str(e)` in HTTPException details with generic messages + logging |

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SEC-01 | Remove `request_payload` from debug endpoint responses — prevent plaintext password exposure | D-04: endpoint removed entirely, attack surface eliminated |
| SEC-02 | Redact or omit `session_id` from all debug/error responses | D-04: endpoint removed entirely, no session_id exposure possible |
| SEC-03 | Add `BROKR_AUTH_TOKEN` environment variable and validate on all API endpoints | D-01, D-02, D-03: static token, dependency middleware, `/api/*` scope |
| SEC-04 | Bind FastAPI to 127.0.0.1 by default — prevent network exposure without TLS | D-07: default `127.0.0.1`, `HOST` env override |
| SEC-05 | Remove debug scripts (`debug_*.py`) from production Docker image | D-05: files deleted from `app/`, D-06: use `scripts/` outside Docker |
| SEC-06 | Add security headers (HSTS, X-Content-Type-Options, etc.) and CORS policy | D-08, D-09: middleware approach, same-origin default, configurable |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | 0.115.6 | Web framework | Required by existing codebase |
| uvicorn | 0.34.0 | ASGI server | Required by existing codebase |
| starlette | (via fastapi) | Middleware foundation | Used for CORSMiddleware and custom middleware |

**Installation:** N/A (existing project, packages already in requirements.txt)

### Security Implementation Components
| Component | Approach | Why Standard |
|-----------|---------|--------------|
| Auth token | `Depends(verify_brok_token)` dependency | FastAPI canonical pattern for route protection |
| Token header | `Authorization: Bearer <token>` | RFC 6750 bearer token standard |
| Security headers | Custom middleware or `fastapi.middleware` | ASVS V14 / OWASP recommendation |
| CORS | `fastapi.middleware.cors.CORSMiddleware` | FastAPI built-in, configurable |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Dependency middleware | Per-route `Depends()` checks | Dependency approach is cleaner and harder to forget |
| Static bearer token | JWT or HMAC-signed token | Overkill for single-user, localhost-bound app |
| Remove debug endpoint | Gate behind env flag | Removal eliminates attack surface completely per D-04 |

---

## Architecture Patterns

### System Architecture Diagram

```
[Client/Browser]
       │
       ▼ HTTP request (with or without Authorization header)
[Uvicorn] ─────► bind: 127.0.0.1:8000 (configurable via HOST env)
       │
       ▼
[Security Headers Middleware] ──► Adds X-Content-Type-Options, X-Frame-Options, CSP, HSTS
       │
       ▼
[CORS Middleware] ──► same-origin default, configurable for Hermes cross-origin
       │
       ▼
[Auth Middleware (depends)] ──► Validates BROKR_AUTH_TOKEN on /api/* routes
       │                         /health and /static/* pass through unprotected
       │
       ▼
[Route Handlers] ──► /api/auth, /api/session, /api/portfolio, /api/hermes-context, /api/logout
       │
       ▼
[Exception Handlers] ──► Generic error messages returned; details logged server-side
```

### Recommended Project Structure
```
app/
├── main.py              # FastAPI app, auth middleware, route handlers (MODIFIED)
├── degiro_client.py      # DeGiro API client (UNCHANGED)
├── market_data.py        # yfinance enrichment (UNCHANGED)
├── scoring.py            # Scoring logic (UNCHANGED)
├── context_builder.py    # Hermes context builder (UNCHANGED)
├── static/
│   ├── index.html        # Frontend (UNCHANGED)
│   └── app.js            # Frontend JS (UNCHANGED)
scripts/                  # Development utilities (NEW, excluded from Docker)
.dockerignore             # Exclude scripts/ from Docker (MODIFIED)
Dockerfile                # Unchanged — already uses COPY app/ ./app/
.env.example              # Document BROKR_AUTH_TOKEN (MODIFIED)
```

### Pattern 1: FastAPI Auth Dependency

**What:** A dependency function that extracts and validates the `Authorization` header against `BROKR_AUTH_TOKEN` env var.

**When to use:** Applied via `Depends()` on all `/api/*` routes.

**Example:**
```python
# Source: FastAPI canonical pattern (adjusted for this project)
def verify_brok_token():
    """Validate BROKR_AUTH_TOKEN from Authorization header."""
    token = os.getenv("BROKR_AUTH_TOKEN", "")
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Extract from header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth format")
    
    provided = auth_header[7:]  # Strip "Bearer " prefix
    if not hmac.compare_digest(provided, token):
        raise HTTPException(status_code=401, detail="Invalid token")
```

**Note:** Using `hmac.compare_digest` for timing-safe comparison prevents timing attacks.

### Pattern 2: Security Headers Middleware

**What:** FastAPI middleware that adds security headers to every response.

**When to use:** App-level middleware, applied before route handlers.

**Example:**
```python
# Source: OWASP Security Headers / FastAPI middleware pattern
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net https://unpkg.com; style-src 'self' 'unsafe-inline'; font-src https://fonts.gstatic.com"
    return response
```

### Pattern 3: CORS Middleware Configuration

**What:** FastAPI built-in CORS middleware with environment-driven configuration.

**When to use:** When cross-origin requests need to be supported (e.g., Hermes integration).

**Example:**
```python
# Source: FastAPI official docs — CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") or ["http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization"],
)
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Token validation | Custom header parsing with string operations | `Authorization: Bearer` with `hmac.compare_digest` | Timing-safe comparison prevents timing attacks |
| Auth middleware | Per-route if/return checks | FastAPI `Depends()` dependency | Single point of control, harder to miss a route |
| CORS configuration | Manual `Access-Control-*` header setting | `CORSMiddleware` | Built-in, handles preflight requests correctly |
| Security headers | Setting headers per-handler | Middleware | Consistent coverage, no forgotten routes |

---

## Common Pitfalls

### Pitfall 1: Auth middleware applied to wrong routes
**What goes wrong:** Auth applied to `/health` or `/static/*` accidentally, breaking monitoring or assets.
**Why it happens:** Using a blanket middleware instead of route-level `Depends()`.
**How to avoid:** Use `Depends()` on specific route groups. Middleware applies to all routes uniformly.
**Warning signs:** Health checks start returning 401, static assets fail to load.

### Pitfall 2: Token comparison using `==` instead of `hmac.compare_digest`
**What goes wrong:** Timing attack reveals token bit-by-bit.
**Why it happens:** Standard string comparison exits early on first mismatched character.
**How to avoid:** Use `hmac.compare_digest(a, b)` for all token comparisons.
**Warning signs:** Security scans flag timing vulnerabilities.

### Pitfall 3: Exception messages still leak internal details
**What goes wrong:** `HTTPException(detail=str(e))` patterns remain after adding generic handler.
**Why it happens:** Multiple exception handlers throughout routes, some still using raw exception strings.
**How to avoid:** Audit all exception handlers in `main.py` — lines 237, 264, 313, 346, 394 per CONCERNS.md.
**Warning signs:** DeGiro API error responses visible in client responses.

### Pitfall 4: CORS misconfiguration allows unintended cross-origin access
**What goes wrong:** `allow_origins=["*"]` or overly permissive configuration.
**Why it happens:** Development convenience in CORS setup, not locked down for production.
**How to avoid:** Default to same-origin only, require explicit env var for cross-origin Hermes calls.
**Warning signs:** Unexpected domains in `Access-Control-Allow-Origin` headers.

### Pitfall 5: .dockerignore still includes debug scripts after deletion
**What goes wrong:** Files deleted from `app/` but already in Docker image layers, or `.dockerignore` not updated.
**Why it happens:** Git-tracked deletes don't automatically remove from Docker context.
**How to avoid:** Verify `.dockerignore` excludes `app/debug*.py` and `app/test*.py`, and rebuild image from clean state.
**Warning signs:** `docker compose build --no-cache` still includes debug scripts in image.

---

## Code Examples

### Auth dependency (SEC-03)
```python
# Source: FastAPI Depends pattern, adapted from project conventions
async def verify_brok_token(request: Request):
    """Validate BROKR_AUTH_TOKEN bearer token on /api/* routes."""
    token = os.getenv("BROKR_AUTH_TOKEN", "")
    
    # Token not configured — block all API requests
    if not token:
        logger.warning("BROKR_AUTH_TOKEN not configured — blocking API request")
        raise HTTPException(status_code=401, detail="Authentication required")
    
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth format")
    
    provided = auth_header[7:]
    if not hmac.compare_digest(provided, token):
        raise HTTPException(status_code=401, detail="Invalid token")

# Apply to all /api/* routes:
@app.get("/api/portfolio", dependencies=[Depends(verify_brok_token)])
async def get_portfolio():
    ...
```

### Exception sanitization (D-10)
```python
# Source: Project convention from CONCERNS.md H-05 fix approach
except Exception as e:
    logger.error("Portfolio fetch error: %s", str(e))
    raise HTTPException(status_code=500, detail="Failed to fetch portfolio")
```

### Bind address configuration (SEC-04)
```python
# In Dockerfile CMD or docker-compose:
# CMD ["uvicorn", "app.main:app", "--host", os.getenv("HOST", "127.0.0.1"), "--port", "8000"]

# Or in docker-compose.yml command override:
command: ["uvicorn", "app.main:app", "--host", "${HOST:-127.0.0.1}", "--port", "8000"]
```

---

## Assumptions Log

> List all claims tagged `[ASSUMED]` in this research. The planner and discuss-phase use this section to identify decisions that need user confirmation before execution.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | FastAPI 0.115.6 is the installed version (from requirements.txt) | Standard Stack | MEDIUM — if version differs, some middleware API may vary |
| A2 | `hmac` module from Python stdlib is available for timing-safe comparison | Don't Hand-Roll | LOW — stdlib always available |
| A3 | `.dockerignore` already exists and contains `__pycache__` entry | Common Pitfalls | LOW — verified to exist with content |

**If this table is empty:** All claims in this research were verified or cited — no user confirmation needed.

---

## Open Questions

1. **CORS allowed origins format**
   - What we know: Default to same-origin, configurable via env for Hermes
   - What's unclear: Should `CORS_ALLOWED_ORIGINS` be a comma-separated string or JSON array?
   - Recommendation: Comma-separated string (`http://localhost:8000,https://hermes.local`) for simplicity

2. **BROKR_AUTH_TOKEN generation**
   - What we know: User must set it for production, defaults to empty (disabled) in dev
   - What's unclear: Should the app generate a random token on first startup if none is set?
   - Recommendation: No auto-generation — require explicit production setup per D-01

3. **HSTS in development**
   - What we know: HSTS header should be added, but only effective when TLS-terminated
   - What's unclear: Should HSTS header be conditional on TLS, or always set?
   - Recommendation: Always set, but `max-age=0` when TLS not detected (development mode)

---

## Environment Availability

Step 2.6: SKIPPED (no external dependencies beyond Python packages already in requirements.txt)

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | YES | Static bearer token via FastAPI dependency |
| V3 Session Management | NO | Single-user app, no sessions stored |
| V4 Access Control | YES | Auth middleware on `/api/*` routes |
| V5 Input Validation | YES | Pydantic models with min_length/max_length on AuthRequest/SessionRequest |
| V6 Cryptography | YES | `hmac.compare_digest` for timing-safe token comparison, HTTPS/TLS required upstream |

### Known Threat Patterns for FastAPI/uvicorn

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Credential exposure via debug endpoint | Information Disclosure | Remove endpoint entirely (D-04) |
| Session ID exposure via debug endpoint | Information Disclosure | Remove endpoint entirely (D-04) |
| Token brute-force via timing attack | Information Disclosure | `hmac.compare_digest` (timing-safe) |
| Cross-origin API abuse | Elevation of Privilege | CORS middleware, same-origin default |
| Clickjacking | Tampering | `X-Frame-Options: DENY` header |
| MIME-type sniffing | Tampering | `X-Content-Type-Options: nosniff` header |
| XSS via CDN compromise | Tampering | CSP header, consider SRI hashes (Phase 5) |
| Exception details in responses | Information Disclosure | Generic error messages + server-side logging |

---

## Sources

### Primary (HIGH confidence)
- `app/main.py` — existing FastAPI app structure, route handlers, session cache patterns
- `app/degiro_client.py` — debug_login_variants function, request_payload structure
- `Dockerfile` — current Docker image build, no debug exclusion
- `.dockerignore` — current exclusion list (only `.git`, `.env`, `__pycache__`, etc.)
- `.planning/codebase/CONCERNS.md` — C-01 through C-04 critical issues, H-02 CORS, H-03 security headers, H-05 exception leakage
- `.planning/phases/01-security-hardening/01-CONTEXT.md` — D-01 through D-10 implementation decisions
- `.planning/phases/01-security-hardening/01-DISCUSSION-LOG.md` — alternatives considered, user choices

### Secondary (MEDIUM confidence)
- [FastAPI Security docs](https://fastapi.tiangolo.com/tutorial/security/) — dependency pattern for auth
- [OWASP Security Headers](https://owasp.org/www-project-secure-headers/) — header recommendations

### Tertiary (LOW confidence)
- WebSearch for FastAPI CORS middleware patterns — verified against FastAPI official docs

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — existing project with pinned versions in requirements.txt
- Architecture: HIGH — FastAPI patterns well-established, implementation decisions locked
- Pitfalls: HIGH — based on verified CONCERNS.md audit

**Research date:** 2026-04-23
**Valid until:** 2026-05-23 (security patterns stable, no fast-moving dependencies)