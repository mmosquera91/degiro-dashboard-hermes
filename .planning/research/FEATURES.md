# Features

**Research Date:** 2026-04-23
**Project:** Brokr — Portfolio analytics dashboard for DeGiro

## Table Stakes

Features users expect and will leave if missing.

### Authentication
- **DeGiro credential login** — Username/password + OTP for DeGiro account access
- **Session persistence** — Stay logged in across browser refreshes (30-min TTL with activity reset)
- **Logout** — Clear session and return to login screen

### Portfolio Display
- **Position list** — All current holdings with name, quantity, value
- **Portfolio summary** — Total value, day change, overall change
- **Sector breakdown** — Pie/doughnut chart showing allocation by sector
- **Performance metrics** — 30-day, 90-day, YTD performance for portfolio and individual positions
- **Price enrichment** — Current price, 52-week high/low, day change for each position

### Market Data
- **Live prices** — Current price from Yahoo Finance
- **RSI indicator** — 14-day relative strength index for each position
- **FX conversion** — Multi-currency position conversion to EUR (base currency)
- **52-week range** — Position's current price relative to 52-week high/low

### Scoring & Ranking
- **Momentum score** — Based on recent price performance
- **Value score** — Based on valuation metrics (RSI, 52w position)
- **Buy priority ranking** — Combined score ranking all positions for potential buying

## Differentiators

Features that provide competitive advantage beyond minimum viable.

### Health Indicators
- **Concentration risk** — Alert when single position exceeds X% of portfolio
- **Sector weighting alert** — Alert when sector exceeds threshold
- **Drawdown alert** — Alert when portfolio drawdown exceeds threshold
- **Rebalancing signal** — Suggest when allocations drift too far from target

### Performance Tracking
- **Benchmark comparison** — S&P 500 / MSCI World performance overlay
- **Historical performance chart** — Portfolio value over time vs benchmark
- **Attribution analysis** — Which positions contributed most to gains/losses

### Hermes AI Integration
- **Context API endpoint** — `/api/hermes-context` returns JSON and plaintext portfolio summary
- **Consumable format** — Ready for AI agent to ingest without further processing

### Dashboard Polish
- **Toast notifications** — Non-blocking feedback replacing browser alerts
- **Better error states** — Graceful degradation when API calls fail
- **Responsive improvements** — Works on mobile and tablet viewports

## Anti-Features

Things to deliberately NOT build based on user scope.

- **Multi-user support** — Single user for now
- **Real-time price streaming** — yfinance polling is sufficient
- **Database/persistent storage** — In-memory cache is acceptable
- **Mobile native app** — Web-only, responsive is sufficient
- **Brokerage trading** — Read-only analytics, no execution
- **Multiple broker integrations** — DeGiro only

## Dependencies

- DeGiro auth → requires intAccount + JSESSIONID (username/password login failed)
- Market data enrichment → requires yfinance (rate-limited, 0.25s between requests)
- Portfolio scoring → requires pandas/numpy for computation
- Hermes context → requires context_builder.py (already implemented)

---
*Synthesized from codebase and requirements analysis: 2026-04-23*