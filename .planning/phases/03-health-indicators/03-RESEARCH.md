# Phase 3: Health Indicators - Research

**Researched:** 2026-04-23
**Domain:** Portfolio health monitoring — alert computation, threshold configuration, UI rendering
**Confidence:** HIGH

## Summary

Phase 3 adds four health monitoring alerts to the Brokr portfolio API and dashboard. The implementation is straightforward: a new `health_checks.py` module computes alerts after positions are enriched and scored, returning a list of structured alert objects via `health_alerts` in the portfolio response and Hermes context. All thresholds are environment variables. The UI renders a "Health Alerts" section between summary cards and charts.

**Primary recommendation:** Implement a `compute_health_alerts()` function in a new `app/health_checks.py` module. Call it from `get_portfolio()` in `main.py` before returning. Add `health_alerts` to `build_hermes_context()` in `context_builder.py`. Render in `app/static/app.js` using existing patterns from Winners/Losers section.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Alert computation (concentration, sector, drawdown, rebalancing) | API / Backend | — | Pure Python logic on position data, no UI involvement |
| Health alerts in portfolio API response | API / Backend | — | `main.py` `get_portfolio()` endpoint appends `health_alerts` |
| Health alerts in Hermes context | API / Backend | — | `context_builder.py` adds `health_alerts` to JSON output |
| Health alerts dashboard rendering | Browser / Client | — | `app/static/app.js` `renderHealthAlerts()` in `renderDashboard()` |
| Threshold configuration | API / Backend | — | Environment variables read at startup/import time |

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Health alerts are **structured objects** with: `type`, `severity` (warn/critical), `message`, `current_value`, `threshold`, and `triggering_positions` (where applicable)
- **D-02:** Alerts are returned as a list in the portfolio response (`health_alerts: []`)
- **D-03:** Alerts are included in Hermes JSON context under a `health_alerts` key
- **D-04:** Alerts are rendered in the dashboard as a dedicated "Health Alerts" section
- **D-05:** All thresholds are **environment variables** — no hardcoded magic numbers in logic
- **D-06:** `HEALTH_POSITION_THRESHOLD` — concentration risk trigger (default: 20, meaning 20%)
- **D-07:** `HEALTH_SECTOR_THRESHOLD` — sector weighting trigger (default: 40, meaning 40%)
- **D-08:** `HEALTH_DRAWDOWN_THRESHOLD` — drawdown trigger (default: -10, meaning -10%)
- **D-09:** `HEALTH_REBALANCE_THRESHOLD` — rebalancing drift trigger (default: 5, meaning 5 percentage points)
- **D-10:** ETF/stock target weights are **environment variables**
- **D-11:** `TARGET_ETF_PCT` — target ETF allocation percentage (default: 70)
- **D-12:** `TARGET_STOCK_PCT` — target stock allocation percentage (default: 30)
- **D-13:** Replace hardcoded `target_etf_pct: 70` / `target_stock_pct: 30` in `context_builder.py` with values from environment
- **D-14:** Drawdown is measured using **portfolio YTD return as a proxy** — computed as the weighted average of individual position `perf_ytd` values, weighted by position EUR value
- **D-15:** No historical portfolio snapshots needed for HEALTH-03 — avoids adding snapshot storage infrastructure in this phase
- **D-16:** The YTD proxy approach uses the existing `perf_ytd` per position (already enriched by yfinance) and `weight` per position
- **D-17:** Rebalancing signal triggers when either ETF or stock actual allocation drifts more than `HEALTH_REBALANCE_THRESHOLD` pp from its target
- **D-18:** The rebalancing signal is part of the health alerts list (not a separate section)

### Claude's Discretion
No open discretion areas — all decisions are locked in CONTEXT.md.

### Deferred Ideas (OUT OF SCOPE)
- **Historical Drawdown Tracking:** If Phase 4 adds portfolio snapshots, HEALTH-03 could use actual historical peak tracking. Do not implement this now.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| HEALTH-01 | Concentration risk alert — warn when single position exceeds 20% of portfolio | `weight` already computed by `compute_portfolio_weights()`; check if `weight > HEALTH_POSITION_THRESHOLD` |
| HEALTH-02 | Sector weighting alert — warn when sector exceeds threshold (e.g., 40%) | `sector_breakdown` already computed in `_build_portfolio_summary()`; compare against `HEALTH_SECTOR_THRESHOLD` |
| HEALTH-03 | Drawdown alert — warn when portfolio drawdown exceeds threshold (e.g., -10%) | Weighted average of `perf_ytd` by `weight`, already available per position |
| HEALTH-04 | Rebalancing signal — suggest when allocations drift too far from target weights | `etf_allocation_pct`/`stock_allocation_pct` already in portfolio; compare against `TARGET_ETF_PCT`/`TARGET_STOCK_PCT` with `HEALTH_REBALANCE_THRESHOLD` |

## Standard Stack

This phase uses only existing project libraries — no new dependencies.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python 3 | any | Runtime | Already in use |
| FastAPI | existing | Web framework | Already in use |
| yfinance | existing | `perf_ytd`, `sector`, `weight` data | Already enriching positions |

**No new packages needed.** All required data (`weight`, `sector`, `perf_ytd`, `etf_allocation_pct`, `stock_allocation_pct`) is already computed and attached to positions by existing code (`scoring.py`, `market_data.py`, `main.py`).

## Architecture Patterns

### System Architecture Diagram

```
[DeGiro API]
     │
     ▼
[DeGiroClient.fetch_portfolio()]  ── raw positions + cash
     │
     ▼
[enrich_positions()]  ── adds sector, perf_ytd, current_price, etc.
     │
     ▼
[compute_portfolio_weights()]  ── adds weight per position
     │
     ▼
[compute_scores()]  ── adds momentum, value, buy_priority scores
     │
     ▼
[compute_health_alerts()]  ◄── NEW: Phase 3 core logic
     │   ├─ HEALTH-01: check position weights vs HEALTH_POSITION_THRESHOLD
     │   ├─ HEALTH-02: check sector_breakdown vs HEALTH_SECTOR_THRESHOLD
     │   ├─ HEALTH-03: weighted avg perf_ytd vs HEALTH_DRAWDOWN_THRESHOLD
     │   └─ HEALTH-04: allocation drift vs TARGET_*_PCT ± HEALTH_REBALANCE_THRESHOLD
     │
     ▼
[_build_portfolio_summary()]  ── adds health_alerts list to response
     │
     ├──► [API Response /api/portfolio]  ── includes health_alerts
     │         │
     │         ▼
     │    [app.js renderDashboard()]  ── calls renderHealthAlerts()
     │         │
     │         ▼
     │    [Health Alerts Section in index.html]
     │
     └──► [build_hermes_context()]  ── adds health_alerts to JSON context
              │
              ▼
         [API Response /api/hermes-context]
```

### Recommended Project Structure
```
app/
├── health_checks.py   # NEW: compute_health_alerts() function
├── main.py            # MODIFIED: call compute_health_alerts(), use env vars for TARGET_*
├── context_builder.py # MODIFIED: replace hardcoded targets, add health_alerts
├── scoring.py        # unchanged
├── market_data.py    # unchanged
├── degiro_client.py  # unchanged
└── static/
    ├── app.js        # MODIFIED: add renderHealthAlerts() in renderDashboard()
    ├── index.html    # MODIFIED: add health alerts HTML section
    └── style.css     # MODIFIED: add alert-card CSS classes
```

### Pattern 1: Structured Alert Object
**What:** Each health alert is a dict with consistent fields.
**When to use:** HEALTH-01 through HEALTH-04 all return the same shape.
**Example:**
```python
# Source: D-01 through D-04 (CONTEXT.md)
{
    "type": "concentration" | "sector" | "drawdown" | "rebalancing",
    "severity": "warn" | "critical",
    "message": "Human-readable description",
    "current_value": float,      # e.g. 23.5 (percentage)
    "threshold": float,         # e.g. 20.0 (percentage)
    "triggering_positions": [   # Only for concentration/sector
        {"name": "AAPL", "symbol": "AAPL", "value": 23.5},
    ] | None,                   # For drawdown/rebalancing
}
```

### Pattern 2: Environment Variable with Default
**What:** Threshold config via `os.getenv` with integer/float defaults.
**When to use:** All threshold and target weight configuration.
**Example:**
```python
# Source: established pattern from main.py verify_brok_token
HEALTH_POSITION_THRESHOLD = int(os.getenv("HEALTH_POSITION_THRESHOLD", "20"))
HEALTH_SECTOR_THRESHOLD   = int(os.getenv("HEALTH_SECTOR_THRESHOLD", "40"))
HEALTH_DRAWDOWN_THRESHOLD = int(os.getenv("HEALTH_DRAWDOWN_THRESHOLD", "-10"))
HEALTH_REBALANCE_THRESHOLD = int(os.getenv("HEALTH_REBALANCE_THRESHOLD", "5"))
TARGET_ETF_PCT = int(os.getenv("TARGET_ETF_PCT", "70"))
TARGET_STOCK_PCT = int(os.getenv("TARGET_STOCK_PCT", "30"))
```

### Pattern 3: Threshold Severity Determination
**What:** Some thresholds use the same value for warn vs critical (simpler approach).
**When to use:** HEALTH-01, HEALTH-02, HEALTH-04 use a single threshold for triggering.
**Note:** Per D-01, severity is part of the alert structure. HEALTH-03 (drawdown) uses the same threshold for warn = critical — no tiered severity in this phase.
```python
# Single threshold — alert triggers when exceeded
if position["weight"] > HEALTH_POSITION_THRESHOLD:
    severity = "warn"  # Could be "critical" if > 25% etc., but not required here
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|------------|-------------|-----|
| Sector classification | Manual mapping of symbols to sectors | `position["sector"]` from yfinance (already enriched) | yfinance provides `info["sector"]` reliably; manual mapping would drift and require maintenance |
| Drawdown from peak | Historical portfolio snapshots to track peak | Weighted `perf_ytd` proxy (D-14) | Snapshots require storage infrastructure; YTD proxy is sufficient per D-15 and avoids scope expansion |
| Weight computation | Custom weight calculation | `compute_portfolio_weights()` in `scoring.py` (already used) | Already computes `(val / total_value) * 100` correctly |

**Key insight:** Phase 3 is nearly all composition — the hard work (enrichment, scoring, weighting, sector breakdown) is already done. The new code just evaluates thresholds against existing data structures.

## Common Pitfalls

### Pitfall 1: Division by Zero in Sector Breakdown
**What goes wrong:** If no positions have a sector (all `None`), `sector_breakdown` computation in `_build_portfolio_summary()` uses `total_for_sector = sum(sector_map.values()) or 1` which silently substitutes 1. An alert could then show "5000%" sector weight.
**Why it happens:** Guard `or 1` masks the zero case instead of handling it properly.
**How to avoid:** In `compute_health_alerts()`, skip HEALTH-02 if total sector value is 0 or if all sectors are "Unknown".
**Warning signs:** HEALTH-02 fires when portfolio just loaded but yfinance enrichment still pending.

### Pitfall 2: Using `None` Weight in Comparisons
**What goes wrong:** `position["weight"] > HEALTH_POSITION_THRESHOLD` throws `TypeError` if `weight` is `None` (position not yet weighted).
**Why it happens:** `compute_portfolio_weights()` is called before `compute_health_alerts()`, but callers of the alert function might change order.
**How to avoid:** Always use `or 0` when accessing weight: `(position.get("weight") or 0) > threshold`
**Warning signs:** `TypeError: '>' not supported between instances of 'NoneType' and 'int'`

### Pitfall 3: YTD Proxy Misses New Positions
**What goes wrong:** A position purchased in January 2026 that gained 5% has `perf_ytd = 5`. A position purchased today (April) showing -50% drag also has `perf_ytd`. The weighted average may not reflect true portfolio drawdown from peak.
**Why it happens:** YTD performance is price-based, not cashflow-adjusted (no XIRR). New cash infusions bias the weighted average.
**How to avoid:** Document that this is a proxy. Acceptable per D-15. Phase 4 historical snapshots could improve it later.
**Warning signs:** HEALTH-03 fires spuriously during high-volatility periods even without true drawdown from peak.

### Pitfall 4: Hardcoded Target Weights Still in context_builder.py
**What goes wrong:** D-13 says to replace hardcoded `target_etf_pct: 70` / `target_stock_pct: 30` in `context_builder.py`. But `context_builder.py` lines 34-35 still show these hardcoded values.
**Why it happens:** Phase 3 implementation has not happened yet.
**How to avoid:** Planner must include a task to update `context_builder.py` to read `TARGET_ETF_PCT` / `TARGET_STOCK_PCT` from environment.

## Code Examples

### compute_health_alerts() Skeleton
```python
# app/health_checks.py
import os

# Threshold defaults (match D-06 through D-09, D-11, D-12)
HEALTH_POSITION_THRESHOLD  = int(os.getenv("HEALTH_POSITION_THRESHOLD", "20"))
HEALTH_SECTOR_THRESHOLD   = int(os.getenv("HEALTH_SECTOR_THRESHOLD", "40"))
HEALTH_DRAWDOWN_THRESHOLD = int(os.getenv("HEALTH_DRAWDOWN_THRESHOLD", "-10"))
HEALTH_REBALANCE_THRESHOLD = int(os.getenv("HEALTH_REBALANCE_THRESHOLD", "5"))
TARGET_ETF_PCT   = int(os.getenv("TARGET_ETF_PCT", "70"))
TARGET_STOCK_PCT = int(os.getenv("TARGET_STOCK_PCT", "30"))


def compute_health_alerts(portfolio: dict) -> list[dict]:
    """Compute all health alerts from a portfolio dict.

    Called after enrich_positions, compute_portfolio_weights, compute_scores.
    """
    alerts = []
    positions = portfolio.get("positions", [])
    sector_breakdown = portfolio.get("sector_breakdown", {})
    etf_pct = portfolio.get("etf_allocation_pct", 0)
    stock_pct = portfolio.get("stock_allocation_pct", 0)

    # HEALTH-01: Concentration risk
    alerts.extend(_check_concentration(positions))

    # HEALTH-02: Sector weighting
    alerts.extend(_check_sector_weighting(sector_breakdown))

    # HEALTH-03: Drawdown
    alerts.append(_check_drawdown(positions))

    # HEALTH-04: Rebalancing
    alerts.append(_check_rebalancing(etf_pct, stock_pct))

    return [a for a in alerts if a is not None]


def _check_concentration(positions: list) -> list[dict]:
    alerts = []
    for pos in positions:
        weight = pos.get("weight") or 0
        if weight > HEALTH_POSITION_THRESHOLD:
            alerts.append({
                "type": "concentration",
                "severity": "warn",
                "message": f"{pos['name']} is {weight:.1f}% of portfolio (threshold {HEALTH_POSITION_THRESHOLD}%)",
                "current_value": weight,
                "threshold": float(HEALTH_POSITION_THRESHOLD),
                "triggering_positions": [{
                    "name": pos["name"],
                    "symbol": pos.get("symbol", ""),
                    "value": weight,
                }],
            })
    return alerts


def _check_sector_weighting(sector_breakdown: dict) -> list[dict]:
    alerts = []
    for sector, pct in sector_breakdown.items():
        if pct > HEALTH_SECTOR_THRESHOLD:
            alerts.append({
                "type": "sector",
                "severity": "warn",
                "message": f"Sector '{sector}' is {pct:.1f}% of portfolio (threshold {HEALTH_SECTOR_THRESHOLD}%)",
                "current_value": pct,
                "threshold": float(HEALTH_SECTOR_THRESHOLD),
                "triggering_positions": None,
            })
    return alerts


def _check_drawdown(positions: list) -> dict | None:
    # D-14: weighted average of perf_ytd by position EUR value
    total_value = sum(p.get("current_value_eur", 0) or 0 for p in positions)
    if total_value == 0:
        return None

    weighted_ytd = sum(
        (p.get("perf_ytd") or 0) * (p.get("current_value_eur", 0) or 0)
        for p in positions
        if p.get("perf_ytd") is not None
    )
    portfolio_ytd = weighted_ytd / total_value

    if portfolio_ytd < HEALTH_DRAWDOWN_THRESHOLD:
        return {
            "type": "drawdown",
            "severity": "warn",
            "message": f"Portfolio YTD return is {portfolio_ytd:+.1f}% (threshold {HEALTH_DRAWDOWN_THRESHOLD}%)",
            "current_value": portfolio_ytd,
            "threshold": float(HEALTH_DRAWDOWN_THRESHOLD),
            "triggering_positions": None,
        }
    return None


def _check_rebalancing(etf_pct: float, stock_pct: float) -> dict | None:
    # D-17: trigger when either ETF or stock drifts beyond threshold
    etf_drift = abs(etf_pct - TARGET_ETF_PCT)
    stock_drift = abs(stock_pct - TARGET_STOCK_PCT)

    if etf_drift > HEALTH_REBALANCE_THRESHOLD or stock_drift > HEALTH_REBALANCE_THRESHOLD:
        return {
            "type": "rebalancing",
            "severity": "warn",
            "message": (
                f"ETF allocation at {etf_pct:.1f}% (target {TARGET_ETF_PCT}%, ±{HEALTH_REBALANCE_THRESHOLD}pp), "
                f"Stock at {stock_pct:.1f}% (target {TARGET_STOCK_PCT}%, ±{HEALTH_REBALANCE_THRESHOLD}pp)"
            ),
            "current_value": etf_pct,  # Primary metric is ETF allocation
            "threshold": float(HEALTH_REBALANCE_THRESHOLD),
            "triggering_positions": None,
        }
    return None
```

### Integrating into get_portfolio() in main.py
```python
# After positions = compute_scores(positions), before _build_portfolio_summary()
# Compute health alerts
health_alerts = compute_health_alerts({
    "positions": positions,
    "sector_breakdown": {},  # Will be computed below
    "etf_allocation_pct": etf_allocation_pct,
    "stock_allocation_pct": stock_allocation_pct,
})

# But sector_breakdown is computed inside _build_portfolio_summary()...
# Alternative: pass positions and compute inside compute_health_alerts
# Solution: compute sector_breakdown inline first, then pass to both
```

### Hermes Context Integration (context_builder.py changes)
```python
# Lines 34-35 in context_builder.py currently hardcoded:
# "target_etf_pct": 70,
# "target_stock_pct": 30,

# Replace with:
import os
TARGET_ETF_PCT   = int(os.getenv("TARGET_ETF_PCT", "70"))
TARGET_STOCK_PCT = int(os.getenv("TARGET_STOCK_PCT", "30"))

# In build_hermes_context json_context["portfolio_summary"]:
"target_etf_pct": TARGET_ETF_PCT,
"target_stock_pct": TARGET_STOCK_PCT,

# Add health_alerts (D-03)
# json_context["health_alerts"] = portfolio.get("health_alerts", [])
# (passed in from main.py via the portfolio dict)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No health monitoring | Dedicated health_alerts list in portfolio response | Phase 3 | First time portfolio signals are surfaced proactively |
| Hardcoded 70/30 target | Env vars TARGET_ETF_PCT / TARGET_STOCK_PCT | Phase 3 | Configuration without code changes |

**Deprecated/outdated:**
- None in this phase.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `position["sector"]` from yfinance is populated for all positions at this point | HEALTH-02 computation | If sector is None for many positions, sector_breakdown will show "Unknown" dominating, causing false HEALTH-02 alerts or masking real concentration |
| A2 | `compute_portfolio_weights()` is always called before `compute_health_alerts()` | HEALTH-01 computation | If called in wrong order, weight is None and comparison fails |
| A3 | `HEALTH_DRAWDOWN_THRESHOLD` defaults to -10 (negative int as string) | HEALTH-03 env var | `int(os.getenv("HEALTH_DRAWDOWN_THRESHOLD", "-10"))` — verify negative default works |

**All assumptions are LOW risk** — they are based on verified code flow from reading `main.py` and established patterns.

## Open Questions

1. **Should HEALTH-01 concentration alerts be tiered (warn at 20%, critical at 30%)?**
   - What we know: D-01 defines severity field but doesn't specify tiers
   - What's unclear: Whether a single threshold means all alerts are "warn" or if critical is ever used
   - Recommendation: Default to "warn" for all HEALTH-01 through HEALTH-04. Critical reserved for extreme cases (not needed in v1).

2. **Should HEALTH-02 show multiple sectors or just the worst offender?**
   - What we know: Sector breakdown is a dict with all sectors
   - What's unclear: Whether to fire one alert per violating sector or aggregate into one
   - Recommendation: Fire one alert per violating sector — more actionable for the user

3. **Should `triggering_positions` for HEALTH-02 (sector) list all positions in that sector?**
   - What we know: D-01 says `triggering_positions` is "where applicable"
   - What's unclear: Whether listing individual positions is worth the UI complexity
   - Recommendation: Keep `triggering_positions: null` for sector alerts — the sector name is self-explanatory

## Environment Availability

> Step 2.6: SKIPPED — no external dependencies beyond the project's own code. All computation uses existing data structures already populated by Phase 2's enrichment pipeline.

## Validation Architecture

> Step 4: SKIPPED — `nyquist_validation` is explicitly `false` in `.planning/config.json` (`workflow.nyquist_validation: false`). No test infrastructure research needed.

## Security Domain

> Required when `security_enforcement` is enabled (absent = enabled). Omit only if explicitly `false`.

**This phase does not introduce new security concerns.** Health alerts are computed from existing position data. All thresholds come from environment variables (not user input). No new authentication or authorization changes.

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Threshold env vars accept negative values | Availability | `HEALTH_DRAWDOWN_THRESHOLD=-5` is valid (less strict); `HEALTH_POSITION_THRESHOLD=150` is nonsensical — document valid ranges in `.env.example` |
| No other new attack surface | — | — |

## Sources

### Primary (HIGH confidence)
- `app/main.py` lines 85-209 — `_build_portfolio_summary()` shows exactly how `sector_breakdown`, `etf_allocation_pct`, `stock_allocation_pct` are computed
- `app/scoring.py` lines 121-134 — `compute_portfolio_weights()` shows how `weight` is added to each position
- `app/context_builder.py` lines 34-37 — hardcoded targets that D-13 says to replace
- `app/static/app.js` lines 527-556 — `renderWinnersLosers()` as pattern to replicate for `renderHealthAlerts()`
- `03-CONTEXT.md` D-01 through D-18 — all locked implementation decisions
- `03-UI-SPEC.md` — UI contract specifying alert-card CSS, severity colors, empty state copy

### Secondary (MEDIUM confidence)
- `03-UI-SPEC.md` — CSS class conventions from `style.css` (not directly read, but referenced)

### Tertiary (LOW confidence)
- None — all findings verified by reading source code.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, all data already available
- Architecture: HIGH — composition of existing pipeline steps
- Pitfalls: MEDIUM — identified from code review of existing patterns

**Research date:** 2026-04-23
**Valid until:** 2026-05-23 (30 days — phase implementation uses stable existing APIs)
