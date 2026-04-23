# Roadmap: Brokr

**Created:** 2026-04-23
**Project:** Portfolio analytics dashboard for DeGiro
**Granularity:** Coarse (6 phases, 2-4 plans each)

## Phase Overview

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 1 | Security Hardening | Fix critical credential exposure and API auth gaps | SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, SEC-06 | 6/6 |
| 2 | Performance | Fix blocking I/O and thread safety issues | PERF-01, PERF-02, PERF-03 | 3/3 |
| 3 | Health Indicators | Add concentration, sector, drawdown alerts | HEALTH-01, HEALTH-02, HEALTH-03, HEALTH-04 | 4/4 [x] (2026-04-23) |
| 4 | Benchmark Tracking | S&P 500 comparison, historical performance | TRACK-01, TRACK-02, TRACK-03 | 3/3 |
| 5 | Dashboard Polish | Toasts, error states, responsive improvements | DASH-01, DASH-02, DASH-03 | 3/3 |
| 6 | Testing | Automated tests for core logic | TEST-01, TEST-02, TEST-03 | 3/3 |

**Total:** 6 phases | 22 requirements | All covered ✓

---

## Phase 1: Security Hardening

**Goal:** Fix critical credential exposure vulnerabilities and add API authentication before any production exposure.

**Requirements:** SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, SEC-06

**Success Criteria:**
1. `/api/debug-login` no longer returns `request_payload` with plaintext passwords
2. `session_id` is redacted from all debug/error responses
3. All API endpoints validate `BROKR_AUTH_TOKEN` from environment
4. FastAPI binds to 127.0.0.1 by default (configurable via HOST env)
5. Debug scripts (`debug_*.py`) removed from production Docker image
6. Security headers (HSTS, X-Content-Type-Options, X-Frame-Options) and CORS policy added

**Implementation Notes:**
- Phase 1 is blocking — no production exposure until complete
- BROKR_AUTH_TOKEN defaults to empty (disabled) in dev, must be set for production
- CORS policy defaults to same-origin, configurable for Hermes integration

---

## Phase 2: Performance

**Goal:** Fix blocking I/O in yfinance enrichment and thread safety issues in session/FX cache.

**Requirements:** PERF-01, PERF-02, PERF-03

**Success Criteria:**
1. `market_data.enrich_positions()` runs in thread pool (asyncio.to_thread or concurrent.futures.ThreadPoolExecutor)
2. Session cache (`_session` dict) is fully thread-safe with no race conditions
3. FX rate cache is thread-safe with proper locking

**Implementation Notes:**
- Use `asyncio.to_thread()` for non-blocking yfinance calls
- Or use `concurrent.futures.ThreadPoolExecutor` with bounded queue
- Profile before/after to verify event loop no longer blocks
- Add load test to verify thread safety under concurrent requests

---

## Phase 3: Health Indicators

**Goal:** Add portfolio health monitoring signals for concentration risk, sector weighting, drawdown, and rebalancing.

**Requirements:** HEALTH-01, HEALTH-02, HEALTH-03, HEALTH-04

**Success Criteria:**
1. Alert triggers when any single position exceeds 20% of portfolio value
2. Alert triggers when any sector exceeds 40% of portfolio value
3. Alert triggers when portfolio drawdown exceeds -10% from peak
4. Rebalancing suggestions appear when actual allocations drift >5% from target weights

**Implementation Notes:**
- Alerts should appear in dashboard UI and be included in Hermes context
- Configurable thresholds via environment variables (no hardcoding)
- Consider both absolute thresholds and relative drift detection

---

## Phase 4: Benchmark Tracking

**Goal:** Add S&P 500 / MSCI World benchmark comparison and historical performance tracking.

**Requirements:** TRACK-01, TRACK-02, TRACK-03

**Success Criteria:**
1. Dashboard shows S&P 500 (or configurable benchmark) performance overlaid with portfolio
2. Historical performance chart displays portfolio value over time vs benchmark
3. Attribution view shows which positions contributed most to gains/losses

**Implementation Notes:**
- Use yfinance to fetch benchmark data (^GSPC for S&P 500)
- Store historical snapshots (could use simple JSON file, not full database)
- Attribution = position return x position weight x direction

**Plans:** 3 plans

Plans:
- [ ] 04-01-PLAN.md — Backend: snapshot module + /api/benchmark endpoint + snapshot-on-refresh
- [ ] 04-02-PLAN.md — Frontend: benchmark chart + attribution table UI
- [ ] 04-03-PLAN.md — Hermes context: extend build_hermes_context() with benchmark + attribution

---

## Phase 5: Dashboard Polish

**Goal:** Replace browser alerts with toast notifications, improve error states, fix responsive issues.

**Requirements:** DASH-01, DASH-02, DASH-03

**Success Criteria:**
1. All browser `alert()` calls replaced with toast notifications (non-blocking)
2. API failures show graceful degradation with retry option, not blank screen
3. Dashboard is usable on 768px tablet and 420px mobile viewports

**Implementation Notes:**
- Toast library or simple custom implementation (no heavy dependency)
- Error states should show last valid data with "stale" indicator
- Test on actual mobile/tablet or use browser dev tools responsive mode

---

## Phase 6: Testing

**Goal:** Add automated test coverage for core logic modules.

**Requirements:** TEST-01, TEST-02, TEST-03

**Success Criteria:**
1. Tests for `scoring.py` — compute_scores, compute_momentum_score, compute_value_score
2. Tests for `market_data.py` — enrich_position, get_fx_rate, compute_rsi
3. Tests for `degiro_client.py` — portfolio parsing, position field extraction

**Implementation Notes:**
- Use pytest as test framework
- Mock yfinance and degiro-connector for deterministic tests
- Store tests in `app/test_*.py` or `tests/` directory
- CI should run tests before any phase commit

---

## Phase Dependencies

```
Phase 1 (Security) ──┬──► Phase 2 (Performance)
                     │          │
                     │          ▼
                     │    Phase 3 (Health)
                     │          │
                     ▼          ▼
                Phase 4 (Benchmark)
                     │
                     ▼
                Phase 5 (Dashboard)
                     │
                     ▼
                Phase 6 (Testing)
```

**Dependency rationale:**
- Phase 1 must complete before any production exposure
- Phase 2 fixes are needed before Phase 3 (health indicators use enrichment)
- Phase 3 and 4 can run in parallel after Phase 2
- Phase 5 (Dashboard) depends on Phase 3/4 data
- Phase 6 (Testing) should happen after functional phases complete

---
*Roadmap created: 2026-04-23*
*Last updated: 2026-04-23 after research synthesis*
