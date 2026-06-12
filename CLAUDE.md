# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Agent skills

### Issue tracker
Local markdown issue tracker — issues live as files under `.scratch/`. See `docs/agents/issue-tracker.md`.

### Triage labels
Default triage label vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs
Single-context layout — one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

---

## Development commands

All development runs inside Docker — `degiro-connector` is not installable on the host.

```bash
# First-time setup
cp .env.example .env
# Edit .env: set BROKR_AUTH_TOKEN, APP_PASSWORD, SECRET_KEY

# Build and start dev container (rebuilds on source changes)
docker compose -f docker-compose.dev.yml up -d --build

# Rebuild after code changes
docker compose -f docker-compose.dev.yml up -d --build

# View logs
docker logs brokr --tail 50 -f

# Health check
curl http://localhost:8000/health
```

### Running tests

Tests must run inside the container:

```bash
# Run full suite
docker cp tests/ brokr:/app/tests/
docker exec brokr pip install pytest pytest-asyncio httpx -q
docker exec brokr bash -c "cd /app && python -m pytest tests/ -q"

# Run a single test file
docker exec brokr bash -c "cd /app && python -m pytest tests/test_scoring.py -q"

# Run a single test by name
docker exec brokr bash -c "cd /app && python -m pytest tests/test_scoring.py::test_buy_priority_insufficient_pool -q"
```

---

## Architecture

### Data flow

```
DeGiro (JSESSIONID) → degiro_client.py → positions (raw)
                                              ↓
yfinance ──────────→ market_data.py → enriched positions (prices, RSI, 52w, FX, P/E)
                                              ↓
                      scoring.py    → momentum + buy_priority scores (per ETF/STOCK pool)
                                              ↓
                      context_builder.py → AI-ready JSON + plaintext (/api/hermes-context)
```

### Key modules

| File | Role |
|------|------|
| `app/main.py` | FastAPI app, all routes, in-memory session/portfolio cache, auth middleware |
| `app/degiro_client.py` | DeGiro v3 connector wrapper; session injection via `from_session_id()` |
| `app/market_data.py` | yfinance enrichment: batch price fetch, RSI(14), 52w range, FX, performance, symbol resolution |
| `app/scoring.py` | Momentum score, value score, buy priority score with quality gates; normalization per ETF/STOCK pool |
| `app/universe.py` | Scores the combined holdings + watchlist universe |
| `app/watchlist_store.py` | Persistent watchlist (JSON file at `WATCHLIST_PATH`); max 30 entries |
| `app/snapshots.py` | Historical P&L snapshots + TWR benchmark vs S&P 500 |
| `app/context_builder.py` | Builds structured Hermes context from enriched portfolio |
| `app/schemas.py` | Pydantic v2 models for all request/response types |
| `app/indexa_client.py` | Indexa Capital integration (separate from DeGiro) |
| `app/rebalance.py` | Rebalancing logic against ETF/stock allocation targets |
| `app/health_checks.py` | Health alerts computed on enrichment |
| `app/rate_limiter.py` | IP-based rate limiting (5 attempts/IP/60s on login) |
| `app/static/app.js` | Main dashboard SPA logic (vanilla JS, no framework) |
| `app/static/watchlist.js` | Watchlist UI |
| `app/static/login.js` | Login page + session injection flow |

### In-memory session cache (`main.py`)

```python
_session = {
    "trading_api": None,     # TradingAPI instance; 30-min TTL
    "portfolio": None,       # enriched portfolio dict; 15-min TTL
    "portfolio_time": None,
}
```

The cached portfolio is served even after the session expires — users don't need to re-inject to see stale data. All state is lost on container restart (stateless by design).

### Scoring pools

Positions are scored **independently** within two pools: **ETFs** and **STOCKs**. A pool needs ≥4 positions to produce meaningful rankings; fewer returns `buy_priority_score = None` for all members of that pool.

ETFs are **exempt from quality gates** (RSI < 70, distance from 52w high < −3%, momentum > −25). Gates apply to stocks only.

Watchlist (unowned) entries are scored in the same pool as holdings, with `weight_inv` factor neutralized to 0.5.

---

## Critical quirks

### DeGiro session injection (preferred auth flow)

DeGiro blocks programmatic login (anti-bot fingerprinting). The only reliable flow is browser session injection:

1. Log in at `trader.degiro.nl` → DevTools → Cookies → copy `JSESSIONID`
2. POST to `/api/session` with `{session_id, int_account}`
3. Backend creates `TradingAPI` with dummy credentials and assigns `session_id` directly

The JSESSIONID is consumed once to pull the portfolio and then discarded. Each new DeGiro sync re-prompts.

### DeGiro response format

DeGiro returns portfolio positions as key-value lists, not flat dicts:
```json
{"name": "positionrow", "value": [{"name": "size", "value": 64}, ...]}
```
`_kv_list_to_dict()` in `degiro_client.py` converts these. If DeGiro changes its API format, this is the first place to look.

### GBp pence conversion

yfinance returns LSE prices in pence. `market_data.py` detects `currency=GBp` and divides by 100 before any calculation.

### yfinance rate limiting

`_YF_DELAY = 0.25` (seconds) is applied between per-symbol requests in `market_data.py`. Prices are batch-fetched first (`yf.download()`); the per-symbol path is a fallback. If 429s appear, increase `_YF_DELAY` or add exponential backoff.

### FX handling

`fx_missing` flag is set when a rate can't be fetched — the position is excluded from EUR totals rather than assuming 1:1. FX rates are cached 1 hour; prices 15 minutes; fundamentals (P/E, P/B) 24 hours.

### Symbol resolution

ISIN → Yahoo ticker resolution uses yfinance Search + suffix scanning. Results are cached to disk (`symbol_overrides.json`). US/GB ISINs derive listing currency from the ISIN country prefix (not always EUR). Overrides can be force-reloaded via `POST /api/admin/reload-overrides`.

### CSS specificity — colored table cells

`.positions-table td { color: var(--text) }` has specificity `0,1,1`. Plain `.pl-positive` / `.pl-negative` / `.mom-*` / `.bp-*` have `0,1,0` and lose. All colored-cell rules in `style.css` are written as `.classname, td.classname` so the `td.` variant wins the tie. Follow this pattern when adding new colored-cell classes inside any table.

### Attribution benchmark reference

`relative_contribution = (perf_ytd − ref_ytd) × weight`. The `ref_ytd` comes from `fetch_sp500_ytd_reference()` in `snapshots.py`, **not** from snapshot data. It computes `avg_monthly_return(^GSPC, 6y) × months_elapsed`. Cached 24h in `_sp500_avg_cache`. Do not replace it with snapshot-derived `benchmark_return_pct` — that value is near-zero when there is only one snapshot.

### Sticky table headers

`position: sticky; top: 0` on `<th>` only works if the scroll container is the element with `overflow-y: auto` **and** a constrained height. `.table-wrap` uses `max-height` + `overflow-y: auto` for this reason. Removing `max-height` or adding `overflow: visible` to any ancestor between `<th>` and `.table-wrap` will silently break the sticky behavior.

---

## Environment variables

| Variable | Required | Notes |
|----------|----------|-------|
| `BROKR_AUTH_TOKEN` | Yes | Bearer token for all `/api/*` routes |
| `APP_PASSWORD` | Yes | Dashboard login password |
| `SECRET_KEY` | Yes | Signed cookie key |
| `COOKIE_SECURE` | No | Set `true` for HTTPS; default `false` |
| `TARGET_ETF_PCT` | No | Default `70` |
| `TARGET_STOCK_PCT` | No | Default `30` |
| `WATCHLIST_PATH` | No | Default `/data/watchlist.json`; bind-mounted via `./data` |

---

## Docker notes

- `docker-compose.yml` (production) uses a pre-built image from GHCR
- `docker-compose.dev.yml` builds from source
- `network_mode: host` is used on Linux for direct port access. On Mac/Windows, switch to `ports:` — see `DECISIONS.md`
- `./data` directory is bind-mounted so `watchlist.json`, `symbol_overrides.json`, and snapshots survive container recreation
- Container runs as non-root `appuser` (UID 1000)
