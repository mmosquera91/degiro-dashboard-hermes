# Technology Stack

**Analysis Date:** 2026-04-23

## Languages

**Primary:**
- Python 3.11 - Backend API, all server-side logic, data processing
  - Runtime specified in `Dockerfile` as `python:3.11-slim`
  - Uses type hints with `| None` union syntax (Python 3.10+ feature) throughout

**Secondary:**
- JavaScript (ES6+, vanilla) - Frontend single-page application
  - No transpilation, no TypeScript, no bundler
  - IIFE pattern with `"use strict"` in `app/static/app.js`
- HTML5 / CSS3 - UI markup and styling
  - CSS custom properties (variables) for theming
  - No CSS preprocessor (plain CSS in `app/static/style.css`)

## Runtime

**Environment:**
- Python 3.11 (slim Docker image)
- Uvicorn ASGI server (version 0.34.0)

**Package Manager:**
- pip (via `requirements.txt`)
- Lockfile: Not present (no `requirements.lock` or pip freeze output)
- `package-lock.json` exists but is an empty stub with no actual dependencies

## Frameworks

**Core:**
- FastAPI 0.115.6 - ASGI web framework, serves both API and static frontend
  - Uses Pydantic v2 for request/response models (`BaseModel`, `model_construct`)
  - Lifespan context manager for startup/shutdown
  - Static file serving via `StaticFiles` mount

**Frontend Libraries (CDN-loaded):**
- Chart.js 4.4.7 - Doughnut and bar charts for portfolio visualization
  - Loaded from `cdn.jsdelivr.net` in `app/static/index.html`
- Lucide Icons 0.460.0 - SVG icon library
  - Loaded from `unpkg.com` in `app/static/index.html`
- Google Fonts (Inter) - Typography
  - Loaded from `fonts.googleapis.com`

**No frontend build step** - All frontend assets are served as-is from `app/static/`.

## Key Dependencies

**Critical:**
- `degiro-connector` 3.0.35 - Official DeGiro trading API SDK
  - Provides `TradingAPI`, `Credentials`, `Login`, `UpdateRequest` models
  - Handles session management, portfolio fetching, product info lookups
  - Uses Pydantic models for request/response validation
- `yfinance` 0.2.51 - Yahoo Finance market data API
  - Fetches current prices, 52-week highs/lows, historical data
  - Used for RSI calculation, performance metrics (30d/90d/YTD)
  - Provides sector, country, P/E ratio data
  - Rate-limited with 0.25s delay between requests

**Data Processing:**
- `pandas` 2.2.3 - Time-series manipulation for historical price data
  - Used in RSI computation and performance calculations
- `numpy` 2.2.1 - Numerical operations
  - Used for median calculation in normalization, array operations

**Infrastructure:**
- `httpx` 0.28.1 - HTTP client (used in Docker healthcheck, imported but not primary HTTP client)
- `python-multipart` 0.0.20 - Form data parsing (FastAPI dependency for form handling)
- `requests` (transitive via degiro-connector) - Used directly in `degiro_client.py` for raw login requests

## Configuration

**Environment:**
- Single env var: `HOST_PORT` (defaults to 8000) - Docker host port mapping
- `.env` file present - contains environment configuration
- `.env.example` provided with `HOST_PORT=8000`
- No Python configuration files (no `settings.py`, no `config.py`)

**Build:**
- `Dockerfile` - Single-stage build, non-root user (`appuser`)
- `docker-compose.yml` - Single service `brokr`, healthcheck via httpx

**Session Management:**
- In-memory Python dict (`_session` in `app/main.py`)
- Thread-safe via `threading.Lock`
- Session TTL: 30 minutes
- Portfolio cache TTL: 5 minutes

## Platform Requirements

**Development:**
- Python 3.11+
- pip
- Docker (optional, for containerized development)

**Production:**
- Docker container (Linux, python:3.11-slim base)
- Network access to DeGiro API (`trader.degiro.nl`)
- Network access to Yahoo Finance API (`finance.yahoo.com`)
- No database required
- No persistent storage required (stateless except in-memory session)
- Port 8000 exposed

---

*Stack analysis: 2026-04-23*
