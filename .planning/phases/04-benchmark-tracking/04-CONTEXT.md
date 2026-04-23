# Phase 04: Benchmark Tracking - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Add S&P 500 / MSCI World benchmark comparison and historical performance tracking. Delivers TRACK-01 through TRACK-03:
- Benchmark comparison chart — S&P 500 performance overlaid with portfolio (TRACK-01)
- Historical performance chart — portfolio value over time vs benchmark (TRACK-02)
- Attribution analysis — which positions contributed most to gains/losses (TRACK-03)

Benchmark tracking appears in dashboard UI and is included in Hermes context API.

</domain>

<decisions>
## Implementation Decisions

### Benchmark Selection (TRACK-01)

- **D-01:** Single benchmark: **S&P 500** (^GSPC via yfinance)
- **D-02:** Benchmark ticker configurable via environment variable (`BENCHMARK_TICKER`, default: `^GSPC`)
- **D-03:** MSCI World is explicitly out of scope — do not implement alongside S&P 500

### Snapshot Storage (TRACK-02)

- **D-04:** **Store each portfolio refresh as a snapshot** — when user manually refreshes, save portfolio state to a JSON file
- **D-05:** Snapshot file: `{data_dir}/snapshots/{date}.json` — one file per day (overwrites if already exists for today)
- **D-06:** `SNAPSHOT_DIR` environment variable sets the base directory (default: `/data/snapshots`)
- **D-07:** Benchmark data is **not** stored separately — fetched fresh on each request from yfinance
- **D-08:** Snapshot contains: `date`, `total_value_eur`, `benchmark_value` (normalized to 100 at portfolio start date), `benchmark_return_pct`
- **D-09:** If no historical snapshots exist yet, chart shows only a single point (portfolio vs benchmark at current moment)
- **D-10:** No auto-cleanup of old snapshots — user manages manually if needed

### Attribution Calculation (TRACK-03)

- **D-11:** Two attribution metrics per position:
  - **Relative contribution:** `(position_return − benchmark_return) × weight × direction` — measures benchmark-beating performance
  - **Absolute contribution:** `position_return × weight` — pure cash impact on portfolio
- **D-12:** Both values shown in the UI — relative for "did this beat the market?", absolute for "how much did it move my portfolio?"
- **D-13:** Attribution is computed on demand from current snapshot data, not pre-computed at snapshot time
- **D-14:** Attribution shown in a table or bar chart sorted by absolute contribution (largest contributors first)

### Overlay Chart (TRACK-01, TRACK-02)

- **D-15:** **Indexed overlay** — single line chart with two series:
  - Series 1: Portfolio value, indexed to 100 at the earliest snapshot date
  - Series 2: Benchmark, indexed to 100 at the same earliest snapshot date
- **D-16:** Normalized (0-100) is explicitly rejected — indexed to 100 is preferred for showing actual relative performance
- **D-17:** Chart X-axis: dates from stored snapshots (gaps allowed — sparse data is fine)
- **D-18:** If only one snapshot: show current comparison as two separate points or a simple table (not a full chart)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Context
- `.planning/phases/01-security-hardening/01-CONTEXT.md` — Auth token pattern, env var conventions
- `.planning/phases/02-performance/02-CONTEXT.md` — Threading patterns, FX cache locking
- `.planning/phases/03-health-indicators/03-CONTEXT.md` — Health alerts pattern, env var conventions for thresholds
- `.planning/ROADMAP.md` §Phase 4 — Phase goal, success criteria, implementation notes
- `.planning/REQUIREMENTS.md` §Performance Tracking (TRACK) — TRACK-01, TRACK-02, TRACK-03

### Codebase
- `app/market_data.py` — `enrich_position()`, `get_fx_rate()`, existing yfinance patterns
- `app/scoring.py` — `compute_portfolio_weights()`, scoring logic
- `app/context_builder.py` — Hermes context structure, plaintext formatting
- `app/main.py` — `get_portfolio()` endpoint, session cache patterns
- `app/static/app.js` — `renderCharts()`, `charts` object, existing Chart.js usage
- `app/static/index.html` — chart canvas elements

### Project Context
- `.planning/PROJECT.md` — Single-user architecture, yfinance for market data, no database
- `.planning/STATE.md` — Current phase position

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `charts` object in `app/static/app.js` — already manages Chart.js instances with `.destroy()` pattern
- `get_fx_rate()` in `market_data.py` — already handles currency conversion
- `enrich_position()` — already fetches `perf_ytd`, `perf_30d`, `perf_90d` from yfinance
- `build_hermes_context()` — already builds structured JSON + plaintext, can be extended for benchmark data

### Established Patterns
- Environment variable config via `os.getenv` with defaults
- JSON file storage pattern (health alerts use env-configurable thresholds)
- Thread-safe FX cache with `threading.RLock`
- Snapshot on refresh pattern: each manual portfolio fetch is an opportunity to snapshot

### Integration Points
- `app/main.py` `get_portfolio()` endpoint — where benchmark data should be fetched and appended to response
- `app/context_builder.py` — add benchmark data to JSON context and plaintext export
- `app/static/app.js` `renderCharts()` — add benchmark chart alongside existing `etfStock`, `topWeight`, `sector`
- `app/static/index.html` — add canvas element for benchmark chart
- `data_dir` for snapshots — consider `/data/snapshots` (Docker volume mount point)

</code_context>

<specifics>
## Specific Ideas

- User pulls portfolio infrequently ("I don't buy every day") — snapshots accumulate slowly over weeks/months
- User trusts planner to pick sensible defaults — recommended options were consistently chosen
- User prefers indexed overlay to normalized scale — indexed shows actual relative performance

</specifics>

<deferred>
## Deferred Ideas

### MSCI World Benchmark
Could be added as a second benchmark line in a future phase. Not in scope for TRACK-01.

### Benchmark Data Caching
Benchmark data (^GSPC) is fetched fresh each time. Could cache to file in future to avoid yfinance rate limits during chart rendering. Not planned now.

### Auto-cleanup of Old Snapshots
No automatic cleanup. User manages manually. Could add `SNAPSHOT_RETENTION_DAYS` env in future phase.

### Multi-benchmark Overlay
Currently only S&P 500. Could show multiple benchmarks in one chart in future phase.

</deferred>

---

*Phase: 04-benchmark-tracking*
*Context gathered: 2026-04-23*
