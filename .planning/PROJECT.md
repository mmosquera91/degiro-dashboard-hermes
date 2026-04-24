# Brokr

## What This Is

A portfolio analytics dashboard for DeGiro stocks/ETFs accounts. Shows portfolio metrics, health indicators, and performance tracking in a browser-based dashboard. Also provides a structured API endpoint that produces ready-to-consume portfolio context for an external AI agent (Hermes) running on the same host.

## Core Value

Reliable portfolio health visibility — seeing risk and performance signals at a glance so you can make informed decisions without manually crunching numbers.

## Requirements

### Validated

<!-- Confirmed valuable — shipped in v1.0. -->

- ✓ DeGiro authentication via intAccount + JSESSIONID — v1.0
- ✓ Raw portfolio fetch from DeGiro API — v1.0
- ✓ Market data enrichment via yfinance (prices, 52w range, RSI) — v1.0
- ✓ Scoring engine (momentum, value, buy priority) — v1.0
- ✓ Portfolio summary with sector breakdown, top winners/losers — v1.0
- ✓ Hermes context builder (JSON + plaintext export) — v1.0
- ✓ Hermes context API endpoint (`/api/hermes-context`) — v1.0
- ✓ Dashboard with Chart.js visualizations (allocation, performance) — v1.0
- ✓ Docker deployment with healthcheck — v1.0
- ✓ FX rate conversion for multi-currency positions — v1.0
- ✓ API authentication on all `/api/*` routes via `BROKR_AUTH_TOKEN` — v1.0
- ✓ FastAPI binds to `127.0.0.1` by default — v1.0
- ✓ Security headers (X-Content-Type-Options, X-Frame-Options, HSTS, CSP) + CORS — v1.0
- ✓ Async yfinance enrichment (thread pool) — v1.0
- ✓ Thread-safe session and FX cache — v1.0
- ✓ Health alerts (concentration, sector, drawdown, rebalancing) — v1.0
- ✓ Benchmark comparison (S&P 500) + historical performance chart — v1.0
- ✓ Attribution analysis — v1.0
- ✓ Toast notification system — v1.0
- ✓ Error states with stale indicators — v1.0
- ✓ Responsive mobile/tablet CSS — v1.0
- ✓ Automated tests (scoring, market_data, degiro_client) — v1.0

### Active

<!-- Current focus — not yet shipped. v1.1 -->

- [ ] Persist portfolio snapshots to disk for container restart survival
- [ ] Fix blank per-stock metrics in dashboard (RSI, Weight, Momentum, Buy Priority show "-")
- [ ] Fix missing sector breakdown chart
- [ ] Fix missing benchmark comparison chart

### Out of Scope

<!-- Explicit boundaries. -->

| Feature | Reason |
|---------|--------|
| Multi-user / multi-account support | Single user for now |
| Real-time price streaming | yfinance polling sufficient |
| Database / persistent storage | In-memory cache acceptable for single-user |
| Mobile app | Web-only, responsive sufficient |
| Hermes-side AI logic | Brokr only provides portfolio data |
| Brokerage trading | Read-only analytics |
| Additional broker integrations | DeGiro only |

## Context

**Tech Stack:** Python 3.11 + FastAPI backend, vanilla JS frontend (Chart.js), Docker deployment. No database — in-memory state with TTL caches.

**DeGiro Integration:** Authentication requires manual extraction of intAccount + JSESSIONID from browser. Session expires ~30 min causing 500 errors on `/api/portfolio`.

**Hermes Integration:** Separate AI agent on same Ubuntu host fetches news and performs analysis. Brokr provides portfolio context via HTTP API.

**v1.0 Shipped:** 3262 LOC Python, 89 commits, 17 plans across 6 phases.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| DeGiro auth via intAccount + JSESSIONID | degiro-connector login with credentials failed; session token works | ✓ Good |
| Vanilla JS frontend (no framework) | No build step needed, Docker image stays small | ✓ Good |
| In-memory session cache (no database) | Single-user app, no persistence needed | ✓ Good |
| Hermes integration via REST API | Hermes calls Brokr, not push | ✓ Good |
| Fix security before features | Credential exposure and no auth unsafe to share | ✓ Good |
| Async yfinance via thread pool | Event loop was blocking on network I/O | ✓ Good |

## Current Milestone: v1.1 Dashboard & Persistence Fix

**Goal:** Fix dashboard data visibility and persistent portfolio caching — make per-stock metrics visible, sector/benchmark charts render, and portfolio data survives container restarts.

**Target features:**
- Persist portfolio snapshots to disk so data survives container restarts
- Fix blank per-stock metrics in dashboard (RSI, Weight, Momentum, Buy Priority show "-")
- Fix missing sector breakdown chart
- Fix missing benchmark comparison chart

## Evolution

This document evolves at phase transitions and milestone boundaries.

---
*Last updated: 2026-04-24 — v1.1 milestone started*
