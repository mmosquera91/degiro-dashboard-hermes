# Phase 4: Benchmark Tracking - Research

**Researched:** 2026-04-23
**Domain:** S&P 500 benchmark comparison, historical performance tracking, position attribution analysis
**Confidence:** HIGH

## Summary

Phase 4 adds benchmark comparison (S&P 500 overlay), historical performance tracking (snapshot-based), and attribution analysis (position-level contribution). The implementation builds on existing patterns: yfinance for market data, Chart.js for visualization, JSON file snapshots for historical data, and Hermes context integration. The architecture is straightforward: a new snapshot module for file I/O, a new `/api/benchmark` endpoint, new frontend chart section, and attribution computation in `scoring.py`.

**Primary recommendation:** Implement `app/snapshots.py` for snapshot storage, add a `/api/benchmark` endpoint in `main.py`, extend `context_builder.py` for benchmark context, add a new chart canvas to `index.html`, extend `renderCharts()` in `app.js` with a line chart, and compute attribution in `scoring.py`.

---

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Single benchmark: **S&P 500** (^GSPC via yfinance)
- **D-02:** Benchmark ticker configurable via environment variable (`BENCHMARK_TICKER`, default: `^GSPC`)
- **D-03:** MSCI World explicitly out of scope — do not implement
- **D-04:** Store each portfolio refresh as a snapshot — when user manually refreshes, save portfolio state to JSON
- **D-05:** Snapshot file: `{data_dir}/snapshots/{date}.json` — one file per day (overwrites if already exists)
- **D-06:** `SNAPSHOT_DIR` environment variable sets base directory (default: `/data/snapshots`)
- **D-07:** Benchmark data fetched fresh each request from yfinance — not stored separately
- **D-08:** Snapshot contains: `date`, `total_value_eur`, `benchmark_value` (normalized to 100 at portfolio start), `benchmark_return_pct`
- **D-09:** If no historical snapshots exist, chart shows only current moment comparison
- **D-10:** No auto-cleanup of old snapshots
- **D-11:** Two attribution metrics per position: relative contribution and absolute contribution
- **D-13:** Attribution computed on demand, not pre-computed at snapshot time
- **D-14:** Attribution shown in table or bar chart sorted by absolute contribution
- **D-15:** Indexed overlay chart — both series indexed to 100 at earliest snapshot date
- **D-16:** Normalized (0-100) explicitly rejected — indexed to 100 is preferred
- **D-17:** Chart X-axis: dates from stored snapshots (gaps allowed)
- **D-18:** If only one snapshot: show comparison as two separate points or simple table

### Deferred Ideas (OUT OF SCOPE)

- MSCI World as second benchmark
- Benchmark data caching (fetched fresh each time)
- Auto-cleanup of old snapshots
- Multi-benchmark overlay

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| S&P 500 historical data fetch | API / Backend | — | yfinance call in Python, not browser |
| Snapshot file storage | API / Backend | — | JSON file writes on server, not client |
| Snapshot retrieval | API / Backend | — | Read JSON files, serve via API |
| Indexed overlay chart | Browser / Client | — | Chart.js renders in browser using fetched data |
| Attribution table | Browser / Client | — | Computed from API data, rendered in DOM |
| Attribution calculation | API / Backend | Browser | Computed on demand in Python from snapshot data |
| Hermes context (benchmark) | API / Backend | — | `context_builder.py` runs server-side |

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TRACK-01 | Benchmark comparison chart — S&P 500 overlaid with portfolio | Chart.js line chart with dual series, indexed to 100 |
| TRACK-02 | Historical performance chart — portfolio value over time vs benchmark | Snapshot storage in JSON files, read on demand |
| TRACK-03 | Attribution analysis — which positions contributed most to gains/losses | Attribution computed from `position_return`, `benchmark_return`, `weight` |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Chart.js | 4.4.7 (in use) | Indexed overlay line chart | Already in project via CDN; line chart is standard for indexed performance comparison |
| yfinance | 0.2.51 (in use) | S&P 500 (^GSPC) historical data | Already in project; same API used for position enrichment |
| JSON (stdlib) | — | Snapshot file storage | No database; simple `{date}.json` files in configured directory |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `os`, `json`, `pathlib` | stdlib | Snapshot file read/write | All snapshot storage operations |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| JSON files | SQLite | Simplicity; single-user means no concurrency concerns; JSON is human-readable and requires no schema |
| ^GSPC | yfinance multiple tickers | D-03 explicitly rejects MSCI World; single benchmark is locked |
| Chart.js line chart | Recharts / D3 | Chart.js already in project; D-15/D-16 lock to indexed overlay which Chart.js handles natively |

**Installation:**
No new packages required. All dependencies (yfinance, Chart.js via CDN) already in use.

---

## Architecture Patterns

### System Architecture Diagram

```
Browser                              FastAPI                           Yahoo Finance          Filesystem
  |                                    |                                   |                      |
  |--- GET /api/portfolio-raw ------->|                                   |                      |
  |<-- raw portfolio ----------------|                                   |                      |
  |                                    |                                   |                      |
  |--- GET /api/portfolio ---------->|                                   |                      |
  |                                    |--- enrich_positions() ----------->|                      |
  |                                    |<-- prices, RSI, perf ------------|                      |
  |                                    |--- compute_scores()                                    |
  |                                    |--- _build_portfolio_summary()                          |
  |                                    |--- [save snapshot] ------------------------------------------------------>|
  |                                    |    (date.json with benchmark_value indexed to 100)                       |
  |<-- full portfolio ----------------|                                   |                      |
  |                                    |                                   |                      |
  |--- GET /api/benchmark ----------->|                                   |                      |
  |                                    |--- load all snapshots from SNAPSHOT_DIR                                   |
  |                                    |--- fetch ^GSPC from yfinance for date range                               |
  |                                    |--- compute attribution for each position                                   |
  |<-- {snapshots, benchmark_series, attribution} --|                    |                      |
  |                                    |                                   |                      |
  |--- renderCharts() (client) ------>|                                   |                      |
  |    charts.benchmark = new Chart()|                                   |                      |
```

### Recommended Project Structure

```
app/
├── snapshots.py          # NEW: snapshot save/load, benchmark fetch, attribution
├── market_data.py        # Existing: yfinance enrichment, FX rates
├── scoring.py            # Existing: compute_scores(), add compute_attribution()
├── context_builder.py    # Existing: extend build_hermes_context() with benchmark data
├── main.py               # Existing: add /api/benchmark endpoint, snapshot-on-refresh
├── static/
│   ├── index.html        # Existing: add chart canvas + attribution table section
│   ├── app.js           # Existing: extend renderCharts() + renderAttribution()
│   └── style.css        # Existing: add chart section + attribution styles
data/snapshots/           # Created at runtime via SNAPSHOT_DIR env var
└── 2026-04-23.json      # One file per day with portfolio + benchmark snapshot
```

### Pattern 1: Snapshot Storage

**What:** JSON file per day storing portfolio state and normalized benchmark value.
**When to use:** When user refreshes portfolio — each manual refresh is a snapshot opportunity.
**Example:**
```python
# Source: D-04 through D-10 from 04-CONTEXT.md
import json, os
from pathlib import Path

SNAPSHOT_DIR = os.getenv("SNAPSHOT_DIR", "/data/snapshots")

def save_snapshot(date_str: str, total_value_eur: float, benchmark_value: float, benchmark_return_pct: float):
    """Save portfolio snapshot for a given date."""
    path = Path(SNAPSHOT_DIR) / f"{date_str}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "date": date_str,
        "total_value_eur": total_value_eur,
        "benchmark_value": benchmark_value,   # indexed to 100 at portfolio start date
        "benchmark_return_pct": benchmark_return_pct,
    }
    with open(path, "w") as f:
        json.dump(data, f)
```

### Pattern 2: Benchmark Data Fetching

**What:** Fetch ^GSPC historical data from yfinance for a date range derived from stored snapshots.
**When to use:** On `/api/benchmark` call to get historical comparison data.
**Example:**
```python
# Source: market_data.py patterns + D-02
import yfinance as yf
from datetime import datetime

BENCHMARK_TICKER = os.getenv("BENCHMARK_TICKER", "^GSPC")

def fetch_benchmark_series(start_date: str, end_date: str) -> list[dict]:
    """Fetch benchmark close prices indexed to 100 at start_date."""
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

### Pattern 3: Indexed Overlay Chart (Chart.js)

**What:** A line chart with two series (portfolio, benchmark) both indexed to 100 at the earliest snapshot date.
**When to use:** TRACK-01 and TRACK-02 — the primary visualization.
**Example:**
```javascript
// Source: app.js renderCharts() patterns + D-15/D-16
charts.benchmark = new Chart($("#chart-benchmark"), {
  type: "line",
  data: {
    labels: snapshots.map(s => s.date),  // x-axis: dates
    datasets: [
      {
        label: "Portfolio",
        data: snapshots.map(s => s.indexed_value),  // indexed to 100
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

### Pattern 4: Attribution Calculation

**What:** Two metrics per position — relative contribution (benchmark-beating performance) and absolute contribution (cash impact).
**When to use:** TRACK-03 — attribution table/bar chart.
**Formula (from D-11):**
```python
# Source: D-11/D-12 from 04-CONTEXT.md
def compute_attribution(positions: list[dict], benchmark_return: float) -> list[dict]:
    """
    relative_contribution = (position_return - benchmark_return) * weight * direction
    absolute_contribution = position_return * weight
    """
    results = []
    for p in positions:
        pos_return = p.get("perf_ytd") or 0  # YTD return as proxy
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

### Anti-Patterns to Avoid

- **Pre-computing attribution at snapshot time:** D-13 locks computation on-demand. Pre-computing would couple snapshot format to attribution logic.
- **Storing benchmark data in snapshots:** D-07 says benchmark fetched fresh. Storing it would require invalidation logic and is explicitly rejected.
- **Normalized (0-100) scale:** D-16 explicitly rejects this in favor of indexed to 100 — indexed shows actual relative performance.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| S&P 500 data fetching | Custom HTTP client for Yahoo Finance | yfinance | Already in project, handles rate limiting, ticker resolution |
| Snapshot file management | SQLite or custom DB | JSON files per day | Simplicity; human-readable; no schema migration; single-user means no concurrency |
| Indexed chart rendering | D3 from scratch | Chart.js line chart | Already in project via CDN; indexed dual-line chart is a standard Chart.js pattern |
| Attribution computation | Custom formula outside of scoring | `compute_attribution()` in `scoring.py` | Keeps attribution logic near other scoring/computation logic; consistent patterns |

**Key insight:** yfinance is the industry standard for personal finance data fetching in Python. JSON snapshot files align with the single-user, no-database constraint. Chart.js is already serving all portfolio charts.

---

## Common Pitfalls

### Pitfall 1: Snapshot directory not existing on first run

**What goes wrong:** `save_snapshot()` fails if `SNAPSHOT_DIR` does not exist, especially in Docker where `/data` may not be pre-created.
**Why it happens:** The code uses `mkdir(parents=True, exist_ok=True)` but the *parent* path must exist or `Path().mkdir` cannot create nested directories in some configurations.
**How to avoid:** Ensure `SNAPSHOT_DIR` defaults to a path that Docker volume mount creates, or add explicit directory creation at startup in `main.py`.
**Warning signs:** `FileNotFoundError` on snapshot save after first portfolio refresh.

### Pitfall 2: yfinance rate limiting causing incomplete benchmark data

**What goes wrong:** Benchmark historical data fetch fails or returns partial data due to rate limiting.
**Why it happens:** yfinance has undocumented rate limits. The existing `_yf_throttle()` in `market_data.py` applies 0.25s delay but only between requests in that module.
**How to avoid:** Apply the same throttle decorator to benchmark fetch function. Fetch only the date range needed (from earliest snapshot to today), not full history.
**Warning signs:** Empty `benchmark_series` in API response, or dates missing from the series.

### Pitfall 3: Sparse snapshots causing flat indexed line

**What goes wrong:** If user only refreshes once per month, the "historical" chart has very few points — still correct but visually sparse.
**Why it happens:** D-09 acknowledges this; D-17 allows gaps. This is by design but may confuse users expecting continuous lines.
**How to avoid:** In the frontend, render the chart with `spanGaps: true` in Chart.js to connect points across date gaps. Document the sparse data behavior in D-18 fallback (single snapshot renders as table).
**Warning signs:** Chart looks "broken" to users — `spanGaps: true` is the standard fix.

### Pitfall 4: Single snapshot edge case not handled in frontend

**What goes wrong:** With only one snapshot, Chart.js cannot render a line (needs 2+ points for line type).
**Why it happens:** D-18 specifies this fallback but frontend may not implement it.
**How to avoid:** Check number of snapshots before rendering: if 1, render a comparison table instead of a chart. If 2+, render line chart.
**Warning signs:** Empty canvas or JavaScript error when Chart.js receives single data point for a line chart.

### Pitfall 5: Attributing with `perf_ytd` when position has no YTD data

**What goes wrong:** `perf_ytd` may be `None` for some positions (yfinance enrichment failure).
**Why it happens:** `enrich_position()` sets `perf_ytd` to `None` when historical data is insufficient.
**How to avoid:** Fill `None` with 0 in attribution calculation (D-13 says on-demand computation; handle None gracefully). Document that 0 means "no data" rather than "no return."
**Warning signs:** Attribution table shows positions with `None` contribution.

---

## Code Examples

### Fetching S&P 500 Historical Data with yfinance

```python
# Source: market_data.py patterns + D-02
import yfinance as yf
from datetime import datetime, timedelta

def fetch_benchmark_for_dates(ticker: str, start_date: str, end_date: str) -> list[dict]:
    """Fetch benchmark close prices for a date range."""
    _yf_throttle()  # Use existing throttle from market_data.py
    data = yf.download(ticker, start=start_date, end=end_date, progress=False)
    if data.empty:
        return []
    closes = data["Close"].dropna()
    return [
        {"date": str(dt.date()), "close": float(price)}
        for dt, price in closes.items()
    ]
```

### Loading All Snapshots

```python
# Source: D-04/D-05/D-08
from pathlib import Path
import json

def load_snapshots(snapshot_dir: str) -> list[dict]:
    """Load all snapshot JSON files, sorted by date."""
    path = Path(snapshot_dir)
    if not path.exists():
        return []
    snapshots = []
    for f in sorted(path.glob("*.json")):
        with open(f) as fh:
            snapshots.append(json.load(fh))
    return snapshots
```

### Attribution Bar Chart in Chart.js

```javascript
// Source: D-14 + existing topWeight chart pattern
charts.attribution = new Chart($("#chart-attribution"), {
  type: "bar",
  data: {
    labels: attribution.map(a => truncate(a.name, 15)),
    datasets: [
      {
        label: "Absolute Contribution",
        data: attribution.map(a => a.absolute_contribution),
        backgroundColor: attribution.map(a =>
          a.absolute_contribution >= 0 ? "#22c55e" : "#ef4444"
        ),
        borderRadius: 3,
      },
    ],
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: "y",
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { color: "#888" }, grid: { color: "#2a2a2a" } },
      y: { ticks: { color: "#888", font: { size: 10 } }, grid: { display: false } },
    },
  },
});
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No benchmark tracking | Indexed S&P 500 overlay | Phase 4 (this phase) | Portfolio vs market comparison |
| Single-point performance | Snapshot-based historical tracking | Phase 4 (this phase) | Users see portfolio trajectory over time |

**Deprecated/outdated:**
- None relevant to this phase.

---

## Assumptions Log

> List all claims tagged `[ASSUMED]` in this research.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Snapshot date format is `YYYY-MM-DD` (matches `datetime.now().isoformat()`) | Snapshot Storage | Snapshot files may not sort correctly if format differs |
| A2 | `SNAPSHOT_DIR` defaults to `/data/snapshots` which Docker will create via volume mount | Environment | Snapshot saves may fail if `/data` doesn't exist in container |
| A3 | `perf_ytd` is an acceptable proxy for position return in attribution (D-11 uses `position_return`) | Attribution Calculation | If yfinance YTD data is stale/missing, attribution is inaccurate |

---

## Open Questions

1. **Should snapshot-on-refresh be triggered by `get_portfolio()` or a separate `POST /api/snapshot`?**
   - What we know: D-04 says "when user manually refreshes" — the refresh action calls `loadPortfolio()` which calls `GET /api/portfolio`
   - What's unclear: Should `get_portfolio()` save snapshot implicitly, or should the frontend call a separate snapshot endpoint after successful refresh?
   - Recommendation: Have `get_portfolio()` save snapshot as a side effect — keeps the trigger tied to the existing flow without frontend changes.

2. **Should attribution use `perf_ytd` or a weighted blend of `perf_30d`/`perf_90d`/`perf_ytd`?**
   - What we know: D-11 says "position_return" — the scoring module uses weighted blend (0.20/0.30/0.50) for momentum
   - What's unclear: Attribution should reflect long-term performance (YTD) matching the benchmark period
   - Recommendation: Use `perf_ytd` directly (already available per position) for consistency with benchmark period

3. **What should the attribution table show if a position has no `perf_ytd` data?**
   - What we know: yfinance enrichment sets `None` on failure
   - What's unclear: Should it show "N/A" or treat as 0% return?
   - Recommendation: Treat as 0% return (contribution = 0) but flag visually as "no data" in the table

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| yfinance | Benchmark data fetch | ✓ | 0.2.51 (requirements.txt) | — |
| Chart.js (CDN) | Overlay chart rendering | ✓ | 4.4.7 (index.html) | — |
| Python json/Pathlib | Snapshot file I/O | ✓ | stdlib | — |
| `/data/snapshots/` dir | Snapshot storage | ✗ | N/A | Create on startup or use `/tmp/snapshots` |

**Missing dependencies with fallback:**
- `/data/snapshots/` — Docker volume mount must create this directory. Plan should include a startup check or `Path.mkdir(parents=True, exist_ok=True)` at first snapshot save. If not available, fallback to `/tmp/brokr-snapshots`.

**Missing dependencies with no fallback:**
- None — all code dependencies are already in the project.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (project uses `app/test_*.py` files; no pytest.ini found) |
| Config file | none detected — existing test files are ad-hoc scripts |
| Quick run command | `python -m pytest` or `python app/test_*.py` |
| Full suite command | `python -m pytest` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|------------------|-------------|
| TRACK-01 | Benchmark overlay chart renders | smoke | `GET /api/benchmark` returns valid JSON with `benchmark_series` | N/A |
| TRACK-02 | Snapshots saved on portfolio fetch | unit | `save_snapshot()` creates file; `load_snapshots()` reads it back | N/A |
| TRACK-03 | Attribution computed correctly | unit | `compute_attribution()` with known inputs produces expected output | N/A |

### Sampling Rate
- **Per task commit:** N/A (no automated tests yet for this phase)
- **Per wave merge:** N/A
- **Phase gate:** N/A — TEST-01/02/03 are Phase 6

### Wave 0 Gaps
- [ ] `app/test_benchmark.py` — covers snapshot save/load, benchmark fetch, attribution computation
- [ ] `app/test_snapshots.py` — covers snapshot module directly (if extracted)
- [ ] Framework install: `pip install pytest` — if none detected

*(If no gaps: "None — existing test infrastructure covers all phase requirements")*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A |
| V3 Session Management | no | N/A |
| V4 Access Control | no | N/A |
| V5 Input Validation | yes | `date` from snapshot filenames is parsed via `datetime.strptime()` — validate format before loading |
| V6 Cryptography | no | N/A |

### Known Threat Patterns for Snapshot Storage

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via `date` parameter | Tampering | Date string validated with `datetime.strptime(date_str, "%Y-%m-%d")` before constructing file path |
| Snapshot file injection | Information Disclosure | Only `json.dump()` is used; no `exec` or dynamic code evaluation on file contents |
| Benchmark ticker injection | Tampering | `BENCHMARK_TICKER` is a static env var; not user input |

---

## Sources

### Primary (HIGH confidence)

- `app/market_data.py` — yfinance patterns, `_yf_throttle()`, `get_fx_rate()`, `enrich_position()`
- `app/scoring.py` — `compute_portfolio_weights()`, score computation patterns, position dict conventions
- `app/static/app.js` — `renderCharts()`, `charts` object, Chart.js initialization patterns
- `04-CONTEXT.md` — All D-01 through D-18 locked decisions

### Secondary (MEDIUM confidence)

- yfinance documentation — `yf.Ticker().history()` API for historical price fetching
- Chart.js 4.4.7 docs — line chart `spanGaps`, dual-series overlay patterns

### Tertiary (LOW confidence)

- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all dependencies already in project; no new packages needed
- Architecture: HIGH — follows existing patterns (snapshot-on-refresh, Chart.js dual-series, Hermes context extension)
- Pitfalls: MEDIUM — identified from codebase patterns but not verified against actual failure logs

**Research date:** 2026-04-23
**Valid until:** 2026-05-23 (30 days — benchmark tracking patterns are stable; yfinance API is mature)
