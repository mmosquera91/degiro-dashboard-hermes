# Requirements: Brokr

**Defined:** 2026-04-24
**Core Value:** Reliable portfolio health visibility — seeing risk and performance signals at a glance.

## v1.1 Requirements

Requirements for v1.1 milestone — Dashboard Fix & Persistence.

### Data Enrichment & Scoring

- [ ] **ENR-01**: yfinance enrichment failures are logged with `_enrichment_error` field per position (not silent WARNING only)
- [ ] **ENR-02**: Positions with enrichment failures display "No data" instead of "-" in dashboard
- [ ] **ENR-03**: Scoring normalization excludes positions with None values (not converted to 0 before normalization)

### Snapshot Persistence

- [ ] **SNAP-01**: `save_snapshot()` accepts full `portfolio_data` dict (positions, sector_breakdown, allocation)
- [ ] **SNAP-02**: `load_latest_snapshot()` reads and returns the most recent snapshot with portfolio data
- [ ] **SNAP-03**: Snapshot writes use atomic rename (write to temp, then rename) to prevent corruption on crash
- [ ] **SNAP-04**: `docker-compose.yml` has `./snapshots:/data/snapshots` volume mount so snapshots survive container restarts

### Startup Restoration

- [ ] **REST-01**: `@app.on_event("startup")` calls `load_latest_snapshot()` and restores portfolio into `_session["portfolio"]`
- [ ] **REST-02**: Dashboard serves last-known portfolio immediately after restart (no DeGiro session required)
- [ ] **REST-03**: Session TTL check does not block serving fresh cached portfolio (401 only when both session expired AND no cached portfolio)

### Dashboard Visualization

- [ ] **DASH-01**: Sector breakdown doughnut chart renders correctly from `portfolio["sector_breakdown"]`
- [ ] **DASH-02**: Benchmark comparison line chart renders from `/api/benchmark` data (needs 2+ snapshots)
- [ ] **DASH-03**: Per-stock RSI displays correctly (not "-") when yfinance enrichment succeeds
- [ ] **DASH-04**: Per-stock Weight, Momentum Score, Buy Priority Score display correctly (not "-") when scoring completes
- [ ] **DASH-05**: Charts show "No data available" message when data is unavailable (not blank/empty)

### Docker Configuration

- [ ] **DOCK-01**: `docker-compose.yml` includes named volume or bind mount for `/data/snapshots`
- [ ] **DOCK-02**: Snapshot directory survives `docker-compose down -v` (named volume preferred over anonymous)

## v2 Requirements

Deferred to future release.

### Session Management

- **AUTH-01**: DeGiro session auto-reauth when expiry detected (no manual re-auth required)
- **AUTH-02**: Dynamic FX rate refresh on-demand (not cached stale)

### Historical Analysis

- **HIST-01**: Historical portfolio snapshots viewer (trend analysis)
- **HIST-02**: Export performance history to CSV/JSON

### Benchmark & Attribution

- **BENC-01**: Store benchmark series to disk to survive restarts
- **BENC-02**: Attribution dashboard with per-position contribution

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-user / multi-account support | Single user for now |
| Real-time price streaming | yfinance polling sufficient |
| Database / persistent storage | JSON snapshots sufficient for single-user |
| Mobile app | Web-only, responsive sufficient |
| Hermes-side AI logic | Brokr only provides portfolio data |
| Brokerage trading | Read-only analytics |
| Additional broker integrations | DeGiro only |
| SQLite/Redis for session storage | Over-engineering for single-user |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ENR-01 | Phase 9 | Pending |
| ENR-02 | Phase 9 | Pending |
| ENR-03 | Phase 9 | Pending |
| SNAP-01 | Phase 7 | Pending |
| SNAP-02 | Phase 7 | Pending |
| SNAP-03 | Phase 7 | Pending |
| SNAP-04 | Phase 7 | Pending |
| REST-01 | Phase 8 | Pending |
| REST-02 | Phase 8 | Pending |
| REST-03 | Phase 8 | Pending |
| DASH-01 | Phase 10 | Pending |
| DASH-02 | Phase 10 | Pending |
| DASH-03 | Phase 10 | Pending |
| DASH-04 | Phase 10 | Pending |
| DASH-05 | Phase 10 | Pending |
| DOCK-01 | Phase 7 | Pending |
| DOCK-02 | Phase 7 | Pending |

**Coverage:**
- v1.1 requirements: 17 total
- Mapped to phases: 17
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-24*
*Last updated: 2026-04-24 after research synthesis*
