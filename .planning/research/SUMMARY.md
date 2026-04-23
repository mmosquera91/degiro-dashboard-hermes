# Research Summary

**Project:** Brokr — Portfolio analytics dashboard for DeGiro
**Synthesized:** 2026-04-23
**Source:** Codebase analysis + requirements extraction

## Key Findings

### Stack
- **Python 3.11 + FastAPI** — Already in production, working well
- **degiro-connector 3.0.35** — Only viable DeGiro integration (username/password login failed)
- **yfinance 0.2.51** — Sufficient for market data, rate-limited (0.25s delay)
- **Vanilla JS + Chart.js** — No build step, keeps Docker image small

### Table Stakes
- DeGiro credential login (intAccount + JSESSIONID approach)
- Portfolio display with prices, performance, sector breakdown
- RSI indicators, 52-week range, FX conversion
- Scoring/ranking for buy priority
- Hermes context API endpoint

### Differentiators
- Health indicators (concentration risk, drawdown alerts, rebalancing signals)
- Benchmark comparison (S&P 500 / MSCI World)
- Historical performance tracking
- Dashboard polish (toasts, error states, responsive)

### Watch Out For

**Critical (must fix in Phase 1):**
1. C-01: Debug endpoint exposes passwords in HTTP response
2. C-02: Debug endpoint exposes DeGiro session IDs
3. C-03: No authentication on any API endpoint
4. C-04: Plaintext HTTP transmits credentials

**Performance (Phase 2):**
- Blocking I/O in yfinance enrichment (event loop responsiveness)
- Thread safety issues in session/FX cache
- Rate limiting on yfinance

**Architecture:**
- Single-process monolith is working, don't over-engineer
- No database needed for single-user app
- Two-phase data loading is good pattern (raw fast, enrichment slow)

## Phase Recommendations

1. **Phase 1: Security Hardening** — Fix credential exposure, add API auth, remove debug scripts
2. **Phase 2: Performance** — Thread pool for yfinance, fix thread safety
3. **Phase 3: Health Indicators** — Concentration risk, sector alerts, rebalancing signals
4. **Phase 4: Benchmark Tracking** — S&P 500 comparison, historical performance
5. **Phase 5: Dashboard Polish** — Toasts, error states, responsive improvements

---
*Synthesized from .planning/codebase/ analysis: 2026-04-23*