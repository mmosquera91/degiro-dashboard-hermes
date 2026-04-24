"""Brokr — FastAPI application with all routes."""

import asyncio
import hmac
import logging
import os
import threading
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .degiro_client import DeGiroClient
from .market_data import enrich_positions, get_fx_rate
from .scoring import compute_scores, compute_portfolio_weights, get_top_candidates
from .context_builder import build_hermes_context
from .health_checks import compute_health_alerts
from .snapshots import save_snapshot, load_snapshots, load_latest_snapshot, fetch_benchmark_series, compute_attribution

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# In-memory session cache
_session = {
    "trading_api": None,
    "session_time": None,
    "portfolio": None,
    "portfolio_time": None,
}
_session_lock = threading.Lock()


async def verify_brok_token(request: Request):
    """Validate BROKR_AUTH_TOKEN bearer token on /api/* routes.

    D-01: Static bearer token — random string via env var, no signature, no expiry.
    D-02: Applied via FastAPI dependency middleware on all /api/* routes.
    D-03: /health and /static/* remain open (no Depends applied to those routes).
    """
    token = os.getenv("BROKR_AUTH_TOKEN", "")

    if not token:
        logger.warning("BROKR_AUTH_TOKEN not configured — blocking API request")
        raise HTTPException(status_code=401, detail="Authentication required")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth format")

    provided = auth_header[7:]
    if not hmac.compare_digest(provided, token):
        raise HTTPException(status_code=401, detail="Invalid token")


SESSION_TTL = timedelta(minutes=30)
PORTFOLIO_TTL = timedelta(minutes=5)


def _is_session_valid() -> bool:
    """Check if the current session is still valid."""
    if _session["trading_api"] is None:
        return False
    if _session["session_time"] and datetime.now() - _session["session_time"] > SESSION_TTL:
        return False
    return True


def _is_portfolio_fresh() -> bool:
    """Check if cached portfolio data is still fresh."""
    if _session["portfolio"] is None or _session["portfolio_time"] is None:
        return False
    return datetime.now() - _session["portfolio_time"] < PORTFOLIO_TTL


def _clear_session():
    """Clear all session data."""
    _session["trading_api"] = None
    _session["session_time"] = None
    _session["portfolio"] = None
    _session["portfolio_time"] = None


def _build_raw_portfolio_summary(positions: list, cash_available: float) -> dict:
    """Build a minimal portfolio summary from raw DeGiro data (no yfinance)."""
    # Work on a copy so the caller's list is not mutated
    positions_copy = [p.copy() for p in positions]

    total_value = sum(p.get("current_value", 0) or 0 for p in positions_copy)
    total_invested = sum((p.get("avg_buy_price", 0) or 0) * p.get("quantity", 0) for p in positions_copy)
    total_pl = total_value - total_invested
    total_pl_pct = (total_pl / total_invested * 100) if total_invested > 0 else 0

    etf_value = sum(p.get("current_value", 0) or 0 for p in positions_copy if p.get("asset_type") == "ETF")
    stock_value = sum(p.get("current_value", 0) or 0 for p in positions_copy if p.get("asset_type") == "STOCK")
    etf_allocation_pct = (etf_value / total_value * 100) if total_value > 0 else 0
    stock_allocation_pct = (stock_value / total_value * 100) if total_value > 0 else 0

    # Basic winners/losers from raw data
    sorted_by_pl = sorted(
        [p for p in positions_copy if p.get("unrealized_pl_pct") is not None],
        key=lambda x: x["unrealized_pl_pct"],
    )
    top_5_losers = [
        {"name": p["name"], "symbol": p.get("symbol", ""), "pl_pct": p["unrealized_pl_pct"]}
        for p in sorted_by_pl[:5]
    ]
    top_5_winners = [
        {"name": p["name"], "symbol": p.get("symbol", ""), "pl_pct": p["unrealized_pl_pct"]}
        for p in sorted_by_pl[-5:][::-1]
    ]

    # Add raw fields that yfinance would later fill
    for p in positions_copy:
        p["current_value_eur"] = p.get("current_value", 0)
        p["52w_high"] = None
        p["52w_low"] = None
        p["distance_from_52w_high_pct"] = None
        p["rsi"] = None
        p["perf_30d"] = None
        p["perf_90d"] = None
        p["perf_ytd"] = None
        p["pe_ratio"] = None
        p["sector"] = None
        p["country"] = None
        p["value_score"] = None
        p["momentum_score"] = None
        p["buy_priority_score"] = None
        p["weight"] = None

    return {
        "date": datetime.now().isoformat(),
        "total_value": round(total_value, 2),
        "total_invested": round(total_invested, 2),
        "total_pl": round(total_pl, 2),
        "total_pl_pct": round(total_pl_pct, 2),
        "etf_allocation_pct": round(etf_allocation_pct, 1),
        "stock_allocation_pct": round(stock_allocation_pct, 1),
        "num_positions": len(positions_copy),
        "top_5_winners": top_5_winners,
        "top_5_losers": top_5_losers,
        "sector_breakdown": {},
        "cash_available": round(cash_available, 2),
        "daily_change_pct": None,
        "positions": positions_copy,
        "top_candidates": {"etfs": [], "stocks": []},
    }


def _build_portfolio_summary(positions: list, cash_available: float) -> dict:
    """Build the full portfolio summary from enriched, scored positions."""
    total_value = sum(p.get("current_value_eur", 0) or 0 for p in positions)
    total_invested = sum((p.get("avg_buy_price", 0) or 0) * p.get("quantity", 0) for p in positions)
    total_pl = total_value - total_invested
    total_pl_pct = (total_pl / total_invested * 100) if total_invested > 0 else 0

    etf_value = sum(p.get("current_value_eur", 0) or 0 for p in positions if p.get("asset_type") == "ETF")
    stock_value = sum(p.get("current_value_eur", 0) or 0 for p in positions if p.get("asset_type") == "STOCK")
    etf_allocation_pct = (etf_value / total_value * 100) if total_value > 0 else 0
    stock_allocation_pct = (stock_value / total_value * 100) if total_value > 0 else 0

    # Top 5 winners and losers by P&L%
    sorted_by_pl = sorted(
        [p for p in positions if p.get("unrealized_pl_pct") is not None],
        key=lambda x: x["unrealized_pl_pct"],
    )
    top_5_losers = [
        {"name": p["name"], "symbol": p.get("symbol", ""), "pl_pct": p["unrealized_pl_pct"]}
        for p in sorted_by_pl[:5]
    ]
    top_5_winners = [
        {"name": p["name"], "symbol": p.get("symbol", ""), "pl_pct": p["unrealized_pl_pct"]}
        for p in sorted_by_pl[-5:][::-1]
    ]

    # Sector breakdown
    sector_map = {}
    for p in positions:
        sector = p.get("sector") or "Unknown"
        val = p.get("current_value_eur", 0) or 0
        sector_map[sector] = sector_map.get(sector, 0) + val

    total_for_sector = sum(sector_map.values()) or 1
    sector_breakdown = {k: round(v / total_for_sector * 100, 1) for k, v in sector_map.items()}

    # Top candidates
    top_candidates = get_top_candidates(positions, n=3)

    # Daily change (approximation from yfinance — not directly from DeGiro)
    daily_change_pct = None

    return {
        "date": datetime.now().isoformat(),
        "total_value": round(total_value, 2),
        "total_invested": round(total_invested, 2),
        "total_pl": round(total_pl, 2),
        "total_pl_pct": round(total_pl_pct, 2),
        "etf_allocation_pct": round(etf_allocation_pct, 1),
        "stock_allocation_pct": round(stock_allocation_pct, 1),
        "num_positions": len(positions),
        "top_5_winners": top_5_winners,
        "top_5_losers": top_5_losers,
        "sector_breakdown": sector_breakdown,
        "cash_available": round(cash_available, 2),
        "daily_change_pct": daily_change_pct,
        "positions": positions,
        "top_candidates": top_candidates,
    }


def _restore_portfolio_from_snapshot():
    """Restore portfolio from latest snapshot on startup (REST-01).

    Loads the most recent snapshot and populates _session["portfolio"] and
    _session["portfolio_time"]. Handles:
    - Missing snapshot (D-13): logs info, returns silently
    - Old-format snapshot with portfolio_data=None (D-12): logs warning, skips restore
    - Valid snapshot: restores portfolio under _session_lock
    """
    snapshot = load_latest_snapshot()
    if snapshot is None:
        logger.info("No snapshot found on startup — starting fresh")
        return

    portfolio_data = snapshot.get("portfolio_data")
    if portfolio_data is None:
        # D-12: Old-format snapshot without portfolio_data — treat as no snapshot
        logger.warning("Snapshot dated %s has no portfolio_data — skipping restore", snapshot["date"])
        return

    with _session_lock:
        _session["portfolio"] = portfolio_data
        _session["portfolio_time"] = datetime.now()

    logger.info("Portfolio restored from snapshot dated %s", snapshot["date"])


# Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Brokr starting up")
    try:
        yield
    except Exception as e:
        logger.error("Unhandled exception during request: %s", str(e))
    finally:
        _clear_session()
        logger.info("Brokr shutting down")


app = FastAPI(title="Brokr", lifespan=lifespan)


@app.on_event("startup")
async def on_startup():
    logger.info("Startup event fired")
    try:
        import socket
        socket.gethostbyname("google.com")
        logger.info("DNS resolution: OK")
    except Exception as e:
        logger.error("DNS resolution failed: %s", e)
    try:
        import app.snapshots
        logger.info("snapshots module: OK")
    except Exception as e:
        logger.error("snapshots import failed: %s", e)
    try:
        import app.market_data
        logger.info("market_data module: OK")
    except Exception as e:
        logger.error("market_data import failed: %s", e)
    try:
        import app.degiro_client
        logger.info("degiro_client module: OK")
    except Exception as e:
        logger.error("degiro_client import failed: %s", e)
    # REST-01: Restore portfolio from latest snapshot
    _restore_portfolio_from_snapshot()


# ─── Security Headers Middleware (SEC-06, D-08) ───
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net https://unpkg.com; style-src 'self' 'unsafe-inline'; font-src https://fonts.gstatic.com"
    return response


# ─── CORS Middleware (SEC-06, D-09) ───
cors_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")
allow_origins = cors_origins.split(",") if cors_origins else ["http://localhost:8000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization"],
)


# ─── API Models ───

class AuthRequest(BaseModel):
    username: str
    password: str
    otp: str | None = None


class SessionRequest(BaseModel):
    session_id: str
    int_account: int | None = None


# ─── Health ───

@app.get("/health")
async def health():
    return {"status": "ok"}


# ─── Auth ───

@app.post("/api/auth", dependencies=[Depends(verify_brok_token)])
async def auth(request: AuthRequest):
    """Authenticate with DeGiro. Credentials are discarded immediately after session establishment."""
    try:
        trading_api = DeGiroClient.authenticate(
            username=request.username,
            password=request.password,
            otp=request.otp,
        )
        with _session_lock:
            _session["trading_api"] = trading_api
            _session["session_time"] = datetime.now()
            _session["portfolio"] = None
            _session["portfolio_time"] = None

        return {"status": "authenticated"}

    except ConnectionError as e:
        raise HTTPException(status_code=401, detail="Authentication failed")
    except Exception as e:
        logger.error("Auth error: %s", str(e))
        raise HTTPException(status_code=500, detail="Authentication failed")


@app.post("/api/session", dependencies=[Depends(verify_brok_token)])
async def session_auth(request: SessionRequest):
    """Authenticate using an existing DeGiro session ID from browser cookies.

    Useful when DeGiro blocks programmatic login and you extract the session
    manually from your browser (DevTools → Application → Cookies).
    """
    try:
        trading_api = DeGiroClient.from_session_id(
            request.session_id,
            int_account=request.int_account,
        )
        with _session_lock:
            _session["trading_api"] = trading_api
            _session["session_time"] = datetime.now()
            _session["portfolio"] = None
            _session["portfolio_time"] = None

        return {"status": "authenticated"}

    except ConnectionError as e:
        raise HTTPException(status_code=401, detail="Session authentication failed")
    except Exception as e:
        logger.error("Session auth error: %s", str(e))
        raise HTTPException(status_code=500, detail="Session authentication failed")


# ─── Portfolio ───

@app.get("/api/portfolio", dependencies=[Depends(verify_brok_token)])
async def get_portfolio():
    """Return full portfolio with all computed metrics.

    Serves cached portfolio even if the DeGiro session has expired.
    Only requires a live session for the initial fetch.
    """
    with _session_lock:
        portfolio = _session["portfolio"]
        if portfolio is not None:
            return portfolio

        # No cached portfolio — need active session to fetch
        if not _is_session_valid():
            raise HTTPException(
                status_code=401,
                detail="Session expired or not authenticated. Please reconnect via the UI.",
            )
        trading_api = _session["trading_api"]

    try:
        # Fetch raw portfolio from DeGiro
        raw = DeGiroClient.fetch_portfolio(trading_api)

        # Enrich with yfinance data
        positions = await asyncio.to_thread(enrich_positions, raw)

        # Compute portfolio weights
        positions = compute_portfolio_weights(positions)

        # Compute scores
        positions = compute_scores(positions)

        # Build summary
        portfolio = _build_portfolio_summary(positions, raw.get("cash_available", 0))

        # Compute health alerts from the portfolio summary data
        health_alerts = compute_health_alerts({
            "positions": portfolio["positions"],
            "sector_breakdown": portfolio.get("sector_breakdown", {}),
            "etf_allocation_pct": portfolio.get("etf_allocation_pct", 0),
            "stock_allocation_pct": portfolio.get("stock_allocation_pct", 0),
        })
        portfolio["health_alerts"] = health_alerts

        # Save snapshot as side effect — benchmark indexed to 100 at portfolio start (D-04)
        try:
            date_str = datetime.now().strftime("%Y-%m-%d")
            snapshots = load_snapshots()

            if snapshots:
                # Compute benchmark return relative to first snapshot date
                first_date = snapshots[0]["date"]
                today_str = datetime.now().strftime("%Y-%m-%d")
                series = fetch_benchmark_series(first_date, today_str)
                if series:
                    # benchmark_value is indexed to 100 at first snapshot
                    benchmark_value = series[-1]["value"]
                    benchmark_return_pct = benchmark_value - 100.0
                else:
                    benchmark_value = snapshots[-1].get("benchmark_value", 100.0)
                    benchmark_return_pct = snapshots[-1].get("benchmark_return_pct", 0.0)
            else:
                # First snapshot — benchmark starts at 100
                benchmark_value = 100.0
                benchmark_return_pct = 0.0

            save_snapshot(
                date_str,
                portfolio["total_value"],
                benchmark_value,
                benchmark_return_pct,
                portfolio,
            )
        except Exception as e:
            logger.warning("Snapshot save failed (non-blocking): %s", str(e))

        with _session_lock:
            _session["portfolio"] = portfolio
            _session["portfolio_time"] = datetime.now()

        return portfolio

    except Exception as e:
        logger.error("Portfolio fetch error: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch portfolio")


@app.get("/api/portfolio-raw", dependencies=[Depends(verify_brok_token)])
async def get_portfolio_raw():
    """Return raw portfolio from DeGiro without yfinance enrichment.

    Fast (~2-3s) — useful for showing basic data immediately while
    the full enrichment happens in the background.
    """
    with _session_lock:
        # If we already have enriched data, return that
        portfolio = _session["portfolio"]
        if portfolio is not None:
            return portfolio

        if not _is_session_valid():
            raise HTTPException(
                status_code=401,
                detail="Session expired or not authenticated. Please reconnect via the UI.",
            )
        trading_api = _session["trading_api"]

    try:
        raw = DeGiroClient.fetch_portfolio(trading_api)
        portfolio = _build_raw_portfolio_summary(
            raw.get("positions", []),
            raw.get("cash_available", 0),
        )
        return portfolio

    except Exception as e:
        logger.error("Raw portfolio fetch error: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch portfolio")


# ─── Hermes Context ───

@app.get("/api/hermes-context", dependencies=[Depends(verify_brok_token)])
async def hermes_context():
    """Return structured context for Hermes AI agent.

    Works with cached portfolio even if the DeGiro session has expired.
    Benchmark and attribution data can be served from snapshots alone.
    """
    with _session_lock:
        portfolio = _session["portfolio"]

    return build_hermes_context(portfolio if portfolio is not None else {})


# ─── Logout ───

@app.post("/api/logout", dependencies=[Depends(verify_brok_token)])
async def logout():
    """Clear in-memory session and portfolio data."""
    with _session_lock:
        _clear_session()
    return {"status": "logged_out"}


# ─── Benchmark ───

@app.get("/api/benchmark", dependencies=[Depends(verify_brok_token)])
async def get_benchmark():
    """Return benchmark comparison data: snapshots, indexed series, and attribution.

    Benchmark data is fetched fresh from yfinance — NOT stored in snapshots (D-07).
    """
    snapshots = load_snapshots()
    if not snapshots:
        return {"snapshots": [], "benchmark_series": [], "attribution": [], "message": "No snapshots yet"}

    # Get date range from snapshots
    first_date = snapshots[0]["date"]
    today = datetime.now().strftime("%Y-%m-%d")

    # Fetch benchmark series (fresh, not stored)
    benchmark_series = fetch_benchmark_series(first_date, today)

    # Get current portfolio for attribution
    with _session_lock:
        portfolio = _session["portfolio"]

    if portfolio is None:
        return {
            "snapshots": snapshots,
            "benchmark_series": benchmark_series,
            "attribution": [],
            "message": "No portfolio loaded",
        }

    # Compute attribution using current benchmark return (from last snapshot)
    latest_benchmark_return = snapshots[-1].get("benchmark_return_pct", 0) if snapshots else 0
    attribution = compute_attribution(portfolio.get("positions", []), latest_benchmark_return)

    return {
        "snapshots": snapshots,
        "benchmark_series": benchmark_series,
        "attribution": attribution,
    }


# ─── Static Files ───

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def root():
    return FileResponse("app/static/index.html")
