# Architecture Research

**Domain:** Portfolio Analytics Dashboard with Persistent Caching
**Project:** Brokr v1.1 — Dashboard Fix & Persistence
**Researched:** 2026-04-24
**Confidence:** HIGH

## Current Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FastAPI (app/main.py)                           │
│  Routes: /api/auth, /api/portfolio, /api/benchmark, /api/hermes-context   │
│  In-memory session cache: _session dict (thread-safe)                    │
│  SESSION_TTL=30min, PORTFOLIO_TTL=5min                                  │
└──────────────┬─────────────────┬─────────────────┬──────────────────────┘
               │                 │                 │
               v                 v                 v
      degiro_client.py     market_data.py     scoring.py
      (DeGiro API v3)      (yfinance thread   (numpy scoring)
                            pool enrichment)
               │                 │                 │
               v                 v                 v
         DeGiro API       Yahoo Finance      Position scores
         (trader.           (^GSPC S&P500)
          degiro.nl)
               │
               v
         snapshots.py ←── ONLY stores: date, total_value_eur,
                           benchmark_value, benchmark_return_pct
                           (NOT enriched positions)
```

## Problem Statement

`snapshots.py` already exists and is functional, but its snapshot format is **incomplete**:

- `save_snapshot()` only records 4 scalar fields: date, total_value_eur, benchmark_value, benchmark_return_pct
- Enriched positions (RSI, momentum, sector, buy priority, weights) are **not** serialized to disk
- On container restart, `_session` is cleared, and even if a snapshot exists, `get_portfolio()` returns blank per-stock metrics because the enrichment chain cannot run without a live DeGiro session

**Result:** Dashboard shows "-" for RSI, Weight, Momentum, Buy Priority after restart.

## Integration Points

### 1. Extend `save_snapshot()` in `snapshots.py`

**Current signature:**
```python
def save_snapshot(
    date_str: str,
    total_value_eur: float,
    benchmark_value: float,
    benchmark_return_pct: float,
) -> None:
```

**New signature (backward-compatible):**
```python
def save_snapshot(
    date_str: str,
    total_value_eur: float,
    benchmark_value: float,
    benchmark_return_pct: float,
    portfolio_data: dict | None = None,  # NEW: full enriched portfolio
) -> None:
```

**Changes:**
- When `portfolio_data` is provided, serialize it alongside scalar snapshot
- File format: JSON with both scalar and portfolio sections
- Backward-compatible: existing snapshots without `portfolio_data` still load correctly

**Storage format (proposed):**
```json
{
  "date": "2026-04-24",
  "total_value_eur": 50000.0,
  "benchmark_value": 110.5,
  "benchmark_return_pct": 10.5,
  "portfolio": { ... full enriched portfolio from _build_portfolio_summary ... }
}
```

### 2. Add `load_latest_snapshot()` in `snapshots.py`

```python
def load_latest_snapshot() -> dict | None:
    """Load most recent snapshot that contains full portfolio data."""
```

**Behavior:**
- Load all snapshots sorted by date descending
- Return first one with `portfolio` key populated
- Return `None` if no valid portfolio snapshot found

### 3. Restore on startup in `main.py`

**Location:** `@app.on_event("startup")` in `main.py`

**Current behavior:**
```python
@app.on_event("startup")
async def on_startup():
    logger.info("Startup event fired")
    # Module import checks only
```

**New behavior:**
```python
@app.on_event("startup")
async def on_startup():
    logger.info("Startup event fired")
    # ... existing checks ...

    # Restore portfolio from disk if no active session
    from .snapshots import load_latest_snapshot
    snapshot = load_latest_snapshot()
    if snapshot is not None:
        with _session_lock:
            _session["portfolio"] = snapshot["portfolio"]
            _session["portfolio_time"] = datetime.now()
        logger.info("Portfolio restored from snapshot: %s", snapshot["date"])
```

**Key insight:** We restore into `_session["portfolio"]` so `get_portfolio()` returns it directly without re-enriching. The session itself may still be expired (intAccount/JSESSIONID needed for trades), but portfolio data is served from the restored snapshot.

### 4. Modify `get_portfolio()` in `main.py`

**Current flow:**
```
get_portfolio()
  → Check _session["portfolio"] cache → Return if exists
  → Else: require live DeGiro session
  → Fetch → Enrich → Score → Build summary → Save snapshot → Return
```

**New flow:**
```
get_portfolio()
  → Check _session["portfolio"] cache → Return if exists (UNCHA NGED)
  → Else: require live DeGiro session
  → Fetch → Enrich → Score → Build summary → Save snapshot with portfolio → Return

  + ON STARTUP (session expired):
    → load_latest_snapshot()
    → Restore portfolio into _session["portfolio"]
    → get_portfolio() now hits cache and returns without enrichment
```

### 5. Dashboard frontend fixes

**Blank per-stock metrics:** Already addressed by snapshot restoration. After restart, restored portfolio contains all enriched position data (RSI, weight, momentum, buy_priority_score).

**Sector breakdown chart (missing):** Rendered in frontend but data is `{}` when portfolio lacks `sector` data from enrichment. Will auto-populate once portfolio is restored.

**Benchmark comparison chart (missing):** Same — benchmark data comes from `GET /api/benchmark` which calls `fetch_benchmark_series()` fresh from yfinance. The chart expects `benchmark_series` array with `{date, value}` objects.

## Data Flow

### Normal operation (live DeGiro session)

```
User → GET /api/portfolio
  ↓
main.py:get_portfolio()
  ↓ (session valid, no cache)
DeGiroClient.fetch_portfolio()
  ↓
market_data.enrich_positions() [asyncio.to_thread, ~5s]
  ↓
scoring.compute_portfolio_weights()
  ↓
scoring.compute_scores()
  ↓
_build_portfolio_summary() → enriched positions dict
  ↓
compute_health_alerts()
  ↓
save_snapshot(date, total_value, benchmark, return_pct, portfolio_data) ← MODIFIED
  ↓
_session["portfolio"] = portfolio
  ↓
Return JSON to frontend
```

### Restart operation (no live session)

```
Container starts
  ↓
on_startup() → load_latest_snapshot() → restore into _session["portfolio"]
  ↓
User → GET /api/portfolio
  ↓
main.py:get_portfolio() → _session["portfolio"] exists (restored) → Return directly
  ↓
No DeGiro fetch, no yfinance enrichment needed
```

### Benchmark chart data flow (unchanged)

```
User → GET /api/benchmark
  ↓
load_snapshots() → list of {date, total_value_eur, benchmark_value, ...}
  ↓
fetch_benchmark_series(first_date, today) → yfinance ^GSPC fresh fetch
  ↓
compute_attribution(portfolio["positions"], latest_benchmark_return)
  ↓
Return {snapshots, benchmark_series, attribution}
  ↓
Frontend renders: snapshot line chart + S&P 500 indexed line + attribution table
```

## Component Responsibilities

| Component | File | Responsibility | Changes for v1.1 |
|-----------|------|----------------|-------------------|
| FastAPI app | `main.py` | Route handling, session cache, lifespan | Startup snapshot restoration |
| DeGiro client | `degiro_client.py` | Auth + portfolio fetch | None |
| Market data | `market_data.py` | yfinance enrichment (thread pool) | None |
| Scoring | `scoring.py` | Momentum, value, buy priority scores | None |
| Snapshots | `snapshots.py` | Disk persistence of snapshot data | Extend save_snapshot, add load_latest_snapshot |
| Health checks | `health_checks.py` | Alert computation | None |
| Context builder | `context_builder.py` | Hermes JSON export | None |
| Frontend | `static/app.js` | Dashboard rendering, charts | Fix sector/benchmark chart rendering |

## Suggested Build Order

Based on dependency order (enrichment must happen before scoring before saving):

### Phase 1: Extend snapshot format
- Modify `snapshots.py`: Add `portfolio_data` parameter to `save_snapshot()`
- Add `load_latest_snapshot()` function
- Test round-trip: save with portfolio → load → verify all fields present

### Phase 2: Startup restoration
- Modify `main.py` `@app.on_event("startup")` to call `load_latest_snapshot()`
- Restore portfolio into `_session["portfolio"]` if snapshot found
- Verify dashboard loads without DeGiro credentials after restart

### Phase 3: Frontend fixes
- Verify sector breakdown chart renders from restored `portfolio["sector_breakdown"]`
- Verify benchmark comparison chart renders from `GET /api/benchmark`
- Fix any null-check issues in chart rendering code

## Anti-Patterns to Avoid

### Anti-Pattern 1: Re-enriching on every request
**What might be tempting:** Reload and re-enrich from disk on every `get_portfolio()` call.
**Why it's wrong:** yfinance calls are slow (~5s), unnecessary for cached data.
**Instead:** Only restore on startup or when cache is cold. Cache serves reads.

### Anti-Pattern 2: Storing unprocessed positions
**What might be tempting:** Save raw DeGiro positions to snapshot, enrich on load.
**Why it's wrong:** yfinance is external service, rate-limited, slow. Defeats restart-survival goal.
**Instead:** Always save enriched/scored positions. Load from disk = instant dashboard.

### Anti-Pattern 3: Blocking startup on enrichment
**What might be tempting:** Run full enrichment chain on startup to "refresh" snapshot.
**Why it's wrong:** Requires live DeGiro session. If session expired, blocks forever.
**Instead:** Startup restoration is synchronous, non-blocking. Fresh enrichment only on user request.

## Scaling Considerations

| Scale | Portfolio Persistence | Session Management | Notes |
|-------|---------------------|-------------------|-------|
| Single user (current) | Snapshots to `/data/snapshots/` | In-memory TTL cache | Sufficient |
| 1-10 users | Same | Same | Each user needs separate session dict |
| 10+ users | Need database (PostgreSQL) | Session per user | Current architecture not multi-user ready |

Current scope remains single-user. Snapshot persistence at `/data/snapshots/` is Docker volume mounted.

## Sources

- Codebase analysis: `app/main.py`, `app/snapshots.py`, `app/degiro_client.py`, `app/scoring.py`, `app/market_data.py`
- Project context: `.planning/PROJECT.md` v1.1 milestone goals
- Existing architecture: `.planning/research/ARCHITECTURE.md` (2026-04-23)

---
*Architecture research for: Brokr v1.1 Dashboard Fix & Persistence*
*Researched: 2026-04-24*
