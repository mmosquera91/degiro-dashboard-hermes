# Architecture

**Analysis Date:** 2026-04-23

## Pattern Overview

**Overall:** Single-process monolith with server-side session caching

**Key Characteristics:**
- FastAPI application serving both REST API and static frontend from a single process
- No database -- all state held in Python process memory with TTL-based cache
- Two-phase data loading: raw DeGiro data served immediately, then enriched with yfinance in a second pass
- Credentials are ephemeral (never persisted to disk); only the session token is cached in memory
- Frontend is a single-page application with no build step (vanilla JS, loaded via CDN dependencies)

## Layers

**API / Routing Layer:**
- Purpose: HTTP endpoint definitions, request validation, response serialization
- Location: `app/main.py`
- Contains: FastAPI route handlers, Pydantic request models, in-memory session cache
- Depends on: `degiro_client`, `market_data`, `scoring`, `context_builder`
- Used by: Frontend JavaScript (`app/static/app.js`)

**DeGiro Integration Layer:**
- Purpose: Authenticate with DeGiro broker API and fetch raw portfolio data
- Location: `app/degiro_client.py`
- Contains: `DeGiroClient` class with static methods, raw HTTP login helpers, debug login variants
- Depends on: `degiro-connector` (third-party SDK), `requests`
- Used by: `app/main.py`

**Market Data Enrichment Layer:**
- Purpose: Enrich portfolio positions with live market data from Yahoo Finance
- Location: `app/market_data.py`
- Contains: yfinance-based enrichment functions, RSI computation, FX rate conversion, performance calculation
- Depends on: `yfinance`, `pandas`, `numpy`
- Used by: `app/main.py`

**Scoring Layer:**
- Purpose: Compute momentum, value, and buy-priority scores for each position
- Location: `app/scoring.py`
- Contains: Score computation functions, min-max normalization, portfolio weight calculation, top candidate selection
- Depends on: `numpy`
- Used by: `app/main.py`

**Context Builder Layer:**
- Purpose: Build structured JSON and plaintext context for the Hermes AI agent
- Location: `app/context_builder.py`
- Contains: Portfolio summarization and plaintext formatting for AI consumption
- Depends on: Standard library only
- Used by: `app/main.py` (via `/api/hermes-context` endpoint)

**Frontend Layer:**
- Purpose: Browser-based dashboard UI for portfolio visualization
- Location: `app/static/` (index.html, app.js, style.css)
- Contains: Vanilla JS SPA, Chart.js visualizations, DOM manipulation
- Depends on: Chart.js (CDN), Lucide icons (CDN), Inter font (Google Fonts CDN)
- Used by: End user via browser

## Data Flow

**Portfolio Loading (two-phase):**

```
Browser                          FastAPI                      DeGiro API              Yahoo Finance
  |                                |                              |                        |
  |--- POST /api/auth ----------->|                              |                        |
  |                                |--- authenticate() --------->|                        |
  |                                |<-- TradingAPI session -------|                        |
  |                                |   (cached in _session dict)  |                        |
  |<-- {status: authenticated} ----|                              |                        |
  |                                |                              |                        |
  |--- GET /api/portfolio-raw --->|                              |                        |
  |                                |--- fetch_portfolio() ------>|                        |
  |                                |<-- raw positions + cash -----|                        |
  |<-- basic portfolio data -------|                              |                        |
  |                                |                              |                        |
  |--- GET /api/portfolio ------->|                              |                        |
  |                                |--- fetch_portfolio() ------>|                        |
  |                                |<-- raw positions + cash -----|                        |
  |                                |--- enrich_positions() ------>|----------------------->|
  |                                |<-- enriched positions -------|<-- prices, RSI, etc ---|
  |                                |--- compute_portfolio_weights()                        |
  |                                |--- compute_scores()                                   |
  |                                |--- _build_portfolio_summary()                         |
  |<-- full portfolio + scores ---|                              |                        |
```

**State Management:**
- Server-side: Module-level `_session` dict in `app/main.py` protected by `threading.Lock`
  - Stores: `trading_api` (DeGiro session), `session_time`, `portfolio` (cached enriched data), `portfolio_time`
  - TTLs: Session = 30 minutes, Portfolio cache = 5 minutes
- Client-side: `portfolioData` JS variable (no localStorage, no IndexedDB)
- No external state store (no database, no Redis, no file persistence)

## Key Abstractions

**DeGiroClient (Static Service Class):**
- Purpose: Encapsulates all DeGiro API interaction behind static methods
- Examples: `app/degiro_client.py` (class `DeGiroClient`)
- Pattern: Static utility class -- no instances created. Methods: `authenticate()`, `from_session_id()`, `fetch_portfolio()`
- Design choice: Uses `degiro-connector` SDK internally but also has raw HTTP fallback for login debugging

**Position Dict (Data Transfer Object):**
- Purpose: Canonical dictionary shape representing a single portfolio position
- Examples: Passed throughout `market_data.py`, `scoring.py`, `context_builder.py`
- Pattern: Plain Python dict (not a Pydantic model or dataclass). Keys are added progressively:
  1. After DeGiro fetch: `id`, `product_id`, `name`, `isin`, `symbol`, `currency`, `asset_type`, `quantity`, `avg_buy_price`, `current_price`, `current_value`, `unrealized_pl`, `unrealized_pl_pct`, `sector`, `country`
  2. After yfinance enrichment: `52w_high`, `52w_low`, `distance_from_52w_high_pct`, `rsi`, `perf_30d`, `perf_90d`, `perf_ytd`, `pe_ratio`, `sector`, `country`, `fx_rate`, `current_value_eur`, `unrealized_pl_eur`
  3. After scoring: `weight`, `momentum_score`, `value_score`, `buy_priority_score`

**Portfolio Summary (Aggregation Dict):**
- Purpose: Top-level portfolio aggregation with all computed data ready for API response
- Examples: Built by `_build_portfolio_summary()` and `_build_raw_portfolio_summary()` in `app/main.py`
- Pattern: Flat dict with scalar fields (`total_value`, `total_pl_pct`), lists (`positions`, `top_5_winners`), and nested dicts (`sector_breakdown`, `top_candidates`)

## Entry Points

**Application Server:**
- Location: `app/main.py` (creates `app = FastAPI(...)`)
- Triggers: Uvicorn ASGI server started by Docker `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`
- Responsibilities: Serves all HTTP routes and static files

**Health Check:**
- Location: `GET /health` in `app/main.py`
- Triggers: Docker healthcheck every 30 seconds
- Responsibilities: Returns `{"status": "ok"}` if the process is alive

**Debug Scripts (standalone, not part of the web app):**
- `app/debug_login.py` -- CLI tool to test DeGiro login with raw credentials
- `app/debug_from_session.py` -- CLI tool to test session-based connection
- `app/debug_int_account.py` -- CLI tool to locate `intAccount` in client details
- `app/debug_portfolio.py` -- CLI tool to dump raw portfolio structure
- `app/debug_raw_portfolio.py` -- CLI tool to inspect raw position fields

## Error Handling

**Strategy:** Try-catch at route level with HTTP status codes; graceful degradation for enrichment failures.

**Patterns:**
- Route handlers wrap all logic in try/except, raising `HTTPException` with appropriate status codes (401 for auth, 500 for server errors, 404 for missing data)
- Individual position enrichment failures in `market_data.py` are caught per-position -- a position with failed yfinance lookup still appears in the portfolio with null enrichment fields
- DeGiro login errors are translated from SDK exceptions into `ConnectionError` with human-readable messages (handles captcha, 2FA, maintenance, bad credentials)
- Raw portfolio data survives even if enrichment fails entirely (two-phase loading strategy)

## Cross-Cutting Concerns

**Logging:** Python `logging` module configured in `app/main.py` with `basicConfig` at INFO level. All modules use `logging.getLogger(__name__)`. Log format: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`.

**Validation:** Pydantic `BaseModel` for API request bodies (`AuthRequest`, `SessionRequest`). No response validation -- portfolio data is returned as raw dicts. Position data has no schema validation at the dict level.

**Authentication:** DeGiro credentials flow through the browser to `/api/auth` or `/api/session`, are used once to establish a `TradingAPI` session, and are discarded. The resulting session object lives in server memory with a 30-minute TTL. No user authentication for the Brokr app itself -- anyone with network access can use it.

**Threading:** A `threading.Lock` (`_session_lock`) protects the in-memory session cache. The yfinance enrichment uses a global throttle (`_YF_DELAY = 0.25s`) to rate-limit API calls. yfinance calls are synchronous (blocking) despite the async FastAPI handlers -- the `enrich_positions` function is declared `async` but calls synchronous yfinance code sequentially.

**Caching:** FX rates cached in module-level `_fx_cache` dict in `market_data.py`. Portfolio data cached in `_session["portfolio"]` with 5-minute TTL. No cache invalidation beyond TTL expiry.

---

*Architecture analysis: 2026-04-23*
