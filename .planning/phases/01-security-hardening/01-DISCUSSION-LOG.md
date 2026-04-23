# Phase 01: Security Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-23
**Phase:** 01-security-hardening
**Areas discussed:** Auth token design, Debug endpoint fate, Debug scripts handling

---

## Auth Token Design

| Option | Description | Selected |
|--------|-------------|----------|
| Static bearer token | Random string in BROKR_AUTH_TOKEN, checked via middleware. Simple, works for single-user production. | ✓ |
| HMAC signature token | Server generates a signed token on first auth and validates signature on subsequent requests. More complex. | |
| JWT with expiry | Token generated and rotated periodically, with session storage. Overkill for single-user localhost app. | |
| Different approach | Clarify the approach | |

**User's choice:** Static bearer token (Recommended)
**Notes:** Simple is best for single-user app. No need for complexity of JWT or HMAC.

---

## Auth Token Scope

| Option | Description | Selected |
|--------|-------------|----------|
| API-only | Less code, consistent. /health and static remain open for monitoring and assets. | ✓ |
| All endpoints | Everything requires auth including health checks and CSS/JS. More secure but monitoring gets harder. | |

**User's choice:** API-only (Recommended)
**Notes:** Monitoring (health endpoint) and static assets (CSS/JS) don't need auth.

---

## Auth Token Implementation Location

| Option | Description | Selected |
|--------|-------------|----------|
| Middleware dependency | Single point of validation, applied to /api/* before route handlers. Cleaner. | ✓ |
| Per-endpoint dependency | Each route manually checks headers. More verbose, easier to forget to add. | |
| Env-gated middleware | Conditional decorator approach | |

**User's choice:** Middleware dependency (Recommended)
**Notes:** Single FastAPI dependency that wraps all /api/* routes. Clean and centralized.

---

## Debug Endpoint Fate

| Option | Description | Selected |
|--------|-------------|----------|
| Remove entirely | Minimal attack surface, addresses C-01/C-02. Diagnostic value lost but C-05 (M-01) already covers that concern. | ✓ |
| Gate behind auth token | Wrap behind BROKR_AUTH_TOKEN. Can only be called if auth token is provided. Diagnostic use preserved. | |
| Redact only, keep endpoint | Keep it but remove request_payload and session_id from responses. Still leaves endpoint surface but without credential exposure. | |

**User's choice:** Remove entirely (Recommended)
**Notes:** The debug endpoint's attack surface (plaintext passwords and session IDs in responses) is completely eliminated by removal.

---

## Debug Scripts Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Delete them | Clean, minimal. Can't run them via exec but they're still in git history. | ✓ |
| Relocate and dockerignore | Move out of app/ to project root or a scripts/ dir that's dockerignored. | |
| Dockerignore only | Keep in app/ but exclude from Docker via .dockerignore | |

**User's choice:** Delete them (Recommended)
**Notes:** Scripts are deleted entirely. If diagnostic scripts are needed for dev, they should live outside app/ in a scripts/ directory excluded from Docker.

---

## Deferred Ideas

No scope creep detected during discussion. All suggestions were either already in scope or noted as belonging to other phases.