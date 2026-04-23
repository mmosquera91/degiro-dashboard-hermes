# Brokr

## What This Is

A portfolio analytics dashboard for DeGiro stocks/ETFs accounts. Shows portfolio metrics, health indicators, and performance tracking in a browser-based dashboard. Also provides a structured API endpoint that produces ready-to-consume portfolio context for an external AI agent (Hermes) running on the same host.

## Core Value

Reliable portfolio health visibility — seeing risk and performance signals at a glance so you can make informed decisions without manually crunching numbers.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. Inferred from existing codebase. -->

- ✓ DeGiro authentication via intAccount + JSESSIONID — existing
- ✓ Raw portfolio fetch from DeGiro API — existing
- ✓ Market data enrichment via yfinance (prices, 52w range, RSI) — existing
- ✓ Scoring engine (momentum, value, buy priority) — existing
- ✓ Portfolio summary with sector breakdown, top winners/losers — existing
- ✓ Hermes context builder (JSON + plaintext export) — existing
- ✓ Hermes context API endpoint (`/api/hermes-context`) — existing
- ✓ Dashboard with Chart.js visualizations (allocation, performance) — existing
- ✓ Docker deployment with healthcheck — existing
- ✓ FX rate conversion for multi-currency positions — existing
- ✓ SEC-01: Debug endpoint removed (`/api/debug-login`)
- ✓ SEC-02: Debug scripts excluded from Docker image (`scripts/`, `app/debug_*.py`, `app/test_*.py`)
- ✓ SEC-03: API authentication on all `/api/*` routes via `BROKR_AUTH_TOKEN` bearer token with hmac.compare_digest
- ✓ SEC-04: FastAPI binds to `127.0.0.1` by default (network exposure prevented)
- ✓ SEC-05: Debug scripts excluded from Docker build context
- ✓ SEC-06: Security headers (X-Content-Type-Options, X-Frame-Options, HSTS, CSP) + CORS middleware on all responses

### Active

<!-- Current scope. Building toward these. -->

- [ ] Fix blocking I/O — run yfinance enrichment in thread pool so the event loop stays responsive
- [ ] Health indicators — concentration risk, sector weightings, drawdown alerts, rebalancing signals
- [ ] Performance tracking — benchmark comparison (e.g., S&P 500 / MSCI World), performance over time
- [ ] Dashboard polish — toast notifications replacing alerts, better error states, responsive improvements
- [ ] Fix thread safety issues in session and FX cache management
- [ ] Add automated tests for scoring, market data, and portfolio parsing

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Multi-user / multi-account support — single user for now, architecture can evolve later
- Real-time price streaming — yfinance polling is sufficient; no WebSocket feed needed
- Database / persistent storage — in-memory cache is fine for single-user dashboard use
- Mobile app — web-only, responsive is enough
- Hermes-side AI logic — Hermes handles all news and analysis independently; Brokr only provides portfolio data
- Brokerage trading / order placement — read-only analytics, no execution capability
- Additional broker integrations — DeGiro only for now

## Context

**Existing codebase:** FastAPI monolith serving both API and static frontend. Python 3.11, vanilla JS frontend with Chart.js, Docker deployment. No database — all state in memory with TTL caches.

**DeGiro integration:** Working but fragile. Authentication requires user to manually extract intAccount and JSESSIONID from their browser. Previous attempts at username/password/TOTP login failed with degiro-connector 3.0.35.

**Hermes integration:** A separate AI agent on the same Ubuntu host that fetches news and performs analysis. Brokr provides portfolio context via an HTTP API endpoint. Hermes calls Brokr, not the other way around.

**Known issues:** The concerns audit (`.planning/codebase/CONCERNS.md`) documents critical security vulnerabilities (credential exposure, no auth, plaintext HTTP), blocking I/O in the enrichment layer, and missing test coverage. These need addressing before the app can be safely shared.

**Tech constraints:** No build step for frontend (vanilla JS, CDN dependencies). No database. Docker-first deployment.

## Constraints

- **Tech Stack**: Python 3.11 + FastAPI backend, vanilla JS frontend (no React/Vue/Svelte) — keep it simple, no framework migration
- **Broker**: DeGiro only via degiro-connector 3.0.35 — no other broker SDKs
- **Market Data**: yfinance only — no paid data providers
- **Deployment**: Docker on Ubuntu — same host as Hermes
- **No Database**: All state in memory — acceptable for single-user use case

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project lifecycle. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| DeGiro auth via intAccount + JSESSIONID (not username/password) | degiro-connector login with credentials failed; session token approach works reliably | ✓ Good |
| Vanilla JS frontend (no framework) | Single-page dashboard, no build step needed, keeps Docker image small | — Pending |
| In-memory session cache (no database) | Single-user app, no persistence needed, simplifies deployment | — Pending |
| Hermes integration via REST API | Hermes calls Brokr's endpoint; no push/webhook from Brokr | ✓ Good |
| Fix security issues before adding features | Critical credential exposure and no auth make the app unsafe to share | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-23 after phase 01 completion (security hardening)*
