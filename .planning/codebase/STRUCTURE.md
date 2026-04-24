# Codebase Structure

**Analysis Date:** 2026-04-23

## Directory Layout

```
brokr/                          # Project root
├── app/                        # Python application package
│   ├── __init__.py             # Empty package init
│   ├── main.py                 # FastAPI app: routes, session cache, summary builders
│   ├── degiro_client.py        # DeGiro authentication and portfolio fetching
│   ├── market_data.py          # yfinance enrichment: prices, RSI, FX, performance
│   ├── scoring.py              # Scoring: momentum, value, buy priority, weights
│   ├── context_builder.py      # Hermes AI agent context builder (JSON + plaintext)
│   ├── static/                 # Frontend assets (served by FastAPI)
│   │   ├── index.html          # Single-page dashboard HTML
│   │   ├── app.js              # Frontend logic: API calls, rendering, charts
│   │   └── style.css           # Dark-theme CSS with custom properties
│   ├── test_auth_methods.py    # Standalone CLI: test OTP vs TOTP login methods
│   ├── test_login.py           # Standalone CLI: test basic DeGiro login
│   ├── debug_from_session.py   # Standalone CLI: test session-based connection
│   ├── debug_int_account.py    # Standalone CLI: inspect intAccount from client details
│   ├── debug_portfolio.py      # Standalone CLI: dump raw portfolio structure
│   └── debug_raw_portfolio.py  # Standalone CLI: inspect raw position field formats
├── .planning/                  # GSD planning documents
│   └── codebase/               # Codebase analysis documents (this directory)
├── Dockerfile                  # Container image: Python 3.11-slim, uvicorn
├── docker-compose.yml          # Single-service container orchestration
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables (gitignored, contains HOST_PORT)
├── .env.example                # Template for .env (contains only HOST_PORT)
├── .gitignore                  # Git ignore rules
├── .dockerignore               # Docker build ignore rules
├── README.md                   # User documentation: setup, usage, security, API
├── agents.md                   # Agent/context documentation
└── package-lock.json           # Artifact (no package.json -- appears unused)
```

## Directory Purposes

**`app/`:**
- Purpose: Entire Python backend application as a single importable package
- Contains: All server-side logic, API routes, DeGiro integration, market data enrichment, scoring, and frontend static files
- Key files: `main.py` (entry point), `degiro_client.py` (broker API), `market_data.py` (yfinance), `scoring.py` (analytics)

**`app/static/`:**
- Purpose: Browser-served frontend assets (HTML, JS, CSS)
- Contains: The complete single-page dashboard application
- Key files: `index.html` (page structure), `app.js` (all client logic), `style.css` (dark theme styles)

**`.planning/codebase/`:**
- Purpose: GSD codebase analysis documents consumed by `/gsd-plan-phase` and `/gsd-execute-phase`
- Contains: Architecture, structure, conventions, and concerns documentation
- Generated: Yes (by `/gsd-map-codebase`)
- Committed: Yes (tracked in git)

## Key File Locations

**Entry Points:**
- `app/main.py`: FastAPI application instance (`app = FastAPI(...)`) and all route handlers. Uvicorn targets `app.main:app`.
- `app/test_auth_methods.py`: Standalone CLI script for testing DeGiro authentication methods (run inside container)
- `app/test_login.py`: Standalone CLI script for basic login verification (run inside container)

**Configuration:**
- `requirements.txt`: Python package dependencies (fastapi, uvicorn, degiro-connector, yfinance, pandas, numpy, httpx, python-multipart)
- `Dockerfile`: Container build instructions (Python 3.11-slim, non-root user, uvicorn CMD)
- `docker-compose.yml`: Single service definition with healthcheck and env_file
- `.env.example`: Documents the only config variable (`HOST_PORT`)
- `.env`: Actual environment configuration (gitignored)

**Core Logic:**
- `app/degiro_client.py`: `DeGiroClient` class with `authenticate()`, `from_session_id()`, `fetch_portfolio()` static methods
- `app/market_data.py`: `enrich_positions()`, `enrich_position()`, `get_fx_rate()`, `compute_rsi()`, `_compute_performance()`
- `app/scoring.py`: `compute_scores()`, `compute_portfolio_weights()`, `get_top_candidates()`, `compute_momentum_score()`, `compute_value_score()`
- `app/context_builder.py`: `build_hermes_context()` -- generates structured context for Hermes AI agent

**Frontend:**
- `app/static/index.html`: Dashboard page with summary cards, chart canvases, positions table, buy radar, winners/losers, credential modal
- `app/static/app.js`: IIFE with all client-side logic -- API calls, DOM rendering, Chart.js charts, sorting, filtering
- `app/static/style.css`: Dark theme with CSS custom properties, responsive breakpoints at 768px and 420px

**Debug / Diagnostic Scripts:**
- `app/debug_login.py`: CLI login test with positional args
- `app/debug_from_session.py`: Tests `from_session_id` connection path
- `app/debug_int_account.py`: Searches client details for `intAccount` field
- `app/debug_portfolio.py`: Dumps raw portfolio update structure (5k char limit)
- `app/debug_raw_portfolio.py`: Inspects raw position fields and cash funds data

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g., `degiro_client.py`, `market_data.py`, `context_builder.py`)
- Debug scripts: `debug_<purpose>.py` (e.g., `debug_portfolio.py`, `debug_int_account.py`)
- Test scripts: `test_<purpose>.py` (e.g., `test_auth_methods.py`, `test_login.py`)
- Frontend: `kebab-case` or `lowercase` (e.g., `index.html`, `app.js`, `style.css`)
- Config: dot-prefixed lowercase (e.g., `.env`, `.env.example`, `.gitignore`)

**Directories:**
- Python package: `app/` (short, flat -- no nested sub-packages)
- Static assets: `app/static/` (conventional FastAPI static files directory)

## Module Dependency Graph

```
app/main.py
  ├── imports app/degiro_client.py     (DeGiroClient, debug_login_variants)
  ├── imports app/market_data.py       (enrich_positions, get_fx_rate)
  ├── imports app/scoring.py           (compute_scores, compute_portfolio_weights, get_top_candidates)
  └── imports app/context_builder.py   (build_hermes_context)

app/market_data.py
  ├── imports yfinance                 (external: Yahoo Finance API)
  ├── imports pandas                   (external: data manipulation)
  └── imports numpy                    (external: numerical computation)

app/scoring.py
  └── imports numpy                    (external: median calculation)

app/context_builder.py
  └── (standard library only)

app/degiro_client.py
  ├── imports degiro_connector         (external: DeGiro SDK)
  └── imports requests                 (external: raw HTTP fallback)

Frontend (app/static/app.js)
  └── depends on CDN: Chart.js, Lucide icons
```

Text representation of the dependency flow:

```
index.html ──loads──> app.js ──fetches──> /api/* routes in main.py
                                              │
                                     ┌────────┼────────┐────────┐
                                     v        v        v        v
                               degiro    market    scoring   context
                              _client    _data               _builder
                                 │        │
                                 │        ├── yfinance
                                 │        ├── pandas
                                 │        └── numpy
                                 │
                                 ├── degiro_connector
                                 └── requests
```

## Where to Add New Code

**New API Endpoint:**
- Add route handler function to `app/main.py` following the existing pattern (decorator + async function + HTTPException on error)
- Add Pydantic request model in the "API Models" section near the top of `app/main.py` if the endpoint accepts POST data

**New Scoring Algorithm:**
- Add function to `app/scoring.py`
- Call it from the pipeline in `app/main.py` within the `get_portfolio()` handler (after `compute_scores()`)

**New Market Data Source:**
- Add enrichment functions to `app/market_data.py` following the `enrich_position()` pattern (accept position dict, mutate in place, return it)
- Wire into `enrich_positions()` or add a new enrichment step in the `get_portfolio()` handler in `app/main.py`

**New Frontend Dashboard Section:**
- Add HTML structure to `app/static/index.html` (inside `#dashboard`)
- Add rendering function to `app/static/app.js` (call from `renderDashboard()`)
- Add styles to `app/static/style.css`

**New Debug Script:**
- Create `app/debug_<purpose>.py` at the top level of `app/`
- Follow the pattern: accept CLI args, create TradingAPI, call method, print result
- Run inside container: `docker compose exec brokr python app/debug_<purpose>.py`

**Utility / Shared Helper:**
- Add a new module to `app/` (e.g., `app/utils.py`)
- Import from `app.main` or other modules using relative import: `from .utils import ...`

## Special Directories

**`app/__pycache__/`:**
- Purpose: Python bytecode cache (auto-generated)
- Generated: Yes (by Python interpreter)
- Committed: No (gitignored)

**`app/static/`:**
- Purpose: Static frontend files served directly by FastAPI via `StaticFiles` mount at `/static`
- Generated: No
- Committed: Yes
- Note: No build step, no bundler. Files are served as-is.

**`.planning/`:**
- Purpose: GSD planning and codebase analysis documents
- Generated: Yes (by GSD tools)
- Committed: Yes

## API Route Map

| Method | Path | Handler in `app/main.py` | Purpose |
|--------|------|--------------------------|---------|
| GET | `/` | `root()` | Serve `index.html` |
| GET | `/health` | `health()` | Health check for Docker |
| POST | `/api/auth` | `auth()` | DeGiro credential-based login |
| POST | `/api/session` | `session_auth()` | DeGiro session-token-based login |
| GET | `/api/portfolio-raw` | `get_portfolio_raw()` | Fast raw portfolio (no yfinance) |
| GET | `/api/portfolio` | `get_portfolio()` | Full enriched portfolio with scores |
| GET | `/api/hermes-context` | `hermes_context()` | AI agent context export |
| POST | `/api/logout` | `logout()` | Clear in-memory session |
| POST | `/api/debug-login` | `debug_login()` | Try multiple login variants |
| GET | `/static/*` | (StaticFiles mount) | Serve CSS, JS, images |

---

*Structure analysis: 2026-04-23*
