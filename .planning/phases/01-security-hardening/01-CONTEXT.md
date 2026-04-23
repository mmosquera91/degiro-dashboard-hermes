# Phase 01: Security Hardening - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix critical credential exposure vulnerabilities and add API authentication before any production exposure. Delivers SEC-01 through SEC-06:
- Remove `request_payload` from debug endpoint (SEC-01) + redact `session_id` (SEC-02)
- Add `BROKR_AUTH_TOKEN` env var and validate on all API endpoints (SEC-03)
- Bind FastAPI to 127.0.0.1 by default via HOST env (SEC-04)
- Remove debug scripts from production Docker image (SEC-05)
- Add security headers and CORS policy (SEC-06)

</domain>

<decisions>
## Implementation Decisions

### Auth Token Design (SEC-03)

- **D-01:** `BROKR_AUTH_TOKEN` is a **static bearer token** — a random string set via environment variable. No signature, no expiry, no session storage.
- **D-02:** Auth token validation via **FastAPI dependency middleware** — applied to all `/api/*` routes. Single point of validation, cleaner than per-endpoint checks.
- **D-03:** Token **protects API endpoints only** (`/api/*`). `/health` and `/static/*` remain open — monitoring and assets don't require auth.

### Debug Endpoint (SEC-01, SEC-02)

- **D-04:** `/api/debug-login` is **removed entirely** — not gated, not redacted. The endpoint's attack surface (exposing plaintext passwords and session IDs in responses) is eliminated. Diagnostic value is sacrificed for minimal attack surface.

### Debug Scripts (SEC-05)

- **D-05:** Debug scripts (`debug_portfolio.py`, `debug_raw_portfolio.py`, `debug_from_session.py`, `debug_int_account.py`, `test_auth_methods.py`, `test_login.py`) are **deleted** from `app/`. Not relocated, not dockerignored — removed.
- **D-06:** Development utility scripts that are needed should be placed outside `app/` in a `scripts/` directory that is excluded from the Docker image via `.dockerignore`.

### Bind Address (SEC-04)

- **D-07:** FastAPI binds to `127.0.0.1` by default. Configurable via `HOST` environment variable.

### Security Headers (SEC-06)

- **D-08:** `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security` (when TLS-terminated upstream), and `Content-Security-Policy` headers added via middleware. Exact header values deferred to planner.
- **D-09:** CORS defaults to `same-origin`. Configurable via environment variable for Hermes integration.

### Error Responses

- **D-10:** Exception handlers return **generic user-facing messages** — internal details (DeGiro API errors, Python tracebacks) are logged server-side only, not returned to client.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Security Concerns
- `.planning/codebase/CONCERNS.md` — Full severity-coded concern list (C-01 through C-04 are the critical issues this phase addresses)

### Project Context
- `.planning/PROJECT.md` — Project overview, single-user architecture, Hermes integration context
- `.planning/ROADMAP.md` §Phase 1 — Phase goal, success criteria, implementation notes

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_session_lock` (threading.Lock in main.py) — existing synchronization primitive for thread-safe operations
- FastAPI middleware pattern — `DependencyMiddleware` approach available for auth validation
- Pydantic `BaseModel` for request/response — `AuthRequest` already exists and can be extended

### Established Patterns
- Thread-safe session cache with `threading.Lock` — pattern already in place
- Environment variable configuration via `os.getenv` / `pydantic BaseModel` field defaults

### Integration Points
- All `/api/*` routes in `main.py` — middleware applied at this layer
- `app/main.py` line 378-394 — debug_login endpoint to remove
- `app/` — debug scripts to delete

</code_context>

<specifics>
## Specific Ideas

No specific references or "I want it like X" moments from discussion — all decisions followed straightforward security best practices.

</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
None — discussion stayed within phase scope.

### CORS Configuration
CORS was not selected for discussion. Default to `same-origin` with `CORS_CONFIG` env for Hermes cross-origin calls. Planner handles.

</deferred>

---

*Phase: 01-security-hardening*
*Context gathered: 2026-04-23*