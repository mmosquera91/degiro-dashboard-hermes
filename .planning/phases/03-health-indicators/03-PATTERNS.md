# Phase 03: Health Indicators - Pattern Map

**Mapped:** 2026-04-23
**Files analyzed:** 6 new/modified files
**Analogs found:** 5 / 6

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/health_checks.py` | service | transform | `app/scoring.py` | role-match |
| `app/main.py` | controller | request-response | `app/main.py` (self) | self |
| `app/context_builder.py` | service | transform | `app/context_builder.py` (self) | self |
| `app/static/app.js` | component | render | `app/static/app.js` (self) | self |
| `app/static/index.html` | component | static | `app/static/index.html` (self) | self |
| `app/static/style.css` | component | static | `app/static/style.css` (self) | self |

## Pattern Assignments

### `app/health_checks.py` (service, transform)

**Analog:** `app/scoring.py` lines 1-134

This is a **new file** — no exact match exists. The closest analog is `scoring.py` which follows the same data-flow pattern: pure Python transformation functions operating on position data structures.

**Imports pattern** (from `app/scoring.py` lines 1-8):
```python
import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)
```

**Core transformation pattern** (from `scoring.py` lines 121-134 — `compute_portfolio_weights`):
```python
def compute_portfolio_weights(positions: list[dict]) -> list[dict]:
    """Compute portfolio weight for each position based on EUR value."""
    total_value = sum(p.get("current_value_eur", 0) or 0 for p in positions)

    if total_value == 0:
        for pos in positions:
            pos["weight"] = 0.0
        return positions

    for pos in positions:
        val = pos.get("current_value_eur", 0) or 0
        pos["weight"] = round((val / total_value) * 100, 2)

    return positions
```

**Environment variable pattern** (from `app/main.py` lines 42-43, 236-237):
```python
# From verify_brok_token:
token = os.getenv("BROKR_AUTH_TOKEN", "")

# From CORS config:
cors_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")
allow_origins = cors_origins.split(",") if cors_origins else ["http://localhost:8000"]
```

**Key conventions to follow:**
- Module-level threshold constants via `int(os.getenv("KEY", "default"))`
- Guard `or 0` when accessing potentially-None dict values (per RESEARCH.md Pitfall 2)
- Guard division by zero before computing ratios
- Return `list[dict]` of structured alert objects matching D-01 schema

---

### `app/main.py` (controller, request-response)

**Analog:** `app/main.py` (self — no change to endpoint pattern)

**Pipeline integration pattern** (lines 343-356):
```python
# Fetch raw portfolio from DeGiro
raw = DeGiroClient.fetch_portfolio(trading_api)

# Enrich with yfinance data
positions = await asyncio.to_thread(enrich_positions, raw)

# Compute portfolio weights
positions = compute_portfolio_weights(positions)

# Compute scores
positions = compute_scores(positions)

# BUILD SUMMARY — health_alerts should be added before this call
portfolio = _build_portfolio_summary(positions, raw.get("cash_available", 0))
```

**Pattern to add:** After `compute_scores()`, call `compute_health_alerts()` and pass `health_alerts` into `_build_portfolio_summary()` response dict under key `health_alerts`.

**Return dict pattern** (from `_build_portfolio_summary` lines 193-209):
```python
return {
    "date": datetime.now().isoformat(),
    "total_value": round(total_value, 2),
    "total_invested": round(total_invested, 2),
    ...
    "positions": positions,
    "top_candidates": top_candidates,
    # NEW: "health_alerts": health_alerts,  <-- add here
}
```

---

### `app/context_builder.py` (service, transform)

**Analog:** `app/context_builder.py` (self — modifications only)

**Hardcoded targets to replace** (lines 34-37):
```python
"target_etf_pct": 70,
"target_stock_pct": 30,
"allocation_delta_etf": portfolio.get("etf_allocation_pct", 0) - 70,
"allocation_delta_stock": portfolio.get("stock_allocation_pct", 0) - 30,
```

**Replace with env var pattern** (from `app/main.py` verify_brok_token):
```python
import os
TARGET_ETF_PCT = int(os.getenv("TARGET_ETF_PCT", "70"))
TARGET_STOCK_PCT = int(os.getenv("TARGET_STOCK_PCT", "30"))
```

**Pattern to add for health_alerts** (D-03): After building `json_context`, add:
```python
# health_alerts from portfolio (passed from main.py)
json_context["health_alerts"] = portfolio.get("health_alerts", [])
```

---

### `app/static/app.js` (component, render)

**Analog:** `app/static/app.js` (self — `renderWinnersLosers` pattern)

**Render function pattern** (lines 527-556 — `renderWinnersLosers`):
```javascript
function renderWinnersLosers() {
    const winners = portfolioData.top_5_winners || [];
    const losers = portfolioData.top_5_losers || [];

    const winnersEl = $("#top-winners");
    const losersEl = $("#top-losers");

    winnersEl.innerHTML = winners
      .map(
        (w) => `
      <div class="wl-item">
        <span>${esc(w.name)}</span>
        <span class="wl-item-pl pl-positive">${w.pl_pct != null ? w.pl_pct.toFixed(2) + "%" : "—"}</span>
      </div>
    `
      )
      .join("");
    // ... losers similar
}
```

**renderDashboard call order** (lines 266-294):
```javascript
function renderDashboard() {
    ...
    renderSummary();
    renderCharts();
    renderPositions();
    renderBuyRadar();
    renderWinnersLosers();
    lucide.createIcons();
}
```

**Pattern for `renderHealthAlerts`:** Add `renderHealthAlerts()` call after `renderWinnersLosers()` in `renderDashboard()`. Function should:
- Read `portfolioData.health_alerts || []`
- Render each alert as an `alert-card` div with severity-based CSS class
- Use `esc()` helper for XSS-safe text
- Handle empty list with a "Portfolio is healthy" message

---

### `app/static/index.html` (component, static)

**Analog:** `app/static/index.html` (self — Winners/Losers section)

**Winners/Losers HTML pattern** (lines 165-175):
```html
<!-- WINNERS / LOSERS -->
<section class="winners-losers-section">
  <div class="card wl-card">
    <h4 class="wl-title wl-win">Top 5 Winners</h4>
    <div id="top-winners" class="wl-list"></div>
  </div>
  <div class="card wl-card">
    <h4 class="wl-title wl-lose">Top 5 Losers</h4>
    <div id="top-losers" class="wl-list"></div>
  </div>
</section>
```

**Health Alerts section location:** Between Buy Radar (lines 150-163) and Winners/Losers (lines 165-175).

**Pattern to add:**
```html
<!-- HEALTH ALERTS -->
<section class="health-alerts-section">
  <h3 class="section-title">Health Alerts</h3>
  <div id="health-alerts" class="alerts-list"></div>
</section>
```

---

### `app/static/style.css` (component, static)

**Analog:** `app/static/style.css` (self — Winners/Losers pattern)

**Winners/Losers CSS pattern** (lines 393-420):
```css
.winners-losers-section {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.wl-title {
  font-size: 0.82rem;
  font-weight: 600;
  margin-bottom: 10px;
}
.wl-win { color: var(--green); }
.wl-lose { color: var(--red); }

.wl-list { display: flex; flex-direction: column; gap: 4px; }

.wl-item {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px solid var(--border);
  font-size: 0.82rem;
}
```

**Alert-card CSS pattern to add:**
```css
.health-alerts-section {
  margin-bottom: 20px;
}

.alerts-list { display: flex; flex-direction: column; gap: 8px; }

.alert-card {
  padding: 12px 16px;
  border-radius: var(--radius);
  border: 1px solid;
}

.alert-card.warn {
  background: rgba(217, 119, 6, 0.08);
  border-color: rgba(217, 119, 6, 0.3);
}

.alert-card.critical {
  background: rgba(239, 68, 68, 0.08);
  border-color: rgba(239, 68, 68, 0.3);
}

.alert-type { font-size: 0.75rem; text-transform: uppercase; font-weight: 600; }
.alert-message { font-size: 0.85rem; margin-top: 4px; }
.alert-meta { font-size: 0.72rem; color: var(--text-dim); margin-top: 4px; }
```

---

## Shared Patterns

### Environment Variable Configuration
**Source:** `app/main.py` lines 42, 236-237
**Apply to:** `app/health_checks.py` (threshold config), `app/context_builder.py` (target weights)
```python
import os
THRESHOLD_NAME = int(os.getenv("THRESHOLD_NAME", "default"))
```

### Null-Safe Field Access
**Source:** `app/scoring.py` lines 39-50, 89-92, 123
**Apply to:** All position dict field reads in `app/health_checks.py`
```python
weight = pos.get("weight") or 0  # Never None for comparison
perf_ytd = p.get("perf_ytd") or 0
```

### Division-by-Zero Guard
**Source:** `app/scoring.py` lines 125-128
**Apply to:** `app/health_checks.py` HEALTH-02 (sector total), HEALTH-03 (total_value)
```python
if total_value == 0:
    return positions  # or return early with None
```

### Structured Alert Dict Schema
**Source:** D-01 (CONTEXT.md)
**Apply to:** All `_check_*` functions in `app/health_checks.py`
```python
{
    "type": "concentration" | "sector" | "drawdown" | "rebalancing",
    "severity": "warn" | "critical",
    "message": "Human-readable description",
    "current_value": float,
    "threshold": float,
    "triggering_positions": [...] | None,
}
```

### Frontend XSS-Safe Text
**Source:** `app/static/app.js` lines 628-633
**Apply to:** All user data rendered in `renderHealthAlerts()`
```javascript
function esc(str) {
  if (str == null) return "";
  const d = document.createElement("div");
  d.textContent = String(str);
  return d.innerHTML;
}
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `app/health_checks.py` | service | transform | New module — `scoring.py` is closest analog but this is a new concern, not existing code |

## Metadata

**Analog search scope:** `app/**/*.py`, `app/static/**/*`
**Files scanned:** 6 primary + 3 supporting
**Pattern extraction date:** 2026-04-23
