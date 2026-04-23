# Phase 03: Health Indicators - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Add portfolio health monitoring signals for concentration risk, sector weighting, drawdown, and rebalancing. Delivers HEALTH-01 through HEALTH-04:
- Concentration risk alert — single position exceeds threshold of portfolio value
- Sector weighting alert — any sector exceeds threshold of portfolio value
- Drawdown alert — portfolio YTD return exceeds negative threshold
- Rebalancing signal — actual ETF/stock allocations drift beyond threshold from target weights

Health indicators appear in dashboard UI and are included in Hermes context API.

</domain>

<decisions>
## Implementation Decisions

### Alert Format

- **D-01:** Health alerts are **structured objects** with: `type`, `severity` (warn/critical), `message`, `current_value`, `threshold`, and `triggering_positions` (where applicable)
- **D-02:** Alerts are returned as a list in the portfolio response (`health_alerts: []`)
- **D-03:** Alerts are included in Hermes JSON context under a `health_alerts` key
- **D-04:** Alerts are rendered in the dashboard as a dedicated "Health Alerts" section

### Threshold Configuration

- **D-05:** All thresholds are **environment variables** — no hardcoded magic numbers in logic
- **D-06:** `HEALTH_POSITION_THRESHOLD` — concentration risk trigger (default: 20, meaning 20%)
- **D-07:** `HEALTH_SECTOR_THRESHOLD` — sector weighting trigger (default: 40, meaning 40%)
- **D-08:** `HEALTH_DRAWDOWN_THRESHOLD` — drawdown trigger (default: -10, meaning -10%)
- **D-09:** `HEALTH_REBALANCE_THRESHOLD` — rebalancing drift trigger (default: 5, meaning 5 percentage points)

### Target Weights

- **D-10:** ETF/stock target weights are **environment variables**
- **D-11:** `TARGET_ETF_PCT` — target ETF allocation percentage (default: 70)
- **D-12:** `TARGET_STOCK_PCT` — target stock allocation percentage (default: 30)
- **D-13:** Replace hardcoded `target_etf_pct: 70` / `target_stock_pct: 30` in `context_builder.py` with values from environment

### Drawdown Detection

- **D-14:** Drawdown is measured using **portfolio YTD return as a proxy** — computed as the weighted average of individual position `perf_ytd` values, weighted by position EUR value
- **D-15:** No historical portfolio snapshots needed for HEALTH-03 — avoids adding snapshot storage infrastructure in this phase
- **D-16:** The YTD proxy approach uses the existing `perf_ytd` per position (already enriched by yfinance) and `weight` per position

### Rebalancing Signal (HEALTH-04)

- **D-17:** Rebalancing signal triggers when either ETF or stock actual allocation drifts more than `HEALTH_REBALANCE_THRESHOLD` pp from its target
- **D-18:** The rebalancing signal is part of the health alerts list (not a separate section)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Context
- `.planning/phases/01-security-hardening/01-CONTEXT.md` — Auth token pattern, env var conventions
- `.planning/phases/02-performance/02-CONTEXT.md` — Threading patterns, FX cache locking
- `.planning/ROADMAP.md` §Phase 3 — Phase goal, success criteria, implementation notes
- `.planning/REQUIREMENTS.md` §Health Indicators (HEALTH) — HEALTH-01, HEALTH-02, HEALTH-03, HEALTH-04

### Codebase
- `app/scoring.py` — `compute_portfolio_weights()`, `get_top_candidates()`, existing scoring logic
- `app/market_data.py` — `enrich_position()` which populates `sector`, `perf_ytd`, `weight` fields
- `app/context_builder.py` — Hardcoded target weights to replace with env vars (lines 34-35)
- `app/main.py` — `_build_portfolio_summary()` which computes `sector_breakdown`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `sector_breakdown` computation — already in `_build_portfolio_summary()` / `_build_raw_portfolio_summary()`; reuse for HEALTH-02
- `compute_portfolio_weights()` in `scoring.py` — already computes `weight` per position
- `perf_ytd` field — already populated per position by yfinance enrichment
- `build_hermes_context()` in `context_builder.py` — already includes rebalancing delta; extend with health alerts

### Established Patterns
- Environment variable config via `os.getenv` with defaults
- Structured alert dicts returned in portfolio response
- Thread-safe session cache patterns from Phase 2

### Integration Points
- `app/main.py` `get_portfolio()` endpoint — where health alerts should be computed and appended to response
- `app/context_builder.py` — add `health_alerts` to JSON context output
- `app/static/app.js` `renderDashboard()` — add "Health Alerts" UI section
- `app/static/index.html` — add health alerts HTML structure

</code_context>

<specifics>
## Specific Ideas

- No specific "like X" references — decisions followed from analysis of existing code and requirements

</specifics>

<deferred>
## Deferred Ideas

### Historical Drawdown Tracking
If Phase 4 (Benchmark Tracking) adds portfolio snapshots, HEALTH-03 could be upgraded to use actual historical peak tracking instead of YTD proxy. Planner should leave the door open for this without implementing it now.

</deferred>

---

*Phase: 03-health-indicators*
*Context gathered: 2026-04-23*
