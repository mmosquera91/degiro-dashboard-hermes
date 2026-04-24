# Conventions

## Code Style

### Python
- **Language version:** Python 3.11+ (Dockerfile uses `python:3.11-slim`)
- **Type hints:** Partial — used on function signatures (`Optional[str]`, `list[dict]`, `int | None`) but not on local variables
- **String formatting:** f-strings exclusively
- **Naming:**
  - Functions/methods: `snake_case`
  - Constants: `UPPER_SNAKE_CASE` (`SESSION_TTL`, `PORTFOLIO_TTL`, `_YF_DELAY`)
  - Private helpers: leading underscore (`_is_session_valid`, `_build_portfolio_summary`, `_min_max_normalize`)
  - Module-level caches: leading underscore (`_fx_cache`, `_last_yf_request`, `_session`)
- **Imports:** stdlib → third-party → local, separated by blank lines
- **Line length:** No enforced limit; lines frequently exceed 100 chars
- **Trailing commas:** Not used consistently

### JavaScript
- **Style:** IIFE-wrapped, strict mode
- **Variables:** `let`/`const`, no `var`
- **Naming:** `camelCase` for functions/variables, `el` prefix for DOM refs (`elDashboard`, `elBtnRefresh`)
- **String quotes:** double quotes for HTML attributes in template literals, single quotes elsewhere
- **DOM:** `$()` and `$$()` shorthand helpers for `querySelector`/`querySelectorAll`
- **No build step:** Vanilla JS served directly, no transpilation or bundling

### CSS
- **Methodology:** Single-file, BEM-like naming for some components
- **Custom properties:** Extensive use of CSS variables in `:root` (--bg, --surface, --teal, etc.)
- **Layout:** CSS Grid and Flexbox, no frameworks
- **Responsive:** Two breakpoints — 768px and 420px

## Patterns

### Error Handling
- **Backend:** try/except with `logger.error()` or `logger.warning()`, re-raise as `HTTPException` or `ConnectionError`
- **Frontend:** try/catch in async functions, display errors in UI elements (`.cred-error` divs)
- **No custom exception classes** — uses `HTTPException`, `ConnectionError`, `RuntimeError`

### Logging
- **Module:** Python stdlib `logging`
- **Pattern:** `logger = logging.getLogger(__name__)` at module top
- **Config:** `basicConfig` in `main.py` — INFO level, timestamp + level + name + message format
- **Frontend:** `console.error` only, no structured logging

### Configuration
- **Hardcoded constants:** TTLs, scoring weights, FX ticker maps, yfinance throttle delay
- **Environment:** Only `HOST_PORT` via `.env` file
- **No config file** or settings module

### Data Flow
- **Position dicts:** Passed through pipeline as mutable dicts (modified in-place)
- **Pipeline:** DeGiro fetch → yfinance enrich → portfolio weights → scoring → summary build
- **Two-stage load:** Raw data served immediately via `/api/portfolio-raw`, then enrichment via `/api/portfolio`

### API Design
- **REST-ish:** GET for reads, POST for auth/logout actions
- **Request models:** Pydantic `BaseModel` for POST bodies
- **Response format:** Plain JSON dicts (not Pydantic response models)
- **Error responses:** `HTTPException` with `detail` string

### Security
- **Credentials:** Never stored on disk, discarded after session establishment
- **CORS:** Not configured (same-origin only)
- **Session:** In-memory per-process, thread-safe via `threading.Lock`
- **XSS prevention:** `esc()` function creates text nodes (not innerHTML) for user data in most places
