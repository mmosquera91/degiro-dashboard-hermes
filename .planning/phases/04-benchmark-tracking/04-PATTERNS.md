# Phase 04: Benchmark Tracking - Pattern Map

**Mapped:** 2026-04-23
**Files analyzed:** 8 new/modified files
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/snapshots.py` | service | file-I/O + request-response | `app/market_data.py` | role-match |
| `app/scoring.py` | service | transform | `app/scoring.py` (same file) | self |
| `app/context_builder.py` | service | transform | `app/context_builder.py` (same file) | self |
| `app/main.py` | route | request-response | `app/main.py` (same file) | self |
| `app/static/app.js` | component | client-rendering | `app/static/app.js` (same file) | self |
| `app/static/index.html` | component | static-markup | `app/static/index.html` (same file) | self |
| `app/static/style.css` | component | styling | `app/static/style.css` (same file) | self |
| `app/test_benchmark.py` | test | batch | `app/test_auth_methods.py` | role-match |

---

## Pattern Assignments

### `app/snapshots.py` (NEW — service, file-I/O + request-response)

**Analog:** `app/market_data.py`

**Imports + yfinance throttle pattern** (lines 1-31 of `market_data.py`):
```python
import logging
import threading
import time
from typing import Optional
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

_YF_DELAY = 0.25
_last_yf_request = 0.0

def _yf_throttle():
    """Sleep if needed to respect rate limits between yfinance calls."""
    global _last_yf_request
    with _fx_lock:
        elapsed = time.time() - _last_yf_request
        if elapsed < _YF_DELAY:
            time.sleep(_YF_DELAY - elapsed)
        _last_yf_request = time.time()
```

**Snapshot storage pattern** (based on D-04 through D-10 from 04-CONTEXT.md + `health_checks.py` lines 3-8 env var pattern):
```python
import os
import json
from pathlib import Path
from datetime import datetime

SNAPSHOT_DIR = os.getenv("SNAPSHOT_DIR", "/data/snapshots")
BENCHMARK_TICKER = os.getenv("BENCHMARK_TICKER", "^GSPC")

def save_snapshot(date_str: str, total_value_eur: float, benchmark_value: float, benchmark_return_pct: float):
    """Save portfolio snapshot for a given date."""
    path = Path(SNAPSHOT_DIR) / f"{date_str}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "date": date_str,
        "total_value_eur": total_value_eur,
        "benchmark_value": benchmark_value,
        "benchmark_return_pct": benchmark_return_pct,
    }
    with open(path, "w") as f:
        json.dump(data, f)
```

**Benchmark fetch pattern** (from `market_data.py` `enrich_position()` lines 189-292 + `_compute_performance()` lines 147-186):
```python
import yfinance as yf

def fetch_benchmark_series(start_date: str, end_date: str) -> list[dict]:
    """Fetch benchmark close prices indexed to 100 at start_date."""
    _yf_throttle()
    ticker = yf.Ticker(BENCHMARK_TICKER)
    hist = ticker.history(start=start_date, end=end_date)
    if hist.empty:
        return []

    start_price = float(hist["Close"].iloc[0])
    return [
        {"date": str(dt.date()), "value": round((float(price) / start_price) * 100, 4)}
        for dt, price in hist["Close"].items()
    ]
```

**Attribution computation** (from 04-RESEARCH.md Pattern 4):
```python
def compute_attribution(positions: list[dict], benchmark_return: float) -> list[dict]:
    """
    relative_contribution = (position_return - benchmark_return) * weight * direction
    absolute_contribution = position_return * weight
    """
    results = []
    for p in positions:
        pos_return = p.get("perf_ytd") or 0  # Handle None gracefully
        weight = p.get("weight", 0) / 100.0

        direction = 1 if pos_return >= 0 else -1
        relative = (pos_return - benchmark_return) * weight * direction
        absolute = pos_return * weight

        results.append({
            "name": p.get("name"),
            "relative_contribution": round(relative, 4),
            "absolute_contribution": round(absolute, 4),
        })
    return sorted(results, key=lambda x: abs(x["absolute_contribution"]), reverse=True)
```

---

### `app/scoring.py` (MODIFY — add `compute_attribution()`, transform)

**Analog:** `app/scoring.py` itself (same file — add new function alongside existing functions)

**Existing function pattern to follow** (lines 121-134 of `scoring.py`):
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

**New function to add** (compute_attribution) — see `app/snapshots.py` section above.

---

### `app/context_builder.py` (MODIFY — extend `build_hermes_context()`, transform)

**Analog:** `app/context_builder.py` itself (same file — extend existing function)

**Existing structure to extend** (lines 14-53 of `context_builder.py`):
```python
def build_hermes_context(portfolio: dict) -> dict:
    """Build Hermes-ready context from portfolio data.

    Returns:
        {
            "json": {...},       # Full structured data
            "plaintext": "..."   # Ready-to-paste text block
        }
    """
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    positions = portfolio.get("positions", [])
    top_candidates = portfolio.get("top_candidates", {"etfs": [], "stocks": []})

    # Build JSON structure
    json_context = {
        "snapshot_date": date_str,
        "portfolio_summary": {
            "total_value_eur": portfolio.get("total_value"),
            ...
        },
        "positions": sorted(positions, key=lambda p: p.get("momentum_score") or 0),
        "top_candidates": top_candidates,
        "health_alerts": portfolio.get("health_alerts", []),
    }

    # Build plaintext
    plaintext = _build_plaintext(json_context, date_str)

    return {"json": json_context, "plaintext": plaintext}
```

**Extension pattern:** Add `benchmark_summary` key to `json_context` with benchmark comparison data (portfolio indexed value, benchmark indexed value, attribution).

---

### `app/main.py` (MODIFY — add `/api/benchmark` endpoint + snapshot-on-refresh, request-response)

**Analog:** `app/main.py` itself (same file — existing endpoint patterns)

**Existing endpoint pattern** (lines 323-376 of `main.py`):
```python
@app.get("/api/portfolio", dependencies=[Depends(verify_brok_token)])
async def get_portfolio():
    """Return full portfolio with all computed metrics."""
    with _session_lock:
        portfolio = _session["portfolio"]
        if portfolio is not None:
            return portfolio

        if not _is_session_valid():
            raise HTTPException(
                status_code=401,
                detail="Session expired or not authenticated. Please reconnect via the UI.",
            )
        trading_api = _session["trading_api"]

    try:
        # Fetch raw portfolio from DeGiro
        raw = DeGiroClient.fetch_portfolio(trading_api)

        # Enrich with yfinance data
        positions = await asyncio.to_thread(enrich_positions, raw)

        # Compute portfolio weights
        positions = compute_portfolio_weights(positions)

        # Compute scores
        positions = compute_scores(positions)

        # Build summary
        portfolio = _build_portfolio_summary(positions, raw.get("cash_available", 0))

        # Compute health alerts
        health_alerts = compute_health_alerts({...})
        portfolio["health_alerts"] = health_alerts

        with _session_lock:
            _session["portfolio"] = portfolio
            _session["portfolio_time"] = datetime.now()

        return portfolio

    except Exception as e:
        logger.error("Portfolio fetch error: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch portfolio")
```

**Snapshot-on-refresh pattern** (add inside `get_portfolio()` after portfolio is built, before returning):
```python
# Save snapshot on each portfolio refresh (D-04)
from .snapshots import save_snapshot
date_str = datetime.now().strftime("%Y-%m-%d")
benchmark_value = ...  # Fetch current benchmark, index to 100
benchmark_return_pct = ...  # Compute benchmark return since first snapshot
save_snapshot(date_str, portfolio["total_value"], benchmark_value, benchmark_return_pct)
```

**New `/api/benchmark` endpoint pattern** (following existing endpoint structure):
```python
@app.get("/api/benchmark", dependencies=[Depends(verify_brok_token)])
async def get_benchmark():
    """Return benchmark comparison data: snapshots, series, and attribution."""
    with _session_lock:
        portfolio = _session["portfolio"]

    if portfolio is None:
        raise HTTPException(status_code=404, detail="No portfolio data loaded. Refresh your portfolio first.")

    from .snapshots import load_snapshots, fetch_benchmark_series, compute_attribution
    snapshots = load_snapshots(os.getenv("SNAPSHOT_DIR", "/data/snapshots"))
    benchmark_series = fetch_benchmark_series(...)  # Date range from snapshots
    attribution = compute_attribution(portfolio["positions"], benchmark_return)

    return {
        "snapshots": snapshots,
        "benchmark_series": benchmark_series,
        "attribution": attribution,
    }
```

---

### `app/static/app.js` (MODIFY — extend `renderCharts()` + add `renderAttribution()`, client-rendering)

**Analog:** `app/static/app.js` itself (same file — `renderCharts()` function)

**Existing chart pattern** (lines 332-416 of `app.js`):
```javascript
function renderCharts() {
    const d = portfolioData;
    const positions = d.positions || [];

    // Destroy existing charts
    Object.values(charts).forEach((c) => c.destroy());
    charts = {};

    // 1. ETF vs Stocks donut
    charts.etfStock = new Chart($("#chart-etf-stock"), {
      type: "doughnut",
      data: {
        labels: ["ETFs", "Stocks"],
        datasets: [{
          data: [etfVal, stockVal],
          backgroundColor: ["#01696f", "#d97706"],
          borderColor: "#1a1a1a",
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "65%",
        plugins: {
          legend: { display: true, position: "bottom", labels: { color: "#888", font: { family: "Inter", size: 11 } } },
        },
      },
    });

    // 2. Top 10 by weight (horizontal bar)
    charts.topWeight = new Chart($("#chart-top-weight"), {
      type: "bar",
      data: {
        labels: top10.map((p) => truncate(p.name, 18)),
        datasets: [{
          data: top10.map((p) => p.weight || 0),
          backgroundColor: top10.map((p) => (p.asset_type === "ETF" ? "#01696f" : "#d97706")),
          borderRadius: 3,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: "y",
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: "#888", font: { family: "Inter", size: 10 } }, grid: { color: "#2a2a2a" } },
          y: { ticks: { color: "#888", font: { family: "Inter", size: 10 } }, grid: { display: false } },
        },
      },
    });
}
```

**New benchmark overlay chart** (from 04-RESEARCH.md Pattern 3):
```javascript
// Add to renderCharts() after existing charts
// 4. Benchmark overlay (indexed line chart)
charts.benchmark = new Chart($("#chart-benchmark"), {
  type: "line",
  data: {
    labels: snapshots.map(s => s.date),
    datasets: [
      {
        label: "Portfolio",
        data: snapshots.map(s => s.indexed_value),
        borderColor: "#01696f",
        backgroundColor: "transparent",
        tension: 0.1,
      },
      {
        label: "S&P 500",
        data: snapshots.map(s => s.benchmark_value),
        borderColor: "#d97706",
        backgroundColor: "transparent",
        tension: 0.1,
      },
    ],
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: true } },
    scales: {
      x: { ticks: { color: "#888" }, grid: { color: "#2a2a2a" } },
      y: { ticks: { color: "#888", callback: (v) => v.toFixed(0) }, grid: { color: "#2a2a2a" } },
    },
  },
});
```

**New attribution render function** (from 04-RESEARCH.md Pattern 3):
```javascript
function renderAttribution(attribution) {
    const container = $("#attribution-list");
    if (!container) return;

    if (!attribution || attribution.length === 0) {
        container.innerHTML = '<div class="attr-empty">No attribution data available</div>';
        return;
    }

    container.innerHTML = attribution.map(a => `
        <div class="attr-item">
            <span class="attr-name">${esc(a.name)}</span>
            <span class="attr-relative ${a.relative_contribution >= 0 ? 'positive' : 'negative'}">${a.relative_contribution >= 0 ? '+' : ''}${a.relative_contribution.toFixed(2)}</span>
            <span class="attr-absolute ${a.absolute_contribution >= 0 ? 'positive' : 'negative'}">${a.absolute_contribution >= 0 ? '+' : ''}${a.absolute_contribution.toFixed(2)}</span>
        </div>
    `).join('');
}
```

---

### `app/static/index.html` (MODIFY — add canvas + attribution section, static-markup)

**Analog:** `app/static/index.html` itself (existing section/canvas patterns)

**Existing chart section pattern** (lines 94-114 of `index.html`):
```html
<!-- ALLOCATION CHARTS -->
<section class="charts-section">
  <div class="card chart-card">
    <h3 class="chart-title">ETF vs Stocks</h3>
    <div class="chart-wrap">
      <canvas id="chart-etf-stock"></canvas>
    </div>
  </div>
  <div class="card chart-card">
    <h3 class="chart-title">Top 10 by Weight</h3>
    <div class="chart-wrap">
      <canvas id="chart-top-weight"></canvas>
    </div>
  </div>
  <div class="card chart-card">
    <h3 class="chart-title">Sector Breakdown</h3>
    <div class="chart-wrap">
      <canvas id="chart-sector"></canvas>
    </div>
  </div>
</section>
```

**New benchmark + attribution sections to add** (after existing charts-section):
```html
<!-- BENCHMARK SECTION -->
<section class="benchmark-section">
  <div class="card chart-card" style="grid-column: span 2;">
    <h3 class="chart-title">Portfolio vs S&P 500 (Indexed to 100)</h3>
    <div class="chart-wrap">
      <canvas id="chart-benchmark"></canvas>
    </div>
  </div>
</section>

<!-- ATTRIBUTION SECTION -->
<section class="attribution-section">
  <div class="card">
    <h3 class="chart-title">Position Attribution</h3>
    <div id="attribution-list" class="attr-list"></div>
  </div>
</section>
```

---

### `app/static/style.css` (MODIFY — add benchmark + attribution styles, styling)

**Analog:** `app/static/style.css` itself (existing card/section patterns)

**Existing chart section styles** (lines 222-245 of `style.css`):
```css
.charts-section {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.chart-card { min-height: 280px; }

.chart-title {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-dim);
  margin-bottom: 12px;
}

.chart-wrap {
  position: relative;
  width: 100%;
  height: 230px;
}

.chart-wrap canvas { width: 100% !important; height: 100% !important; }
```

**New styles to add** (following existing patterns):
```css
/* ─── BENCHMARK SECTION ─── */
.benchmark-section {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

/* ─── ATTRIBUTION ─── */
.attribution-section { margin-bottom: 20px; }

.attr-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.attr-item {
  display: flex;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
  font-size: 0.82rem;
}

.attr-item:last-child { border-bottom: none; }

.attr-name {
  flex: 1;
  font-weight: 500;
}

.attr-relative, .attr-absolute {
  min-width: 80px;
  text-align: right;
  font-weight: 600;
  margin-left: 16px;
}

.attr-relative.positive, .attr-absolute.positive { color: var(--green); }
.attr-relative.negative, .attr-absolute.negative { color: var(--red); }

.attr-empty {
  text-align: center;
  color: var(--text-dim);
  padding: 20px;
}
```

---

### `app/test_benchmark.py` (NEW test file, batch)

**Analog:** `app/test_auth_methods.py`

**Existing test pattern** (from `app/test_auth_methods.py`):
```python
"""Test authentication methods."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Tests would follow pytest patterns:
# def test_save_snapshot_creates_file():
#     ...
# def test_load_snapshots_returns_sorted_list():
#     ...
# def test_compute_attribution_with_known_inputs():
#     ...
```

**Note:** Project has ad-hoc test files (`app/test_*.py`) rather than a formal pytest suite. Follow the same pattern.

---

## Shared Patterns

### yfinance Rate Limiting
**Source:** `app/market_data.py` lines 20-31 (`_yf_throttle()`)
**Apply to:** `app/snapshots.py` — benchmark fetch functions
```python
_YF_DELAY = 0.25
_last_yf_request = 0.0

def _yf_throttle():
    global _last_yf_request
    with _fx_lock:
        elapsed = time.time() - _last_yf_request
        if elapsed < _YF_DELAY:
            time.sleep(_YF_DELAY - elapsed)
        _last_yf_request = time.time()
```

### Environment Variable Configuration
**Source:** `app/health_checks.py` lines 3-10, `app/market_data.py` lines 10-11
**Apply to:** All new config — `SNAPSHOT_DIR`, `BENCHMARK_TICKER`
```python
import os
HEALTH_POSITION_THRESHOLD = int(os.getenv("HEALTH_POSITION_THRESHOLD", "20"))
```

### Session Lock Pattern
**Source:** `app/main.py` lines 26-33, 329-343
**Apply to:** `app/snapshots.py` — thread-safe file operations if needed
```python
_session_lock = threading.Lock()
# Use with _session_lock when accessing shared state
```

### Chart.js destroy before recreate
**Source:** `app/static/app.js` lines 337-339
**Apply to:** `app/static/app.js` — new benchmark and attribution charts
```javascript
Object.values(charts).forEach((c) => c.destroy());
charts = {};
```

### Positive/negative color classes
**Source:** `app/static/style.css` lines 186-189, `app/static/app.js` lines 306-309
**Apply to:** Attribution values in `renderAttribution()`
```css
.pl-positive { color: var(--green); }
.pl-negative { color: var(--red); }
```

---

## No Analog Found

All files have direct analogs in the codebase (either the same file or a file with the same role).

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| — | — | — | All files matched |

---

## Metadata

**Analog search scope:** `app/` directory
**Files scanned:** 17 Python files, 3 static files
**Pattern extraction date:** 2026-04-23

**Key patterns summary:**
- yfinance fetching: `_yf_throttle()` + `yf.Ticker().history()` from `market_data.py`
- JSON file storage: `pathlib.Path` + `json.dump()` — `snapshots.py` will follow `health_checks.py` env var pattern
- Chart.js: `new Chart()` with destroy-before-create from `app.js` `renderCharts()`
- API endpoints: FastAPI `@app.get()` with `Depends(verify_brok_token)` from `main.py`
- Attribution computation: position dict transforms in `scoring.py` style
