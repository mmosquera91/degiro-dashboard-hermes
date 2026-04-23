# Stack

**Research Date:** 2026-04-23
**Project:** Brokr — Portfolio analytics dashboard for DeGiro

## Standard Stack

### Backend

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Runtime** | Python 3.11 | Specified in Dockerfile, modern syntax support |
| **Framework** | FastAPI 0.115.6 | ASGI framework, Pydantic v2 models, static file serving built-in |
| **Server** | Uvicorn 0.34.0 | Standard ASGI server for FastAPI, production-ready |
| **HTTP Client** | httpx 0.28.1 | Used in Docker healthcheck; degiro-connector uses requests |
| **Data Processing** | pandas 2.2.3, numpy 2.2.1 | RSI computation, median calculations, time-series manipulation |

### External Integrations

| Component | Library | Version |
|-----------|---------|---------|
| **Broker API** | degiro-connector | 3.0.35 |
| **Market Data** | yfinance | 0.2.51 |

### Frontend

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Language** | Vanilla JavaScript (ES6+) | No build step, keeps Docker image small |
| **Charts** | Chart.js | 4.4.7 via CDN |
| **Icons** | Lucide | 0.460.0 via CDN |
| **Fonts** | Google Fonts (Inter) | Via CDN |

### Infrastructure

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Container** | Docker | python:3.11-slim base, non-root user |
| **Orchestration** | docker-compose | Single service with healthcheck |

## Architecture Patterns

**Monolith with layered separation:**
```
app/main.py          # API layer, routing, session cache
app/degiro_client.py # Broker integration
app/market_data.py   # Market data enrichment
app/scoring.py       # Portfolio scoring
app/context_builder.py # Hermes context export
app/static/          # Frontend (served as static files)
```

**Session management:** In-memory Python dict with threading.Lock for thread safety. 30-min TTL, portfolio cache 5-min TTL.

**Two-phase data loading:** Raw portfolio first (fast), then enrichment pass with yfinance (slower, blocking I/O).

## Key Libraries

- **degiro-connector 3.0.35**: TradingAPI, Credentials, Login models. Handles session management.
- **yfinance 0.2.51**: Prices, 52-week range, RSI, sector data. Rate-limited with 0.25s delay.
- **fastapi 0.115.6**: Route handlers, Pydantic models, StaticFiles mount.
- **pandas 2.2.3**: Time-series operations for historical data.
- **numpy 2.2.1**: Numerical operations, median calculation.

## Don't Hand-Roll

- **Authentication session management** — degiro-connector handles this
- **Portfolio data parsing** — degiro-connector models are comprehensive
- **Chart rendering** — Chart.js handles all visualization
- **HTTP client for DeGiro** — Use degiro-connector's internal requests, not raw httpx

## Confidence

- Stack choices: **High** — validated by existing codebase
- Library versions: **High** — confirmed in requirements.txt and working container

---
*Synthesized from codebase analysis: 2026-04-23*