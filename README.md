# Brokr — Portfolio Intelligence

[![CI](https://github.com/mmosquera91/degiro-dashboard-hermes/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/mmosquera91/degiro-dashboard-hermes/actions/workflows/docker-publish.yml)
[![Docker Image](https://img.shields.io/badge/ghcr-mmosquera91%2Fdegiro--dashboard--hermes-blue?logo=docker)](https://github.com/mmosquera91/degiro-dashboard-hermes/pkgs/container/degiro-dashboard-hermes)

Self-hosted portfolio analytics dashboard for long-term DeGiro investors. Brokr connects to your DeGiro account, enriches positions with live market data via yfinance, computes momentum and buy-priority scores, and produces structured context blocks for AI-powered analysis.

---

## Quick Start

### From Docker image (recommended)

```bash
docker pull ghcr.io/mmosquera91/degiro-dashboard-hermes:latest

# Create .env (see Environment Variables below)
cp .env.example .env
# Edit .env — BROKR_AUTH_TOKEN, APP_PASSWORD, and SECRET_KEY are REQUIRED

docker run -d \
  --name brokr \
  --network host \
  --restart unless-stopped \
  --env-file .env \
  -v ./data/snapshots:/data/snapshots \
  ghcr.io/mmosquera91/degiro-dashboard-hermes:latest
```

Dashboard at **http://localhost:8000**

### From source (for development)

```bash
git clone git@github.com:mmosquera91/degiro-dashboard-hermes.git brokr && cd brokr
cp .env.example .env
docker compose up -d
```

---

## Architecture

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, uvicorn |
| DeGiro API | degiro-connector 3.0.35 |
| Market data | yfinance (prices, RSI, 52w range, sector, P/E, performance) |
| Frontend | Vanilla JS + Chart.js v4 + Lucide icons |
| Font | Inter (Google Fonts) |
| Deploy | Docker Compose (single container, `network_mode: host`) |

### Auth Flow

Brokr uses a **dual-layer auth system**:

1. **Browser Session** — password-protected login via Jinja2 template. Sets signed `brokr_session` cookie validated by middleware on every page request.

2. **API Bearer Token** — JS calls `/api/session-token` after page load to get `BROKR_AUTH_TOKEN`. All `/api/*` endpoints require `Authorization: Bearer <token>` header.

### Data Flow

```
DeGiro API ──→ portfolio positions ──→ yfinance enrichment ──→ scoring engine
                                         │                         │
                                         ▼                         ▼
                                   market_data.py            scoring.py
                                   (prices, RSI,            (momentum, value,
                                    52w, P/E, perf)          buy priority)
                                                                    │
                                                                    ▼
                                                           context_builder.py
                                                           (JSON + plaintext for AI)
```

---

## API Reference

### Authentication

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/session` | Bearer | Inject DeGiro JSESSIONID from browser. Body: `{session_id, int_account?}` |
| `DELETE` | `/api/session` | Bearer | Clear DeGiro session and portfolio cache |

### Portfolio

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/portfolio` | Bearer | Full portfolio with enrichment, scores, and top candidates. Returns cache if stale. |
| `GET` | `/api/portfolio-raw` | Bearer | Raw DeGiro positions without yfinance (~2-3s). |
| `POST` | `/api/refresh-prices` | Bearer | Force re-enrichment of cached positions with live prices. |
| `GET` | `/api/enrichment-status` | None | Poll enrichment progress: `{enriching, last_enriched_at, positions_enriched}` |

### Analytics

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/hermes-context` | Bearer | Structured JSON + plaintext block for AI analysis |
| `GET` | `/api/benchmark` | Bearer | S&P 500 benchmark comparison vs portfolio |
| `GET` | `/api/snapshots` | Bearer | List all stored portfolio snapshots |
| `POST` | `/api/snapshots/save` | Bearer | Save current portfolio state as snapshot |
| `DELETE` | `/api/snapshots/{date}` | Bearer | Delete a specific snapshot |

### Admin

| Method | Path | Description |
|--------|------|-------------|
| `DELETE` | `/api/admin/symbol-cache` | Clear yfinance symbol resolution cache |
| `POST` | `/api/admin/reload-overrides` | Reload symbol overrides from `/data/symbol_overrides.json` |

### System

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check — returns `{status: "ok"}` |
| `GET` | `/api/session-token` | Bootstrap endpoint — returns bearer token for JS API calls |

---

## Hermes Integration

Brokr generates a ready-to-paste context block for AI agents. Click **Export for Hermes** in the dashboard or hit `GET /api/hermes-context`.

### What's in the context

- **Portfolio Summary** — total value, P&L, allocation vs targets (70/30 ETF/stock), cash
- **Positions Table** — sorted by momentum score, weakest first
- **Detailed Metrics** — per-position: RSI, 52w range, P/E, 30d/90d/YTD performance, momentum/value/buy priority scores
- **Top Buy Candidates** — top 3 ETFs and stocks ranked by buy priority
- **Benchmark vs S&P 500** — indexed performance comparison with historical snapshots
- **Attribution** — absolute and relative contribution of each position

### How Brokr + Hermes work together

Brokr provides **portfolio data and metrics only**. The AI agent (Hermes) handles:
- News and sentiment analysis
- Macroeconomic context
- Earnings reports
- Buy/sell/hold recommendations

Brokr doesn't make decisions — it gives the agent clean, structured data to reason with.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST_PORT` | `8000` | Port the dashboard listens on |
| `BROKR_AUTH_TOKEN` | *(required)* | Bearer token for API auth |
| `APP_PASSWORD` | *(required)* | Password for browser login |
| `SECRET_KEY` | *(required)* | Key for signing session cookies |
| `TARGET_ETF_PCT` | `70` | Target ETF allocation percentage |
| `TARGET_STOCK_PCT` | `30` | Target stock allocation percentage |
| `COOKIE_SECURE` | `true` | Set `false` for local HTTP development |

---

## Deployment

### Pre-built image (easiest)

```bash
# Pull the latest image
docker pull ghcr.io/mmosquera91/degiro-dashboard-hermes:latest

# Run (network_mode: host — use port mapping for macOS/Windows)
docker run -d --name brokr --network host --restart unless-stopped \
  --env-file .env \
  -v ./data/snapshots:/data/snapshots \
  ghcr.io/mmosquera91/degiro-dashboard-hermes:latest
```

### Docker Compose (source build)

```bash
docker compose up -d --build
```

Container uses `network_mode: host`. For bridge networking (Mac/Windows), set `NETWORK_MODE=bridge` and add `ports: "8000:8000"` to `docker-compose.yml`.

### Production with HTTPS

```nginx
server {
    listen 443 ssl;
    server_name brokr.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/brokr.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/brokr.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name brokr.yourdomain.com;
    return 301 https://$host$request_uri;
}
```

### DeGiro Session Injection

DeGiro blocks automated login with 400/503 due to anti-bot fingerprinting. The recommended flow:

1. Log into trader.degiro.nl in your browser
2. Open DevTools → Application → Cookies → `trader.degiro.nl`
3. Copy the `JSESSIONID` value
4. In the Brokr dashboard, tab **Browser Session**, paste JSESSIONID + your intAccount
5. Brokr creates a session using your browser-authenticated cookie

Credentials are never stored on disk.

---

## Security

- **Credentials never stored.** Username, password, and 2FA codes are used only for the duration of the API call and discarded immediately.
- **Session in memory only.** DeGiro session token held server-side with 30-minute TTL. Lost on container restart.
- **No database.** All state is in-memory — no persistent credential storage.
- **Bearer token auth** on all `/api/*` endpoints.
- **Rate limiting** — 5 login attempts per IP per 60 seconds.
- **Signed cookies** — HttpOnly, SameSite=Lax, Secure (conditional on HTTPS).
- **SRI hashes** on CDN resources (Chart.js, Lucide).
- **Run behind HTTPS** in production (nginx + certbot).

---

## Development

### Setup

```bash
cd ~/workspace/brokr
docker compose up -d --build
```

### Running Tests

Tests must run inside the Docker container (host lacks `degiro-connector`):

```bash
docker cp tests/ brokr:/app/tests/
docker exec brokr pip install pytest pytest-asyncio httpx -q
docker exec brokr bash -c "cd /app && python -m pytest tests/ -q"
```

**120 tests passing** (as of Sprint 6).

### Key Commands

```bash
# Rebuild after code changes
docker compose up -d --build

# View logs
docker logs brokr --tail 50 -f

# Verify container is running as appuser (not root)
docker exec brokr id   # must show uid=1000(appuser)
```

### Project Structure

```
brokr/
├── app/
│   ├── main.py              # FastAPI app, all routes, auth middleware
│   ├── degiro_client.py     # DeGiro API integration, session management
│   ├── market_data.py       # yfinance enrichment, FX rates, RSI, performance
│   ├── scoring.py           # Momentum, value, buy priority scoring
│   ├── context_builder.py   # Hermes context generation (JSON + plaintext)
│   ├── snapshots.py         # Portfolio snapshot storage, benchmark comparison
│   ├── health_checks.py     # Health alert computation
│   ├── rate_limiter.py      # In-memory IP-based rate limiter
│   ├── schemas.py           # Pydantic v2 request/response models
│   └── static/
│       ├── index.html       # Dashboard SPA
│       ├── style.css        # Dark theme (#0f0f0f, #1a1a1a, teal #01696f)
│       └── app.js           # Vanilla JS, Chart.js charts, API calls
├── templates/
│   ├── login.html           # Password-protected login page
│   └── index.html           # Dashboard template
├── tests/                   # Pytest suite (120 tests)
├── Dockerfile               # python:3.11-slim, USER appuser (UID 1000)
├── docker-compose.yml       # Service "brokr", bind mount snapshots
├── DECISIONS.md             # Architecture decision records
├── agents.md                # Agent-facing project context
└── README.md                # This file
```

---

## Sprint History

### Sprint 1 — Critical Fixes
Division by zero guards, IndexError on empty DeGiro responses, race condition locks.

### Sprint 2 — Security Hardening
Bearer token auth, rate limiting, signed cookies, XSS escaping, SRI hashes, timing-safe comparison.

### Sprint 3 — Test Coverage
101 tests across 4 phases (unit, integration, edge cases, regression).

### Sprint 4 — Architecture
Pydantic v2 schemas, pinned dependencies, Jinja2 templates, `/api/session` injection endpoint, Health Alerts.

### Sprint 5 — Dashboard UX
KPI cards with live values, daily portfolio valuation, benchmark Y-axis fix, mobile table with sticky column, allocation bar layout.

### Sprint 6 — Bug Squash & Optimization (current)
- **Block A:** 7 HIGH-priority bugs fixed — FX duplication (H4), event loop crash (H5), scoring defaults (H6), P&L% miscalculation (H7), N/A display (H8), Chart.js memory leak (H9), benchmark price KeyError (C3).
- **Block B:** Post-batch enrichment parallelized with `asyncio.gather` — enrichment time reduced from ~13.2s to ~9.1s steady state.
- **Infrastructure:** Docker volume → bind mount + UID alignment — eliminated `PermissionError` on snapshot writes.

---

## FAQ

**Q: Why not use the degiro-connector login directly?**  
A: DeGiro blocks automated login with 400/503 errors. Browser session injection (JSESSIONID) is the reliable workaround.

**Q: Where are my credentials stored?**  
A: Nowhere. They're used once to establish a session and immediately discarded. Not in environment files, not in Docker volumes, not in localStorage.

**Q: Can I run this without Docker?**  
A: Yes — `pip install -r requirements.txt && python start.py`. But Docker is the tested deployment path.

**Q: How do I update?**  
A: `docker compose down && git pull && docker compose up -d --build`

---

*Built for long-term buy-and-hold investors. Not financial advice.*
