# Architecture

**Research Date:** 2026-04-23
**Project:** Brokr — Portfolio analytics dashboard for DeGiro

## Component Boundaries

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI (app/main.py)                    │
│  Routes: /api/auth, /api/portfolio, /api/hermes-context, etc │
│  Session cache (thread-safe in-memory dict)                 │
└──────────┬──────────┬──────────┬──────────────┬────────────┘
           │          │          │              │
           v          v          v              v
   degiro_client  market_data   scoring   context_builder
   (broker API)  (yfinance)    (compute)  (Hermes export)
           │          │          │              │
           v          v          v              v
   DeGiro API   Yahoo Finance  numpy/     JSON/text output
   (trader.     (finance.      pandas     to Hermes
    degiro.nl)   yahoo.com)
```

## Data Flow

1. **User authenticates** → `POST /api/auth` → degiro_client.authenticate() → session stored
2. **Portfolio fetch** → `GET /api/portfolio` → degiro_client.fetch_portfolio() → raw positions
3. **Market enrichment** → market_data.enrich_positions() → yfinance calls for each position (blocking!)
4. **Scoring** → scoring.compute_scores() → numpy calculations for momentum/value scores
5. **Response** → FastAPI serializes enriched portfolio → JSON response to frontend

## Key Architectural Decisions

| Decision | Rationale | Status |
|----------|-----------|--------|
| Single-process monolith | Simple deployment, no network calls between layers | Working |
| No database | Single-user, in-memory cache with TTL is sufficient | Working |
| Vanilla JS frontend | No build step, CDN dependencies, keeps image small | Working |
| Two-phase loading | Raw first (fast), enrichment second (slow but non-blocking) | Working but slow |
| Session in-memory | No auth tokens stored on client, 30-min TTL | Working |
| Hermes pull model | Hermes calls Brokr endpoint, Brokr doesn't push | Working |

## Build Order

Dependencies between components (what can be built in what order):

1. **app/main.py foundation** — Routes, session cache, basic error handling
2. **app/degiro_client.py** — Authentication and portfolio fetching
3. **app/market_data.py** — yfinance enrichment (depends on degiro_client output)
4. **app/scoring.py** — Score computation (depends on market_data output)
5. **app/context_builder.py** — Hermes export (depends on scoring output)
6. **Frontend** — Dashboard UI (depends on all backend endpoints)

## Suggested Phase Structure

Based on dependencies and risk profile:

**Phase 1: Security Hardening** — Fix critical vulnerabilities before production exposure
**Phase 2: Performance** — Fix blocking I/O in enrichment layer
**Phase 3: Health Indicators** — Concentration risk, sector alerts, rebalancing signals
**Phase 4: Benchmark Tracking** — S&P 500 comparison, historical performance
**Phase 5: Dashboard Polish** — Toasts, error states, responsive improvements

---
*Synthesized from codebase analysis: 2026-04-23*