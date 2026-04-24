# Feature Research

**Domain:** Portfolio analytics dashboard (DeGiro + yfinance enrichment)
**Researched:** 2026-04-24
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Per-stock RSI | Standard market data for any stock/ETF position | LOW | Computed from yfinance 1y history; None = "-", 30+ = oversold |
| Per-stock Weight (% of portfolio) | Users need to know relative importance of each position | LOW | Computed from EUR value / total portfolio value; None = "-" |
| Per-stock Momentum Score | Key signal for buy/sell decisions | LOW | Weighted 30d(20%) + 90d(30%) + YTD(50%); None = "-" when no price history |
| Per-stock Buy Priority Score | Actionable ranking — what to buy next | MEDIUM | Composite of value_score + distance + RSI + weight; None = "-" when score can't be computed |
| Sector Allocation Chart | Standard portfolio visualization | LOW | Doughnut chart; requires `sector_breakdown` dict with percentage values; empty dict = no chart rendered |
| Benchmark Comparison Chart | Portfolio vs S&P 500 performance | MEDIUM | Line chart indexed to 100; requires 2+ snapshots; single snapshot = comparison table fallback |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Health Alerts | Proactive risk signals (concentration, sector drift, drawdown) | MEDIUM | Already shipped; v1.1 fixes the underlying data pipeline |
| Buy Radar | Top 3 ETF/Stock candidates with reason strings | LOW | Uses buy_priority_score ranking; empty = "No candidates available" |
| Attribution Analysis | Which positions drove outperformance vs benchmark | MEDIUM | Already shipped; requires snapshots to compute |
| Hermes Context API | Ready-to-consume format for external AI agent | LOW | Plaintext and JSON; already shipped |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time price streaming | "Stock prices change — why not live?" | yfinance polling sufficient for a daily check; adds WebSocket complexity for no practical benefit | 5-minute TTL cache with manual refresh |
| Multiple brokers | "What about Interactive Brokers?" | DeGiro-only keeps scope manageable; session management for multiple APIs is error-prone | Focus on DeGiro depth |
| Multi-user / shared accounts | "My spouse also uses this" | Single-user design is explicit; auth layer would need major rework | Keep single-user |
| Database for historical tracking | "I want to query my history" | SQLite adds complexity; snapshots on disk already give historical tracking | Snapshots already provide this |

## Feature Dependencies

```
DeGiro fetch_raw_portfolio()
    └── enrich_positions() — yfinance data (prices, RSI, sector, 52w range)
           └── compute_portfolio_weights() — weight per position (EUR-based)
                  └── compute_scores() — momentum_score, value_score, buy_priority_score
                          └── _build_portfolio_summary() — assembles full response
                                  └── save_snapshot() — persists to disk

/api/benchmark
    └── load_snapshots() — reads from disk
            └── fetch_benchmark_series() — fetches S&P 500 data from yfinance
                    └── compute_attribution() — relative vs absolute contribution

API response feeds frontend:
    positions[].weight → "weight" column in positions table
    positions[].rsi → "rsi" column in positions table
    positions[].momentum_score → "momentum" column in positions table
    positions[].buy_priority_score → "buy priority" column in positions table
    portfolioData.sector_breakdown → sector doughnut chart
    benchmarkData.snapshots → benchmark line chart (needs 2+ snapshots)
```

### Dependency Notes

- **enrich_positions requires yfinance:** If yfinance fails for a ticker (rate limit, invalid symbol, network timeout), the position's RSI, momentum_score, and buy_priority_score all remain None → displayed as "-"
- **compute_portfolio_weights requires enrich_positions:** weight is based on `current_value_eur` which only exists after FX conversion in enrichment
- **compute_scores requires compute_portfolio_weights:** buy_priority_score normalization uses weight values; score chain breaks if weight is None
- **Sector chart requires sector field:** If yfinance returns no sector info for a position, it goes to "Unknown" bucket; all positions with no sector info result in 100% "Unknown" → chart renders but is meaningless
- **Benchmark chart requires snapshots:** Chart only renders when 2+ snapshots exist; with 1 snapshot, falls back to comparison table

## MVP Definition

### Launch With (v1.0 - Already Shipped)

- [x] DeGiro auth (intAccount + JSESSIONID)
- [x] Raw portfolio fetch
- [x] yfinance enrichment (prices, RSI, 52w range)
- [x] Scoring engine (momentum, buy priority)
- [x] Portfolio summary with sector breakdown
- [x] Benchmark comparison
- [x] Health alerts
- [x] Toast notifications + error states

### Add After Validation (v1.1 - Current Milestone)

- [x] Persist portfolio snapshots to disk (survives container restart)
- [ ] Fix blank per-stock metrics in dashboard (RSI, Weight, Momentum, Buy Priority show "-")
- [ ] Fix missing sector breakdown chart
- [ ] Fix missing benchmark comparison chart

### Future Consideration (v2+)

- [ ] Snapshot-based historical portfolio viewer
- [ ] Export/import snapshot data for backup
- [ ] Docker volume for snapshot directory persistence

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Persist snapshots to disk | HIGH — container restarts lose data | MEDIUM — disk I/O, path management | P1 |
| Fix blank RSI/Weight/Momentum/Buy Priority | HIGH — core metrics invisible | MEDIUM — depends on full enrichment pipeline | P1 |
| Fix sector breakdown chart | MEDIUM — chart missing | LOW — sector_breakdown already computed | P1 |
| Fix benchmark comparison chart | MEDIUM — chart missing | LOW — snapshots already saved | P1 |

**Priority key:**
- P1: Must have for v1.1 completion
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Competitor Feature Analysis

| Feature | Personal Capital | Morningstar | Our Approach |
|---------|-----------------|-------------|--------------|
| Per-stock RSI | Yes — tooltip on chart | Yes — on stock detail page | Present in detailed row view |
| Portfolio weight | Yes — pie chart hover | Yes — allocation table | Visible in positions table column |
| Momentum/Buy Priority | No — "smart score" proprietary | No | Unique to Brokr — the buy radar |
| Sector allocation chart | Yes — donut chart | Yes — pie chart | Donut chart in dashboard |
| Benchmark comparison | Yes — S&P 500 overlay | Yes — category benchmark | Line chart (needs 2+ snapshots) |
| Snapshot persistence | Yes — cloud-based | Yes — premium feature | Local disk snapshots (no DB needed) |

## Observed Behavior for "-" Display

When per-stock metrics show "-" in the positions table, the user is seeing one of these states:

| Field | "-" Means | How to Fix |
|-------|-----------|------------|
| RSI | yfinance enrichment failed or ticker not found | Check yfinance symbol resolution; rate limiting may cause partial failures |
| Weight | compute_portfolio_weights not called, or total_value is 0 | Ensure enrichment → scoring chain completed |
| Momentum Score | No price history for 30d/90d/YTD lookback | yfinance needs 1y history; ticker may be invalid |
| Buy Priority Score | score computation chain broke (usually upstream None) | Check that rsi and weight are populated first |

**Root cause pattern:** If yfinance returns None for a position's `sector`, `rsi`, or `current_price`, the downstream fields cascade to None through the scoring chain. The frontend correctly shows "-" but users experience this as "the dashboard is broken" when it affects most positions.

**The fix:** Ensure the full pipeline (enrich → compute_weights → compute_scores) runs before the response is returned, even for partial enrichment. The current code does this correctly in `/api/portfolio`, but the raw fallback in `/api/portfolio-raw` returns un-scored positions immediately while enrichment is still in progress.

## Sources

- Codebase analysis: `app/main.py`, `app/market_data.py`, `app/scoring.py`, `app/snapshots.py`, `app/static/app.js`
- Existing research: `.planning/research/FEATURES.md` (2026-04-23)

---
*Feature research for: Brokr portfolio dashboard v1.1 milestone — dashboard visibility and persistence fix*
*Researched: 2026-04-24*