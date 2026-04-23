---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: Ready to discuss next phase
stopped_at: Phase 04 benchmark tracking complete
last_updated: "2026-04-23T19:53:00.000Z"
progress:
  total_phases: 6
  completed_phases: 4
  total_plans: 9
  completed_plans: 9
  percent: 100
---

# State

## Project Reference

**Brokr** — Portfolio analytics dashboard for DeGiro stocks/ETFs. Provides portfolio metrics, health indicators, performance tracking, and an API endpoint for the Hermes AI agent.

**Core Value:** Reliable portfolio health visibility — seeing risk and performance signals at a glance.

## Current Position

- **Phase:** 4 of 6 (Benchmark Tracking) — Complete
- **Status:** Ready to discuss next phase

## Progress

```
[████████░░░░░░] 67% — Phase 4 (Benchmark Tracking) complete — ready for Phase 5
```

## Recent Decisions

- DeGiro auth via intAccount + JSESSIONID (not username/password) — works reliably
- Vanilla JS frontend (no framework) — no build step, keeps Docker image small
- In-memory session cache (no database) — acceptable for single-user use case
- Hermes integration via REST API — Hermes calls Brokr, not push
- Fix security issues before adding features — critical credential exposure must be addressed first
- 6-phase coarse roadmap: Security → Performance → Health → Benchmark → Dashboard → Testing
- Health alerts: concentration, sector, drawdown, rebalancing alerts with env-configurable thresholds
- TARGET_ETF_PCT/TARGET_STOCK_PCT now read from environment (not hardcoded 70/30)
- S&P 500 (^GSPC) as default benchmark — indexed to 100 at first snapshot date
- Attribution = (position_return - benchmark_return) × weight × direction for relative; position_return × weight for absolute

## Phase Map

| # | Phase | Requirements | Status |
|---|-------|--------------|--------|
| 1 | Security Hardening | SEC-01 through SEC-06 | Complete |
| 2 | Performance | PERF-01 through PERF-03 | Complete |
| 3 | Health Indicators | HEALTH-01 through HEALTH-04 | Complete |
| 4 | Benchmark Tracking | TRACK-01 through TRACK-03 | Complete |
| 5 | Dashboard Polish | DASH-01 through DASH-03 | Pending |
| 6 | Testing | TEST-01 through TEST-03 | Pending |

## Completed Phases

- Phase 1: Security Hardening — API auth, credential redaction, debug cleanup, security headers
- Phase 2: Performance — async yfinance, thread-safe session/FX cache
- Phase 3: Health Indicators — compute_health_alerts(), health_alerts UI, Hermes context integration
- Phase 4: Benchmark Tracking — snapshots.py, /api/benchmark, benchmark chart + attribution table in UI, Hermes context extension

## Blockers/Concerns

- No automated tests for scoring, market data, and portfolio parsing

## Session Continuity

Last session: --stopped-at
Stopped at: Phase 04 benchmark tracking complete

---
*Last updated: 2026-04-23 after phase 04 completion*
