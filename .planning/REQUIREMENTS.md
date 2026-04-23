# Requirements: Brokr

**Defined:** 2026-04-23
**Core Value:** Reliable portfolio health visibility — seeing risk and performance signals at a glance

## v1 Requirements

### Security (SEC)

- [x] **SEC-01
**: Remove `request_payload` from debug endpoint responses — prevent plaintext password exposure
- [x] **SEC-02
**: Redact or omit `session_id` from all debug/error responses
- [x] **SEC-03
**: Add `BROKR_AUTH_TOKEN` environment variable and validate on all API endpoints
- [ ] **SEC-04**: Bind FastAPI to 127.0.0.1 by default — prevent network exposure without TLS
- [ ] **SEC-05**: Remove debug scripts (`debug_*.py`) from production Docker image
- [x] **SEC-06
**: Add security headers (HSTS, X-Content-Type-Options, etc.) and CORS policy

### Performance (PERF)

- [ ] **PERF-01**: Run `market_data.enrich_positions()` in thread pool — prevent event loop blocking
- [ ] **PERF-02**: Fix thread safety issues in session cache (`_session` dict with threading.Lock)
- [ ] **PERF-03**: Fix thread safety issues in FX rate cache

### Health Indicators (HEALTH)

- [ ] **HEALTH-01**: Concentration risk alert — warn when single position exceeds 20% of portfolio
- [ ] **HEALTH-02**: Sector weighting alert — warn when sector exceeds threshold (e.g., 40%)
- [ ] **HEALTH-03**: Drawdown alert — warn when portfolio drawdown exceeds threshold (e.g., -10%)
- [ ] **HEALTH-04**: Rebalancing signal — suggest when allocations drift too far from target weights

### Performance Tracking (TRACK)

- [ ] **TRACK-01**: Benchmark comparison — S&P 500 / MSCI World performance overlay
- [ ] **TRACK-02**: Historical performance chart — portfolio value over time vs benchmark
- [ ] **TRACK-03**: Attribution analysis — which positions contributed most to gains/losses

### Dashboard (DASH)

- [ ] **DASH-01**: Toast notifications — non-blocking feedback replacing browser alerts
- [ ] **DASH-02**: Better error states — graceful degradation when API calls fail
- [ ] **DASH-03**: Responsive improvements — work on mobile and tablet viewports

### Testing (TEST)

- [ ] **TEST-01**: Automated tests for scoring logic (`scoring.py`)
- [ ] **TEST-02**: Automated tests for market data enrichment (`market_data.py`)
- [ ] **TEST-03**: Automated tests for portfolio parsing (`degiro_client.py`)

## v2 Requirements

### Multi-Currency
- **CURR-01**: Dynamic FX rate refresh — fetch latest rates on demand, not cached stale
- **CURR-02**: Support additional currencies beyond EUR

### Historical Data
- **HIST-01**: Store historical portfolio snapshots for trend analysis
- **HIST-02**: Export performance history to CSV/JSON

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-user support | Single user for now, architecture can evolve later |
| Real-time price streaming | yfinance polling is sufficient |
| Database/persistent storage | In-memory cache acceptable for single-user |
| Mobile native app | Web-only, responsive is sufficient |
| Brokerage trading | Read-only analytics, no execution |
| Multiple broker integrations | DeGiro only for now |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SEC-01 | Phase 1 | Pending |
| SEC-02 | Phase 1 | Pending |
| SEC-03 | Phase 1 | Pending |
| SEC-04 | Phase 1 | Pending |
| SEC-05 | Phase 1 | Pending |
| SEC-06 | Phase 1 | Pending |
| PERF-01 | Phase 2 | Pending |
| PERF-02 | Phase 2 | Pending |
| PERF-03 | Phase 2 | Pending |
| HEALTH-01 | Phase 3 | Pending |
| HEALTH-02 | Phase 3 | Pending |
| HEALTH-03 | Phase 3 | Pending |
| HEALTH-04 | Phase 3 | Pending |
| TRACK-01 | Phase 4 | Pending |
| TRACK-02 | Phase 4 | Pending |
| TRACK-03 | Phase 4 | Pending |
| DASH-01 | Phase 5 | Pending |
| DASH-02 | Phase 5 | Pending |
| DASH-03 | Phase 5 | Pending |
| TEST-01 | Phase 6 | Pending |
| TEST-02 | Phase 6 | Pending |
| TEST-03 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 20 total
- Mapped to phases: 20
- Unmapped: 0 ✓

---
*Requirements synthesized from PROJECT.md Active items and research: 2026-04-23*
*Last updated: 2026-04-23 after research synthesis*