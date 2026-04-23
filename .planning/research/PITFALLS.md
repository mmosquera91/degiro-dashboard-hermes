# Pitfalls

**Research Date:** 2026-04-23
**Project:** Brokr — Portfolio analytics dashboard for DeGiro

## Critical Mistakes

### C-01: Credential Exposure in Debug Endpoint
- **Warning signs**: Debug endpoint returns request payloads with plaintext passwords
- **Prevention**: Never include `request_payload` in debug results, gate debug endpoints behind env flags
- **Phase**: Phase 1 (Security) — must fix before any production exposure

### C-02: Session ID Exposure
- **Warning signs**: Login success models expose `session_id` in debug responses
- **Prevention**: Redact or omit session IDs from any debug or error output
- **Phase**: Phase 1 (Security)

### C-03: No API Authentication
- **Warning signs**: All endpoints publicly accessible, no token checks
- **Prevention**: Add BROKR_AUTH_TOKEN environment variable, validate on all API calls
- **Phase**: Phase 1 (Security)

### C-04: Plaintext HTTP in Production
- **Warning signs**: Credentials sent over HTTP, no TLS enforcement
- **Prevention**: Bind to 127.0.0.1, document TLS requirement, add security headers
- **Phase**: Phase 1 (Security)

## Common Implementation Mistakes

### Blocking I/O in Event Loop
- **Warning signs**: yfinance calls block FastAPI event loop, dashboard hangs during enrichment
- **Prevention**: Run market_data.enrich_positions() in thread pool (asyncio.to_thread or concurrent.futures)
- **Phase**: Phase 2 (Performance)

### Thread Safety in Session Cache
- **Warning signs**: Race conditions when multiple requests access _session dict simultaneously
- **Prevention**: threading.Lock around all _session accesses, verify in load testing
- **Phase**: Phase 2 (Performance) or Phase 1 if security issue

### Rate Limiting in Market Data
- **Warning signs**: yfinance returns errors after too many rapid requests
- **Prevention**: 0.25s delay between yfinance calls (already implemented), add retry with backoff
- **Phase**: Phase 2 (Performance)

## Domain-Specific Pitfalls

### DeGiro Session Management
- **Warning signs**: Session expires mid-use, authentication fails after period
- **Prevention**: Monitor session TTL, implement session refresh flow, handle 401 gracefully
- **Phase**: Phase 1 or 2

### yfinance Data Quality
- **Warning signs**: Missing prices for some tickers, stale data returned
- **Prevention**: Validate data freshness, handle None values in enrichment, show "N/A" in UI
- **Phase**: Phase 2 or 3

### Multi-Currency Portfolio
- **Warning signs**: FX rates stale, conversion calculations incorrect
- **Prevention**: Cache FX rates with TTL, fetch from reliable source, log when rates are old
- **Phase**: Phase 2 or 3

## Anti-Patterns to Avoid

1. **Debug scripts in production image** — Remove debug_*.py before building production Docker image
2. **Hardcoded credentials** — Always use environment variables for secrets
3. **Blocking enrichment in request path** — Async/thread pool for yfinance calls
4. **No error boundaries** — Uncaught exceptions crash the dashboard
5. **No input validation** — DeGiro API responses assumed to be well-formed

## Phase Mapping

| Pitfall | Phase | Notes |
|---------|-------|-------|
| Credential exposure | Phase 1 | Critical, must fix first |
| Session ID exposure | Phase 1 | Critical |
| No API auth | Phase 1 | Critical |
| Plaintext HTTP | Phase 1 | Critical |
| Blocking I/O | Phase 2 | Performance |
| Thread safety | Phase 1 or 2 | Security/performance |
| Rate limiting | Phase 2 | Performance |

---
*Synthesized from codebase CONCERNS.md analysis: 2026-04-23*