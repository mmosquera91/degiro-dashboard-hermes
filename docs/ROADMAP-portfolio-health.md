# Roadmap — Portfolio Health & "Mostly Buy" Functionality

*Drafted 2026-05-30. Status: proposal backlog, not yet planned into phases.*

## Mission lens

Brokr serves a **long-term portfolio owner practicing "mostly buy, rarely sell."** The
goal of every item here is to advance one of two things:

1. **Direct new cash well** — make buying decisions easier and better (the "mostly buy" loop).
2. **Keep the portfolio healthy over years** — surface slow-moving risks before they compound.

The mission is already encoded in the export prompt (`app/context_builder.py:95` —
*"Do not recommend selling. Strategy is buy-and-hold."*). These features close the gap
between that stated mission and what the tool can currently *do*.

## Three structural gaps this roadmap addresses

| Gap | Where it shows in code | Consequence |
|-----|------------------------|-------------|
| Buy engine only ranks **owned** positions | `scoring.py:compute_scores`, `get_top_candidates` | Can't suggest new holdings for diversification — only top-ups |
| Drift is **detected** but never **actioned** | `health_checks.py:_check_rebalancing` | "You're 8pp over on ETFs" never becomes "buy here next" |
| "Over the years" is barely modeled | `_check_drawdown` is a weak YTD proxy | No real drawdown, no income, no personal return, no projection |

---

## Committed near-term track (selected)

### A. Cash-flow rebalancing planner — *flagship*
**"Where should my next €X go?"** Input a contribution amount; output a buy-only
allocation across holdings (and, with B, watchlist candidates) that maximally corrects
allocation / sector / concentration drift. **Never suggests selling** — it rebalances
purely by directing new cash. This is the literal embodiment of the mission.

- Builds on: drift math in `health_checks.py:_check_rebalancing`, `buy_priority_score`.
- Output: ordered buy list with amounts + the drift each buy corrects.
- New surface: input control + result panel; extend `/api/*` and the Hermes export.

### B. Watchlist / candidate universe
Track tickers **not yet owned**. Enrichment and scoring already run per-symbol — extend
them to a watchlist pool so buy candidates can include *new* positions, not just top-ups.
Turns Brokr from "top up what you have" into "grow the portfolio deliberately."

- Builds on: `market_data.py` enrichment, `scoring.py` pools (ETF / STOCK).
- Pairs tightly with A — A is far stronger when it can point cash at new holdings.
- Needs: persistent watchlist store (JSON, mirroring snapshot/override pattern).

### C. Dividend & income tracking
For buy-and-hold, reinvested dividends are most of the long-run return — and nothing
tracks them today. Add per-position yield, forward annual income estimate, a dividend
calendar, and trailing income received.

- Builds on: yfinance dividend history / `dividendYield` (already a dependency).
- Output: income KPIs, calendar, per-position yield column; add to Hermes context.

### D. ETF overlap / look-through diversification
The silent killer of buy-and-hold is redundant funds (e.g. S&P 500 + MSCI World ≈ 60%
overlapping names). Add a health check that flags overlap and shows *true* underlying
exposure rather than fund-level allocation.

- Builds on: `health_checks.py` alert pattern; needs an ETF-holdings data source.
- Risk/unknown: holdings data is the hardest sourcing problem in this roadmap — spike first.

---

## Backlog (proposed, not selected)

### E. Real drawdown & volatility from snapshots
Daily `portfolio_data` is already persisted (`data/snapshots/`). Replace the YTD-proxy
drawdown (`_check_drawdown`) with true peak-to-trough drawdown, max drawdown, and
volatility — proper long-term risk telemetry from data we already have.

### F. Long-term projection / goal trajectory
"At your contribution rate and historical return, here's your 10/20-year path." The
forward-looking view a long-term owner actually wants. Depends on H (XIRR) for a
credible return input.

### G. Scheduled digest
Periodic email/push: "cash idle N days — deploy it," "position X crossed 20%,"
"dividend received." Fits an investor who checks in rarely.
- **Constraint:** the single-use DeGiro token (`degiro_client.py`, by design) means a
  scheduled job runs on cached / price-only data unless the user re-syncs. Digest must be
  honest about freshness, or be limited to yfinance-derived signals.

### H. Personal money-weighted return (XIRR)
Benchmark uses TWR (`snapshots.py`), which is correct for comparing-vs-index but hides
*the investor's own* result across real contributions. Add XIRR over actual cash flows to
answer "how am I really doing?" Feeds F.

---

## Suggested sequencing

```
B (watchlist) ──┐
                ├──► A (cash-flow rebalancer)   ← flagship, most mission value
C (dividends) ──┘        │
                         ▼
D (ETF overlap) ── independent; spike data source first
                         │
E, H ── cheap wins on existing snapshot data ── feed ──► F (projection)
                         │
                         ▼
                    G (digest) ── last; depends on freshness story
```

**Rationale:** B unblocks A's full value. C is self-contained and high-compounding-value.
D is high-value but carries the only hard data-sourcing unknown, so spike it before
committing. E/H are cheap because the snapshot history already exists. F and G build on
the rest.

## Open questions to resolve in per-feature design

- **A:** whole-share buying (you can't buy 0.37 of a non-fractional share) — integer
  optimization or accept fractional/notional output?
- **B:** how does a user add to the watchlist — paste ISIN/ticker, and how is it persisted?
- **C:** show gross or net-of-withholding-tax yield? (DeGiro investors face varying treaty rates.)
- **D:** which ETF-holdings source is reliable and free enough for self-hosted use?
- **Cross-cutting:** every feature that adds data should also extend the Hermes export so
  the AI agent reasons with it — the export is the product's reasoning surface.
