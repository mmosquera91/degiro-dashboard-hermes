# Brokr — Portfolio Intelligence

[![CI](https://github.com/mmosquera91/degiro-dashboard-hermes/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/mmosquera91/degiro-dashboard-hermes/actions/workflows/docker-publish.yml)
[![Docker](https://img.shields.io/badge/ghcr-mm0squera91%2Fdegiro--dashboard--hermes-blue?logo=docker)](https://github.com/mmosquera91/degiro-dashboard-hermes/pkgs/container/degiro-dashboard-hermes)
[![Python](https://img.shields.io/badge/python-3.11-blue?logo=python)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-120%20passing-teal)](https://github.com/mmosquera91/degiro-dashboard-hermes)

Portfolio analytics dashboard for long-term DeGiro investors. Pulls your positions, enriches them with live market data, and generates structured context for AI-powered portfolio analysis.

---

## Quick Start

```bash
# 1. Download
curl -O https://raw.githubusercontent.com/mmosquera91/degiro-dashboard-hermes/master/docker-compose.yml
curl -O https://raw.githubusercontent.com/mmosquera91/degiro-dashboard-hermes/master/.env.example

# 2. Configure
cp .env.example .env
# → Edit .env: BROKR_AUTH_TOKEN, APP_PASSWORD, and SECRET_KEY are required
# → If using plain HTTP (most users): COOKIE_SECURE=false is already set — leave it

# 3. Run
docker compose up -d
```

Dashboard at **http://localhost:8000** — no build, no clone, just download and go.

To update: `docker compose pull && docker compose up -d`

---

## What Brokr Does

- **Portfolio** — fetches your DeGiro positions via browser session injection
- **Enrichment** — live prices, RSI, 52w range, P/E, multi-period performance (yfinance)
- **Scoring** — momentum, value, and buy-priority scores with quality gates
- **Benchmark** — portfolio vs S&P 500 with historical snapshots
- **AI Export** — structured JSON + plaintext context block for AI agents

Brokr provides **data and metrics only**. It doesn't make buy/sell decisions — it gives AI agents clean, structured data to reason with.

---

## Stack

`Python 3.11` `FastAPI` `degiro-connector 3.0.35` `yfinance` `Chart.js v4` `Vanilla JS`

### Auth

Dual-layer: **browser session cookie** (login page) → **API bearer token** (JS calls).  
Credentials are never stored on disk — DeGiro session held in memory with 30-min TTL.

### Data Flow

```
DeGiro → positions → yfinance enrichment → scoring engine → AI context
```

---

## API

### Auth & Session

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/session` | Inject DeGiro JSESSIONID. Body: `{session_id, int_account?}` |
| `DELETE` | `/api/session` | Clear session and cache |

### Portfolio

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/portfolio` | Full portfolio with enrichment (~9s). Cached if stale |
| `GET` | `/api/portfolio-raw` | Raw DeGiro positions (~2-3s) |
| `POST` | `/api/refresh-prices` | Force re-enrichment |
| `GET` | `/api/enrichment-status` | Poll progress: `{enriching, last_enriched_at}` |

### Analytics

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/hermes-context` | Structured JSON + plaintext for AI analysis |
| `GET` | `/api/benchmark` | Portfolio vs S&P 500 |
| `GET` | `/api/snapshots` | Historical snapshots |
| `POST` | `/api/snapshots/save` | Save current state |
| `DELETE` | `/api/snapshots/{date}` | Delete snapshot |

### Admin & System

| Method | Path | Description |
|--------|------|-------------|
| `DELETE` | `/api/admin/symbol-cache` | Clear symbol cache |
| `POST` | `/api/admin/reload-overrides` | Reload symbol overrides |
| `GET` | `/health` | Health check |
| `GET` | `/api/session-token` | Bootstrap endpoint for JS auth |

---

## Hermes Integration

Click **Export for Hermes** in the dashboard or hit `GET /api/hermes-context`. The context block includes:

- Portfolio summary (total value, P&L, ETF/stock allocation vs 70/30 targets, cash)
- Positions ranked by momentum score (weakest first)
- Per-position: RSI, 52w range, P/E, 30d/90d/YTD performance, scores
- Top 3 buy candidates (ETFs and stocks)
- Benchmark vs S&P 500 with historical comparison
- Attribution breakdown per position

The AI agent handles news, sentiment, macro, and buy/sell recommendations — Brokr just provides the data.

---

## DeGiro Session Injection

DeGiro blocks automated login. The recommended flow:

1. Log into trader.degiro.nl in your browser
2. DevTools → Application → Cookies → `trader.degiro.nl` → copy `JSESSIONID`
3. In Brokr dashboard → **Browser Session** tab → paste JSESSIONID + intAccount

Credentials are discarded immediately — only the session cookie is used.

---

## Environment Variables

| Variable | Default | Required |
|----------|---------|----------|
| `BROKR_AUTH_TOKEN` | — | **Yes** |
| `APP_PASSWORD` | — | **Yes** |
| `SECRET_KEY` | — | **Yes** |
| `COOKIE_SECURE` | `false` | No — set `true` for HTTPS |
| `TARGET_ETF_PCT` | `70` | No |
| `TARGET_STOCK_PCT` | `30` | No |

---

## Development

```bash
git clone git@github.com:mmosquera91/degiro-dashboard-hermes.git brokr && cd brokr
cp .env.example .env
docker compose -f docker-compose.dev.yml up -d --build
```

### Running Tests

Tests run inside Docker (host lacks `degiro-connector`). 120 passing as of Sprint 6.

```bash
docker cp tests/ brokr:/app/tests/
docker exec brokr pip install pytest pytest-asyncio httpx -q
docker exec brokr bash -c "cd /app && python -m pytest tests/ -q"
```

### Useful Commands

```bash
docker compose -f docker-compose.dev.yml up -d --build   # rebuild after changes
docker logs brokr --tail 50 -f                            # view logs
docker exec brokr id                                       # verify uid=1000(appuser)
```

### Project Structure

```
brokr/
├── app/
│   ├── main.py              # FastAPI app, routes, auth middleware
│   ├── degiro_client.py     # DeGiro API + session management
│   ├── market_data.py       # yfinance enrichment, FX, RSI, performance
│   ├── scoring.py           # Momentum, value, buy priority scoring
│   ├── context_builder.py   # AI context JSON + plaintext
│   ├── snapshots.py         # Historical P&L + benchmark
│   ├── health_checks.py     # Health alerts
│   ├── rate_limiter.py      # IP-based rate limiting
│   ├── schemas.py           # Pydantic v2 models
│   └── static/              # Vanilla JS, Chart.js, dark theme
├── tests/                   # Pytest suite (120 tests)
├── Dockerfile               # python:3.11-slim, appuser (UID 1000)
├── docker-compose.yml       # Production (pre-built image)
├── docker-compose.dev.yml   # Development (build from source)
├── DECISIONS.md             # Architecture decisions
└── agents.md                # Context for AI coding agents
```

---

## Security

- No credential storage — username/password discarded after session creation
- Session in memory only, lost on container restart
- Stateless — no database, no persistent auth
- Bearer token on all `/api/*` endpoints
- Rate limiting: 5 attempts/IP/60s on login
- Signed cookies: HttpOnly, SameSite=Lax, conditional Secure
- SRI hashes on CDN resources

---

## Sprint History

**Sprint 1-2** — Critical fixes (zero-division, IndexError, race conditions) + security hardening (bearer auth, rate limiting, signed cookies, XSS, SRI).

**Sprint 3-4** — 101-unit test suite + architecture (Pydantic v2, pinned deps, session injection).

**Sprint 5** — Dashboard UX: live KPI cards, benchmark Y-axis fix, mobile table with sticky columns.

**Sprint 6** — Bug squash (7 HIGH bugs), enrichment parallelized (13.2s → 9.1s), Docker volume → bind mount, scoring overhaul with quality gates, Docker image on GHCR.

---

*Built for long-term buy-and-hold investors. Not financial advice.*
