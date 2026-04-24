# Stack Research — v1.1 Dashboard & Persistence Fix

**Domain:** Portfolio analytics dashboard with persistent snapshot storage
**Researched:** 2026-04-24
**Confidence:** MEDIUM-HIGH (based on existing codebase analysis — standard Python libraries, no new dependencies needed)

---

## Executive Summary

The v1.1 milestone requires two categories of stack work:

1. **Persistent snapshots** — Already implemented using stdlib `json` + `pathlib` in `snapshots.py`. No new libraries needed. Volume mount point `/data/snapshots` provides container restart survival.

2. **Blank per-stock metrics (RSI/Weight/Momentum/Buy Priority)** — Not a stack problem. The existing stack is correct. The issue is a data-flow bug: the `/api/portfolio` endpoint returns cached raw portfolio before enrichment completes, or the in-memory cache stores a partial state. No library additions required.

---

## Current Stack (Validated v1.0)

### Backend

| Component | Choice | Version | Rationale |
|-----------|--------|---------|-----------|
| **Runtime** | Python | 3.11 | Dockerfile base |
| **Framework** | FastAPI | 0.115.6 | ASGI, Pydantic v2, static file serving |
| **Server** | Uvicorn | 0.34.0 | Standard ASGI server |
| **HTTP Client** | httpx | 0.28.1 | Docker healthcheck only |
| **Data Processing** | pandas | 2.2.3 | Time-series operations |
| **Numerical** | numpy | 2.2.1 | RSI computation, median |

### External Integrations

| Component | Library | Version |
|-----------|---------|---------|
| **Broker API** | degiro-connector | 3.0.35 |
| **Market Data** | yfinance | 0.2.51 |

### Persistence

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Snapshot Storage** | stdlib `json` + `pathlib` | Already implemented in `snapshots.py` |
| **Storage Path** | `/data/snapshots` (env: `SNAPSHOT_DIR`) | Docker volume mount point |
| **Benchmark Data** | yfinance fetch (NOT stored) | Fresh on each call, not snapshot-dependent |

### Frontend (No Changes)

| Component | Choice | Version |
|-----------|--------|---------|
| **Language** | Vanilla JS (ES6+) | No build step |
| **Charts** | Chart.js | 4.4.7 via CDN |
| **Icons** | Lucide | 0.460.0 via CDN |
| **Fonts** | Google Fonts (Inter) | Via CDN |

---

## What IS Needed for v1.1

### 1. Persistent Snapshots — Already Implemented

The snapshot system in `app/snapshots.py` uses only stdlib:

```python
import json
from pathlib import Path

# File: app/snapshots.py (lines 41-53)
Path(SNAPSHOT_DIR).mkdir(parents=True, exist_ok=True)
file_path = Path(SNAPSHOT_DIR) / f"{date_str}.json"
with open(file_path, "w") as f:
    json.dump(snapshot, f, indent=2)
```

**No new library additions.** The system relies on:
- Docker volume mount for `/data/snapshots` (must be configured in `docker-compose.yml`)
- Stdlib `json` for serialization (already available)
- Stdlib `pathlib.Path` for path manipulation (already available)

**Required Docker change:** Add volume mount to `docker-compose.yml`:

```yaml
volumes:
  - ./snapshots:/data/snapshots  # persist snapshots across restarts
```

### 2. Fixing Blank Metrics — Root Cause Analysis

**NOT a stack problem.** The stack is correct. The blank metrics (RSI="-", Weight="-", Momentum="-", Buy Priority="-") are data-flow bugs, not missing libraries. The existing thread pool and yfinance enrichment are properly configured.

**Root causes (probable):**

| Symptom | Likely Root Cause | Fix Location |
|---------|------------------|-------------|
| RSI shows "-" | `enrich_position()` returning `None` for RSI because `compute_rsi()` gets insufficient history data | `app/market_data.py:251` — `hist = ticker.history(period="1y")` may return insufficient data for some tickers |
| Weight shows "-" | `_build_portfolio_summary()` called on stale cached data before `compute_portfolio_weights()` runs | `app/main.py` — check if cached portfolio has unweighted positions |
| Momentum/Buy Priority show "-" | `compute_scores()` receives positions with all-None performance fields | `app/scoring.py:44` — returns `None` when all perfs are `None` |

**No new libraries required** for fixing these. The thread pool in `main.py:379` is correctly used:

```python
positions = await asyncio.to_thread(enrich_positions, raw)
```

---

## No New Dependencies

The v1.1 milestone does not require any new Python packages. All needed functionality is available via:

| Needed For | Library | Status |
|-----------|---------|--------|
| JSON serialization | stdlib `json` | Already used in `snapshots.py` |
| File paths | stdlib `pathlib` | Already used |
| Thread pool | `asyncio.to_thread()` | Already used in `main.py` |
| Date handling | stdlib `datetime` | Already used |
| yfinance enrichment | yfinance 0.2.51 | Already in requirements.txt |

---

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **SQLite or any DB** | Single-user app, over-engineering | JSON files in `/data/snapshots` |
| **pickle serialization** | Security risk (arbitrary code exec) | stdlib `json` |
| **Dask or Polars** | Overkill for this data volume | pandas 2.2.3 is sufficient |
| **Celery or task queue** | Single-user app, unnecessary complexity | `asyncio.to_thread()` thread pool |
| **Redis** | Adds infrastructure burden | In-memory cache + JSON snapshots |
| **orjson or msgspec** | Not needed; stdlib `json` is fast enough for snapshot sizes | stdlib `json` |

---

## Integration Points

### Snapshot Storage

**Write path:** `app/snapshots.py:save_snapshot()` called as side effect in `/api/portfolio` after enrichment.

**Read path:** `app/snapshots.py:load_snapshots()` called in:
- `/api/portfolio` (lines 402-416) — to index benchmark to 100 at first snapshot
- `/api/benchmark` (lines 507-516) — to get historical snapshots

**Data directory:** `/data/snapshots/` (configurable via `SNAPSHOT_DIR` env var)

### Thread Pool Integration

The existing thread pool pattern (`asyncio.to_thread()`) should be used for any new blocking I/O:

```python
# Existing pattern in main.py:379
positions = await asyncio.to_thread(enrich_positions, raw)
```

No changes needed to the thread pool — it correctly handles the synchronous `enrich_positions` call without blocking the event loop.

---

## Installation

No new packages needed. Existing `requirements.txt` is sufficient:

```bash
# Existing — no changes needed
fastapi==0.115.6
uvicorn==0.34.0
degiro-connector==3.0.35
yfinance==0.2.51
pandas==2.2.3
numpy==2.2.1
httpx==0.28.1
python-multipart==0.0.20
```

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Snapshot stack | HIGH | Stdlib only, already implemented and working |
| Metric fix (no new lib needed) | HIGH | Bug is in data flow, not missing libraries |
| Thread pool integration | HIGH | Already correctly implemented |
| Docker volume config | MEDIUM | Must verify `docker-compose.yml` has volume mount |

---

## Conclusion

**No new stack additions are required for v1.1.** The existing stdlib JSON + pathlib-based snapshot system is the correct approach for a single-user portfolio dashboard. The blank metrics issue is a data-flow bug that requires debugging of the existing enrichment pipeline, not new libraries.

The only action item is ensuring the Docker volume mount is configured to persist `/data/snapshots` across container restarts.

---

*Stack research for: Brokr v1.1 Dashboard & Persistence Fix*
*Researched: 2026-04-24*
