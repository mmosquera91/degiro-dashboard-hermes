# Roadmap: Brokr

**Created:** 2026-04-23
**Project:** Portfolio analytics dashboard for DeGiro
**Granularity:** Coarse

## Milestones

- ✅ **v1.0 MVP** — Phases 1-6 (shipped 2026-04-24)
- ⏳ **v1.1 Dashboard & Persistence Fix** — Phases 7-10

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-6) — SHIPPED 2026-04-24</summary>

- [x] Phase 1: Security Hardening (2/2 plans) — completed 2026-04-23
- [x] Phase 2: Performance (2/2 plans) — completed 2026-04-23
- [x] Phase 3: Health Indicators (2/2 plans) — completed 2026-04-23
- [x] Phase 4: Benchmark Tracking (5/5 plans) — completed 2026-04-23
- [x] Phase 5: Dashboard Polish (2/2 plans) — completed 2026-04-24
- [x] Phase 6: Testing (4/4 plans) — completed 2026-04-24

</details>

### v1.1 Dashboard & Persistence Fix (Phases 7-10)

- [x] **Phase 7: Snapshot Format Extension** — Persist full portfolio data in snapshots with atomic writes (completed 2026-04-24)
- [x] **Phase 8: Startup Portfolio Restoration** — Restore portfolio on app startup from latest snapshot (completed 2026-04-24; gap closure in progress)
- [x] **Phase 9: Data Enrichment & Scoring Fixes** — Fix silent yfinance failures and scoring None pollution (completed 2026-04-30)
- [x] **Phase 10: Frontend Dashboard Verification** — Verify charts render with real data and handle missing data gracefully (completed 2026-04-30)

## Phase Details

### Phase 7: Snapshot Format Extension
**Goal**: Extended snapshot format stores full enriched portfolio data and uses atomic writes for crash safety
**Depends on**: Nothing (first v1.1 phase)
**Requirements**: SNAP-01, SNAP-02, SNAP-03, DOCK-01, DOCK-02
**Success Criteria** (what must be TRUE):
  1. `save_snapshot()` accepts and writes full `portfolio_data` dict including positions, sector_breakdown, and allocation
  2. `load_latest_snapshot()` reads most recent snapshot and returns portfolio data
  3. Snapshot writes use atomic rename (temp file + rename) to prevent corruption on crash
  4. `docker-compose.yml` has named volume or bind mount for `/data/snapshots`
  5. Snapshot directory survives `docker-compose down -v`
**Plans**: 3 plans
Plans:
- [x] 07-01-PLAN.md — Docker named volume configuration
- [x] 07-02-PLAN.md — Snapshot module extension (save_snapshot + load_latest_snapshot + atomic writes)
- [x] 07-03-PLAN.md — Integration into get_portfolio() and test scaffold
**UI hint**: no

### Phase 8: Startup Portfolio Restoration
**Goal**: Dashboard serves last-known portfolio immediately after container restart without requiring DeGiro session
**Depends on**: Phase 7
**Requirements**: REST-01, REST-02, REST-03
**Success Criteria** (what must be TRUE):
  1. `@app.on_event("startup")` loads latest snapshot and restores portfolio into `_session["portfolio"]`
  2. Dashboard renders with last-known portfolio immediately after restart (no 401 error)
  3. When session is expired but cached portfolio exists, dashboard serves cached portfolio (no 401)
  4. Session TTL check does not block serving fresh cached portfolio
**Plans**: 3 plans
Plans:
- [x] 08-01-PLAN.md — Startup portfolio restoration via on_startup event
- [x] 08-02-PLAN.md — Workspace-relative snapshot dir + WARNING log
- [x] 08-03-PLAN.md — Directory auto-creation + ERROR log + file existence check
**UI hint**: no

### Phase 9: Data Enrichment & Scoring Fixes
**Goal**: Per-stock metrics display actual values when data is available and explicit "No data" when enrichment fails
**Depends on**: Phase 7 (snapshot must include position data for Phase 10 verification)
**Requirements**: ENR-01, ENR-02, ENR-03
**Success Criteria** (what must be TRUE):
  1. yfinance enrichment failures populate `_enrichment_error` field on position (not silent WARNING)
  2. Dashboard displays "No data" for positions with enrichment failures (not "-")
  3. Scoring normalization excludes positions with None values (None positions do not pollute normalization pool)
**Plans**: TBD
**UI hint**: no

### Phase 10: Frontend Dashboard Verification
**Goal**: Sector and benchmark charts render correctly; per-stock metrics visible when data available
**Depends on**: Phase 8 (requires portfolio restored in session)
**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04, DASH-05
**Success Criteria** (what must be TRUE):
  1. Sector breakdown doughnut chart renders from `portfolio["sector_breakdown"]`
  2. Benchmark comparison line chart renders from `/api/benchmark` data (requires 2+ snapshots)
  3. Per-stock RSI displays actual value when yfinance enrichment succeeds
  4. Per-stock Weight, Momentum Score, Buy Priority Score display correctly when scoring completes
  5. Charts show "No data available" message when data is unavailable (not blank/empty)
**Plans**: TBD
**UI hint**: yes

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 7. Snapshot Format Extension | 3/3 | Complete    | 2026-04-24 |
| 8. Startup Portfolio Restoration | 2/3 | Gap closure | 2026-04-24 |
| 9. Data Enrichment & Scoring Fixes | ~80% | Complete — enrichment_error field added; "No data" UI added via quick task | 2026-04-30 |
| 10. Frontend Dashboard Verification | ~80% | Complete — chart-empty state added for empty benchmark/sector charts | 2026-04-30 |

---

*Roadmap created: 2026-04-23*
*Last updated: 2026-04-30 — v1.1 complete*
*Gaps remaining: none — all gaps closed*

---

## Future Enhancements (v1.2+)

### Multi-day Snapshot History + Portfolio Performance Trends
- Daily portfolio value indexed to 100 (first snapshot baseline)
- Rolling 7/30-day vs S&P 500 performance
- Drawdown heatmap + daily breakdown table
- New `/api/portfolio-history` endpoint

### Historical Per-Position Attribution Charts
- Time-series attribution (position × day matrix)
- Waterfall charts (daily contribution to total return)
- Top/bottom movers heatmap
- `/api/position-history` endpoint from snapshot positions

*Estimated: 4 phases, 2 days effort*
