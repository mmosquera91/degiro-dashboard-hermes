# Brokr — Portfolio Intelligence

Brokr is a self-hosted portfolio analytics dashboard for long-term DeGiro investors. It connects to your DeGiro account, enriches positions with live market data (yfinance), computes momentum and buy-priority scores, and produces a structured context block ready for AI-powered analysis via an external agent (Hermes).

## Prerequisites

- Docker and Docker Compose installed on the host
- A DeGiro trading account

## Setup

```bash
# Clone the repository
git clone <repo-url> brokr && cd brokr

# Create your .env file
cp .env.example .env

# (Optional) Change the host port in .env
# HOST_PORT=8000
```

## Run

```bash
docker compose up -d
```

Access the dashboard at **http://localhost:8000** (or your configured `HOST_PORT`).

## How to Use

1. Open the dashboard in your browser
2. Click **Connect to DeGiro** and enter your credentials
3. Your portfolio is loaded with full analytics — scores, RSI, performance, and buy recommendations
4. Use **Export for Hermes** to copy a structured context block for AI analysis

## View Logs

```bash
docker compose logs -f brokr
```

## Stop

```bash
docker compose down
```

## Update

```bash
docker compose down
git pull
docker compose up -d --build
```

## Production: HTTPS with nginx

The container does not handle TLS. Run it behind an nginx reverse proxy with SSL (certbot) on the host.

Minimal nginx config (`/etc/nginx/sites-available/brokr`):

```nginx
server {
    listen 443 ssl;
    server_name brokr.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/brokr.yourdomain.com/fullchain.pem;
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

## Security Model

- **Credentials are never stored.** Your DeGiro username and password are used only for the duration of the API call to establish a session. They are never written to disk, Docker volumes, environment files, localStorage, or any persistent storage.
- The DeGiro session token is held in server-side memory only, with a 30-minute TTL. It is cleared on container restart or explicit logout.
- For production, always run behind HTTPS (nginx + certbot) to protect credentials in transit.

## Hermes Integration

The `/api/hermes-context` endpoint produces a structured JSON and formatted plaintext context block designed to be pasted directly into the Hermes agent for AI-powered buy recommendations. Hermes handles all news fetching and macro analysis independently — Brokr provides only portfolio data and metrics.

Example usage with Hermes:

```
Paste the context from "Export for Hermes" into your Hermes conversation.
Hermes will analyze the portfolio data alongside news and macro context
to recommend what to buy next.
```

## Architecture

- **Backend**: Python (FastAPI) — serves API endpoints and static files
- **Frontend**: Single-file HTML/CSS/JS with Chart.js, no framework
- **DeGiro**: degiro-connector library for authentication and portfolio data
- **Market data**: yfinance for prices, RSI, performance, fundamentals
- **Stateless**: No database — all data fetched live and cached in-memory

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (returns `{status: "ok"}`) |
| POST | `/api/auth` | Authenticate with DeGiro |
| GET | `/api/portfolio` | Full portfolio with metrics |
| GET | `/api/hermes-context` | Hermes-ready context (JSON + plaintext) |
| POST | `/api/logout` | Clear session |
