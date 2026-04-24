# Integrations

## External APIs

### DeGiro Trading API (primary)
- **Library:** `degiro-connector` v3.0.35
- **Purpose:** Broker authentication, session management, portfolio data retrieval
- **Auth methods:**
  1. **Credential-based** — username/password (+ optional OTP for 2FA) via `TradingAPI.connect()`
  2. **Session-based** — browser-extracted `JSESSIONID` cookie + optional `intAccount`
- **Key endpoints used:**
  - `urls.LOGIN` / `urls.LOGIN + "/totp"` — raw login with multiple variant strategies
  - `trading_api.get_client_details` — fetches `intAccount` after login
  - `trading_api.get_update` — fetches portfolio positions, total portfolio, cash funds
  - `trading_api.get_products_info` — resolves product IDs to names/ISINs/symbols
- **Data models:** `Credentials`, `Login`, `LoginSuccess`, `LoginError`, `UpdateRequest`, `UpdateOption` from degiro-connector
- **Error handling:** Catches `DeGiroConnectionError`, `CaptchaRequiredError`, `MaintenanceError` and converts to user-friendly messages
- **Session lifetime:** 30 min TTL (in-memory), 5 min portfolio cache TTL

### Yahoo Finance (yfinance)
- **Library:** `yfinance` v0.2.51
- **Purpose:** Market data enrichment for each portfolio position
- **Data fetched per position:**
  - Current price (overrides DeGiro price as more real-time)
  - 52-week high/low
  - Sector, country, industry
  - P/E ratio (trailing/forward)
  - Historical data (1 year) for:
    - RSI(14) calculation
    - 30d, 90d, YTD performance
- **FX rates:** Fetched via currency pair tickers (e.g. `USDEUR=X`) for non-EUR positions
- **Rate limiting:** 0.25s throttle between requests, FX rate caching via module-level `_fx_cache` dict
- **Fallback:** If yfinance fails for a position, all enrichment fields default to `None` — raw DeGiro data still displays

### CDN Dependencies (frontend)
- **Chart.js** v4.4.7 — doughnut and bar charts (ETF/stock split, top 10 by weight, sector breakdown)
- **Lucide Icons** v0.460.0 — UI icons (refresh, clipboard, login, charts, etc.)
- **Google Fonts** — Inter typeface (300–700 weights)

## Internal Integrations

### Hermes AI Context Export
- Endpoint: `GET /api/hermes-context`
- Produces structured JSON + plaintext context from cached portfolio
- Plaintext includes portfolio summary, rebalancing note, position table (sorted by momentum), detailed metrics, top buy candidates
- Used for pasting into an external AI agent ("Hermes") for investment analysis

## Authentication Flow
1. User submits credentials via modal (credential or browser session tab)
2. Backend authenticates with DeGiro, stores `TradingAPI` in-memory (per-process, not persisted)
3. Session has 30-min TTL; expired sessions require re-authentication
4. Credentials are discarded after session establishment — never stored on disk
5. Portfolio data cached for 5 minutes, survives session expiry (serves stale data rather than forcing re-login)

## Environment Configuration
- `HOST_PORT` — host port mapping (default: 8000)
- No backend env vars required for operation — all configuration is runtime via API
