---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Dashboard & Persistence Fix
status: ready_to_plan
last_updated: "2026-04-26"
progress:
  total_phases: 4
  completed_phases: 2
  total_plans: 8
  completed_plans: 7
  percent: 50
---

# State

## Project Reference

**Brokr** — Portfolio analytics dashboard for DeGiro stocks/ETFs.

**Core Value:** Reliable portfolio health visibility — seeing risk and performance signals at a glance.

**Current Focus:** Phase --phase — 08

## Milestone v1.1 Goals

- Persist portfolio snapshots to disk for container restart survival
- Fix blank per-stock metrics in dashboard (RSI, Weight, Momentum, Buy Priority show "-")
- Fix missing sector breakdown chart
- Fix missing benchmark comparison chart

## Phase Progress

| Phase | Name | Plans | Status |
|-------|------|-------|--------|
| 7 | Snapshot Format Extension | 0 | Not started |
| 8 | Startup Portfolio Restoration | 0 | Not started |
| 9 | Data Enrichment & Scoring Fixes | 0 | Not started |
| 10 | Frontend Dashboard Verification | 0 | Not started |

## Problems to Diagnose

- Per-stock data shows "-" — likely yfinance enrichment failing or scoring not running
- Sector breakdown chart missing — sector data not populated in positions
- Benchmark comparison chart missing — benchmark series not being fetched/rendered
- Portfolio snapshots exist but per-stock metrics remain blank after restart

## Accumulated Context

### Architecture Decisions

- Snapshot format extends to store full `portfolio_data` dict
- `load_latest_snapshot()` added to restore portfolio on startup
- Atomic rename for snapshot writes (temp file + rename)
- Docker volume mount `./snapshots:/data/snapshots` for persistence

### Dependencies

- Phase 7 before Phase 8 (snapshots must have portfolio data before restoration)
- Phase 9 can parallelize with Phase 7-8 but must complete before Phase 10
- Phase 10 depends on Phase 8 (portfolio must be in session)

## Next Milestone Goals (Pending)

- DeGiro session auto-reauth
- Dynamic FX rate refresh
- Historical portfolio snapshots (trend analysis)
- Performance history export

## Quick Tasks Completed

- **fix symbol vwdId fallback to yfinance (2026-04-26):** Removed `vwdId` and `vwd_id` from symbol fallback chain in `fetch_portfolio()`. vwdId is a Van der Moolen internal numeric ID (e.g. "72095021"), not a market ticker — using it as a yfinance symbol fallback caused symbol_cache.json poisoning and wasted 10 yfinance HTTP calls per leveraged product/turbo/warrant per enrichment run. `enrich_position()` already handles empty symbol with early return + warning log. `app/degiro_client.py` line 697.
- **fix _yf_rate_limited race condition (2026-04-24):** Added `_yf_rate_limited_until` with 60s cooldown. `enrich_positions()` now conditionally resets flag only after cooldown expires. `_resolve_yf_symbol()` sets 60s cooldown on 429 detection and checks expiry before skipping. Prevents premature retry after rate limit hit. Commit: 68279c0
- **fix 429 abort in _resolve_yf_symbol (2026-04-24):** Module-level `_yf_rate_limited` flag replaces broken string-based 429 detection. Loop was continuing suffixes because yfinance internally catches/re-raises 429 so str(e) doesn't contain "429". Flag is checked before each suffix and set on 429 detection. enrich_positions resets flag at start of each call. Commit: 98fa798
- **yfinance symbol resolution (2026-04-24):** _resolve_yf_symbol had a dead suffixes_to_try list that was never used - just returned symbol unchanged. European stocks need exchange suffixes for yfinance. Now actively tries each suffix and returns first with valid market price. Commit: ae7e392
- **portfolio enrichment error (2026-04-24):** Dashboard showed "Failed to fetch portfolio" after raw portfolio loaded — `compute_scores()` and `compute_health_alerts()` threw unhandled exceptions that propagated to the 500 error handler. Both are now wrapped in defensive try/except with warning-level logging. Commit: 28012c9. PR: [#1](https://github.com/mmosquera91/degiro-dashboard-hermes/pull/1).
- **enrich_positions async def fix (2026-04-24):** enrich_positions was declared `async def` but contained zero await expressions — asyncio.to_thread() received a coroutine object instead of a callable. Changed to `def` in app/market_data.py line 313. Commit: 0c43209.
- **yfinance rate limit back-off (2026-04-24):** Increase _YF_DELAY from 0.25s to 1.0s to avoid 429s on portfolios >5 positions. Detect 429/Too Many Requests in enrich_position and mark as rate_limited. Track _session_rate_limited in enrich_positions loop and short-circuit remaining positions. Commit: f2fef6a.
- **FX rate prefetch before enrichment loop (2026-04-24):** Pre-warm FX cache for all unique non-base currencies before the position enrichment loop begins. Eliminates interleaved yfinance FX HTTP requests during the loop. Commit: b7e9227.
- **fix Dockerfile ownership and /data/snapshots permissions (2026-04-24):** Move COPY start.py before USER appuser, copy to /app/start.py, create and chown /data/snapshots, update CMD to /app/start.py. Commit: d29863d.

- **rescore positions after snapshot restore (2026-04-26):** Added `compute_portfolio_weights()` and `compute_scores()` calls in `_restore_portfolio_from_snapshot()` after the `_sanitize_floats` loop. Fixes `None` weight/momentum_score/buy_priority_score when snapshot was saved during a rate-limited session. `app/main.py` line 244-249.
- **price-currency-guard (2026-04-26):** Added `_price_currency_safe` check in `enrich_position()`. Before calling `ticker.history()`, read `ticker.fast_info.currency` and compare to `position["currency"]`. Only update `current_price`/`current_value`/`unrealized_pl` when currencies match. On mismatch, log a warning and keep DeGiro's price — which is always in the correct currency. Fixes wrong P/L when yfinance resolves a USD ticker for a EUR position. `app/market_data.py` lines 361-413.
- **ETF sector/category fallback (2026-04-26):** `enrich_position()` now uses ETF-aware sector assignment. ETFs get `category` → `fundFamily` → `industry` as sector (yfinance "sector" is stock-only). Stocks unchanged: `sector` → `industry`. Fixes all ETFs showing "Unknown" in sector breakdown chart. `app/market_data.py` lines 343-356.

---

*Last updated: 2026-04-26 — quick task shipped*
