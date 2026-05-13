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

## How the Numbers Work

Every metric on the dashboard is derived from two sources: **DeGiro** (your positions, buy prices, quantities) and **yfinance** (live prices, historical data, fundamentals). Here's how each one is calculated.

### Prices & Currency

All values are normalized to EUR.

**Current price** — fetched via `yf.download()` in batch (all symbols at once), then per-symbol `ticker.history("1y")` as fallback. Results are cached for 15 minutes.

**Position value (EUR)** — `current_price × quantity × fx_rate`. FX rates come from yfinance currency pairs (e.g. `EURUSD=X`) and are cached per session.

**P&L %** — `((current_price − avg_buy_in_local) / avg_buy_in_local) × 100`. The average buy price from DeGiro is in EUR, so for non-EUR positions it's converted to the position's currency before computing.

**GBp safety net** — yfinance returns LSE prices in pence. Brokr detects `currency=GBp` and divides by 100 before any calculation.

### Technical Indicators

All technical indicators come from 1 year of daily closing prices via `ticker.history(period="1y")`.

**RSI(14)** — Wilder's smoothing method:
1. Compute daily price changes
2. Separate into gains and losses
3. Initial SMA over 14 periods, then exponential smoothing: `avg_gain[i] = (avg_gain[i-1] × 13 + gain[i]) / 14`
4. `RS = avg_gain / avg_loss` → `RSI = 100 − 100/(1 + RS)`

If 1-year history has fewer than 14 data points, falls back to 3-month history.

**52-Week High / Low** — `max(close)` and `min(close)` from the 1-year history window.

**Distance from 52w High** — `((current_price − 52w_high) / 52w_high) × 100`. Negative = below the high. Displayed as an absolute percentage (e.g. "12% below").

**Performance (30d / 90d / YTD)**:
- **30d**: `((current − price_22_days_ago) / price_22_days_ago) × 100` (~22 trading days/month)
- **90d**: `((current − price_63_days_ago) / price_63_days_ago) × 100` (~63 trading days/quarter)
- **YTD**: `((current − first_price_of_year) / first_price_of_year) × 100`

### Scoring System

Scoring happens in three stages. Positions are scored independently within two pools: **ETFs** and **Stocks**.

#### 1. Momentum Score

```
momentum = 0.20 × perf_30d + 0.30 × perf_90d + 0.50 × perf_ytd
```

YTD performance carries the most weight because it captures the primary trend. Missing periods default to 0 (neutral). All positions get a momentum score regardless of buy eligibility.

#### 2. Value Score

Average of `trailingPE` and `priceToBook` from yfinance `ticker.info`. Lower = cheaper. Only available for stocks — ETFs get `None` (treated as neutral in scoring).

#### 3. Buy Priority Score

**Quality gates** — applied first. A position that fails any gate gets `buy_priority_score = None` and is excluded from ranking:

| Gate | Rule | Reason |
|------|------|--------|
| RSI | < 70 | Not overbought |
| Distance from 52w high | < −3% | Sufficiently below the high |
| Momentum | > −25 | Not in freefall |

**Composite score** — for positions that pass all gates:

```
buy_priority = 0.25 × value + 0.20 × momentum + 0.30 × distance + 0.15 × RSI_inv + 0.10 × weight_inv
```

| Factor | Weight | What it rewards |
|--------|--------|-----------------|
| Value | 25% | Low P/E and P/B (cheap) |
| Momentum | 20% | Positive recent performance |
| Distance from 52w high | 30% | Far below the 52-week high (good entry) |
| RSI inverse | 15% | Low RSI (oversold) |
| Weight inverse | 10% | Small position (diversification benefit) |

**Normalization** — each factor is z-score normalized within its pool (ETF or Stock), then mapped to [0, 1]:

```
normalized = max(0, min(1, 0.5 + (value − mean) / (3 × std)))
```

If a pool has fewer than 3 positions, all factors default to 0.5 (neutral). Missing data (e.g. no P/E) also gets 0.5.

**Important**: the buy priority score is **relative, not absolute**. A score of 0.72 means "best candidate relative to the current pool" — not a buy signal on its own.

### Portfolio-Level Metrics

**Weight** — `position_value_eur / total_portfolio_value × 100`. Computed for all positions.

**ETF / Stock allocation** — sum of weights by `asset_type`. Compared against configurable targets (default: 70% ETF / 30% stock).

**Attribution** — how much each position contributed to portfolio returns:
- `absolute_contribution = position_return × weight`
- `relative_contribution = (position_return − benchmark_return) × weight`

**Benchmark** — S&P 500 (`^GSPC`), indexed to 100 at the date of your first snapshot. Each snapshot records `benchmark_return_pct` for comparison.

### Worked Example

Let's trace a fictitious stock through the full pipeline.

**Position: NVDA (NVIDIA Corp)**

| Field | Value | Source |
|-------|-------|--------|
| Quantity | 10 shares | DeGiro |
| Avg buy price | €45.00 | DeGiro (EUR) |
| Currency | USD | yfinance |
| Current price | $120.00 | yfinance batch |

**Step 1 — Price & P&L**

```
FX rate (USD→EUR) = 0.92
Position value = $120.00 × 10 = $1,200.00
Value in EUR = $1,200.00 × 0.92 = €1,104.00

avg_buy converted to USD = €45.00 / 0.92 = $48.91
P&L % = (($120.00 − $48.91) / $48.91) × 100 = +145.2%
```

**Step 2 — Technical Indicators** (from 1-year history)

```
52w high = $140.50 (max of close)
52w low = $72.30 (min of close)
Distance from 52w high = ((120.00 − 140.50) / 140.50) × 100 = −14.6%

RSI(14) = 62 (Wilder's smoothing on daily closes)
perf_30d = ((120 − 108) / 108) × 100 = +11.1%
perf_90d = ((120 − 95) / 95) × 100 = +26.3%
perf_ytd = ((120 − 80) / 80) × 100 = +50.0%
```

**Step 3 — Scoring**

```
Momentum = 0.20 × 11.1 + 0.30 × 26.3 + 0.50 × 50.0 = +35.1
Value (P/E=65, P/B=42) = (65 + 42) / 2 = 53.5
```

Quality gates:
- RSI 62 < 70 ✓
- Distance −14.6% < −3% ✓
- Momentum 35.1 > −25 ✓

→ NVDA is **buyable**. Now compute the composite score.

After z-score normalization across the stock pool (let's say 8 stocks), NVDA's normalized factors are:

```
value_norm     = 0.35  (high P/E → expensive → lower score)
momentum_norm  = 0.78  (strong upward trend)
distance_norm  = 0.82  (14.6% below high → good entry)
rsi_inv_norm   = 0.55  (RSI 62 → slightly above midpoint)
weight_inv_norm = 0.70  (small position → diversification bonus)

Buy Priority = 0.25×0.35 + 0.20×0.78 + 0.30×0.82 + 0.15×0.55 + 0.10×0.70
             = 0.088 + 0.156 + 0.246 + 0.083 + 0.070
             = 0.64
```

NVDA scores **0.64** — a solid candidate driven by good entry distance and momentum, limited by a high P/E. If it had RSI 75, it would fail the quality gate and get `buy_priority_score = None`.

### Data Sources

| Data | Source | Cache |
|------|--------|-------|
| Positions, quantities, buy prices | DeGiro API | In-memory, 30-min TTL |
| Current prices | yfinance batch download | 15-min TTL |
| RSI, 52w range, performance | yfinance `ticker.history("1y")` | Per-request (fresh) |
| P/E, P/B, sector, country | yfinance `ticker.info` | 24-hour TTL |
| Symbol resolution (ISIN → Yahoo ticker) | yfinance Search + suffix scan | Persistent (disk) |
| FX rates | yfinance currency pairs | Per-session |
| Historical snapshots | Local JSON files | N/A |

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

- No credential storage — JSESSIONID token discarded after session creation
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
