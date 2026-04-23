# Phase 04: Benchmark Tracking - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-23
**Phase:** 04-benchmark-tracking
**Areas discussed:** Benchmark selection, Snapshot storage, Attribution calc, Overlay chart

---

## Benchmark Selection

| Option | Description | Selected |
|--------|-------------|----------|
| S&P 500 only | Simple, proven, most referenced. Configurable ticker via env var. | ✓ |
| MSCI World only | Global exposure, more relevant for ETFs. Fetch ^MSCIWORLD. | |
| Both S&P 500 and MSCI World | Both tickers fetched, both shown in chart. More data, richer context. | |
| Let me decide | Ticker set via environment. Planner handles the fetch logic. | |

**User's choice:** S&P 500 only (recommended)
**Notes:** User accepted S&P 500 as default. Benchmark ticker configurable via env var.

---

## Snapshot Storage

| Option | Description | Selected |
|--------|-------------|----------|
| JSON file per day | Simple, works for single-user. App can be restarted without losing history. | |
| One file per day, auto-cleanup | Append only, no rotation. Manually delete old files or it grows forever. | |
| SQLite DB | Python's sqlite3 (stdlib). No external DB setup. Query-able. | |
| Store each time you refresh | Save portfolio snapshot each time you manually refresh. Builds chart over weeks/months of sporadic refreshes. | ✓ |
| No storage at all | Just compare current portfolio vs benchmark. No snapshot file. | |
| Store, auto-cleanup | Store last 30 days of snapshots. Auto-cleanup. | |

**User's choice:** Store each time you refresh (user noted: "I don't buy every day")
**Notes:** User pulls portfolio infrequently. Store snapshot each manual refresh so chart grows over weeks/months of sporadic pulls. User deferred to recommendation on storage approach.

---

## Attribution Calc

| Option | Description | Selected |
|--------|-------------|----------|
| Relative to benchmark | (position return − benchmark return) × weight × direction | |
| Absolute P&L only | position return × weight — pure cash impact | |
| Both | Both relative (benchmark-beating) and absolute (cash impact) metrics shown | ✓ |

**User's choice:** Both
**Notes:** User wants both metrics. Relative shows "did this beat the market?", absolute shows "how much did it move my portfolio?"

---

## Overlay Chart

| Option | Description | Selected |
|--------|-------------|----------|
| Indexed overlay | One line chart, two series: portfolio value and benchmark indexed to 100 at start. | ✓ |
| Normalized (0-100 scale) | Both series scaled 0-100 range to compare shapes regardless of absolute values. | |
| Separate panels | Two separate charts stacked vertically. Portfolio on top, benchmark below. | |

**User's choice:** Indexed overlay (recommended)
**Notes:** Indexed shows actual relative performance over time. Normalized is rejected in favor of indexed.

---

## Deferred Ideas

- **MSCI World Benchmark** — Could be added as second benchmark line in future phase
- **Benchmark Data Caching** — Fetch fresh each time; could cache in future to avoid yfinance rate limits
- **Auto-cleanup of Old Snapshots** — No automatic cleanup; user manages manually
- **Multi-benchmark Overlay** — Currently only S&P 500; could show multiple benchmarks in future
