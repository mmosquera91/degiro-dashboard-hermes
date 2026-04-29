"""Brokr — FastAPI application with all routes."""

import asyncio
import hmac
import logging
import os
import threading
from pathlib import Path
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .degiro_client import DeGiroClient
from .market_data import enrich_positions, get_fx_rate, _sanitize_floats, clear_symbol_cache, audit_symbol_cache
from .scoring import compute_scores, compute_portfolio_weights, get_top_candidates
from .context_builder import build_hermes_context
from .health_checks import compute_health_alerts
from .snapshots import save_snapshot, load_snapshots, load_latest_snapshot, fetch_benchmark_series, compute_attribution, SNAPSHOT_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# In-memory session cache
_session = {
    "trading_api": None,
    "session_time": None,
    "portfolio": None,
    "portfolio_time": None,
    "last_enriched_at": None,
    "enriching": False,
}
_session_lock = threading.Lock()

# Global operation lock — prevents concurrent enrichment, Update Prices, and DeGiro sync
_operation_lock = threading.Event()

def _is_operation_locked():
    return _operation_lock.is_set()

def _acquire_operation_lock():
    """Attempt to acquire the operation lock. Returns True if acquired, False if already held."""
    return not _operation_lock.is_set()

def _release_operation_lock():
    _operation_lock.clear()

# Benchmark cache (1-hour TTL)
_benchmark_cache: dict = {"series": None, "attribution": None}
_benchmark_cache_time: float = 0.0
_BENCHMARK_TTL: int = 3600  # 1 hour


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


def _is_prices_current() -> bool:
    """Returns True if yfinance enrichment ran today."""
    if _session["last_enriched_at"] is None:
        return False
    return _session["last_enriched_at"].date() == datetime.now().date()


def _clear_session():
    """Clear all session data."""
    _session["trading_api"] = None
    _session["session_time"] = None
    _session["portfolio"] = None
    _session["portfolio_time"] = None
    _session["last_enriched_at"] = None
    _session["enriching"] = False


def _build_raw_portfolio_summary(positions: list, cash_available: float) -> dict:
    """Build a minimal portfolio summary from raw DeGiro data (no yfinance)."""
    # Work on a copy so the caller's list is not mutated
    positions_copy = [p.copy() for p in positions]

    total_value = sum(p.get("current_value", 0) or 0 for p in positions_copy)
    total_invested = sum((p.get("avg_buy_price", 0) or 0) * p.get("quantity", 0) for p in positions_copy)
    unrealized_pl_total = total_value - total_invested
    unrealized_pl_total_pct = (unrealized_pl_total / total_invested * 100) if total_invested > 0 else 0

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
        "date": datetime.now(timezone.utc).isoformat(),
        "total_value": round(total_value, 2),
        "total_value_eur": round(total_value, 2),
        "total_invested": round(total_invested, 2),
        # DeGiro does not expose realized gains via API — total_pl = unrealized only
        "unrealized_pl_total": round(unrealized_pl_total, 2),
        "unrealized_pl_total_pct": round(unrealized_pl_total_pct, 2),
        "true_total_pl": None,
        "true_total_pl_pct": None,
        "total_deposit_withdrawal": 0.0,
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
        "top5_holdings": [
            {"ticker": p.get("symbol") or p.get("name", ""), "weight": round(p.get("weight", 0) or 0, 1)}
            for p in sorted(
                [{"symbol": p.get("symbol") or p.get("name", ""), "weight": p.get("weight", 0) or 0} for p in positions_copy],
                key=lambda x: x["weight"], reverse=True
            )[:5]
        ],
    }


def _build_portfolio_summary(positions: list, cash_available: float, raw: dict | None = None) -> dict:
    """Build the full portfolio summary from enriched, scored positions."""
    total_value = sum(p.get("current_value_eur", 0) or 0 for p in positions)
    total_invested = sum((p.get("avg_buy_price", 0) or 0) * p.get("quantity", 0) for p in positions)
    unrealized_pl_total = total_value - total_invested
    unrealized_pl_total_pct = (unrealized_pl_total / total_invested * 100) if total_invested > 0 else 0

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

    # True P&L = all position value + cash - total net deposits ever made
    # Does NOT include fees separately — fees already reduce cash balance
    total_deposit_withdrawal = raw.get("total_deposit_withdrawal", 0.0) if raw else 0.0
    if total_deposit_withdrawal > 0:
        true_total_pl = round(total_value + (cash_available or 0) - total_deposit_withdrawal, 2)
        true_total_pl_pct = round((true_total_pl / total_deposit_withdrawal) * 100, 2)
    else:
        true_total_pl = None
        true_total_pl_pct = None

    return {
        "date": datetime.now(timezone.utc).isoformat(),
        "total_value": round(total_value, 2),
        "total_value_eur": round(total_value, 2),
        "total_invested": round(total_invested, 2),
        # DeGiro does not expose realized gains via API — total_pl = unrealized only
        "unrealized_pl_total": round(unrealized_pl_total, 2),
        "unrealized_pl_total_pct": round(unrealized_pl_total_pct, 2),
        "true_total_pl": true_total_pl,
        "true_total_pl_pct": true_total_pl_pct,
        "total_deposit_withdrawal": round(total_deposit_withdrawal, 2),
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
        "top5_holdings": [
            {"ticker": p["ticker"], "weight": round(p["weight_pct"], 1)}
            for p in sorted(
                [{"ticker": p.get("symbol") or p.get("name", ""), "weight_pct": p.get("weight", 0) or 0} for p in positions],
                key=lambda x: x.get("weight_pct") or 0, reverse=True
            )[:5]
        ],
    }


def _sanitize_floats_deep(portfolio: dict) -> dict:
    """Apply _sanitize_floats recursively to all positions in a portfolio dict."""
    if "positions" in portfolio:
        portfolio["positions"] = [_sanitize_floats(p) for p in portfolio["positions"]]
    return portfolio


def _save_snapshot_for_portfolio(portfolio: dict) -> None:
    """Save portfolio snapshot and invalidate benchmark cache. Called as a side effect after enrichment."""
    try:
        date_str = datetime.now().strftime("%Y-%m-%d")
        snapshots = load_snapshots()

        if snapshots:
            first_date = snapshots[0]["date"]
            today_str = datetime.now().strftime("%Y-%m-%d")
            series = fetch_benchmark_series(first_date, today_str)
            if series:
                benchmark_value = series[-1]["value"]
                benchmark_return_pct = benchmark_value - 100.0
            else:
                benchmark_value = snapshots[-1].get("benchmark_value", 100.0)
                benchmark_return_pct = snapshots[-1].get("benchmark_return_pct", 0.0)
        else:
            benchmark_value = 100.0
            benchmark_return_pct = 0.0

        safe_portfolio = _sanitize_floats_deep(portfolio)
        save_snapshot(
            date_str,
            safe_portfolio["total_value"],
            benchmark_value,
            benchmark_return_pct,
            safe_portfolio,
        )
    except Exception as e:
        logger.warning("Snapshot save failed (non-blocking): %s", str(e))


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
        logger.error("No snapshot found on startup — portfolio NOT restored; dashboard will show empty state")
        return

    # Verify snapshot file still exists on disk (gap: restore succeeded but file gone)
    latest_path = Path(SNAPSHOT_DIR) / f"{snapshot['date']}.json"
    if not latest_path.exists():
        logger.error("Snapshot file %s not found on disk — restore aborted", latest_path)
        return

    portfolio_data = snapshot.get("portfolio_data")
    if portfolio_data is None:
        # D-12: Old-format snapshot without portfolio_data — treat as no snapshot
        logger.warning("Snapshot dated %s has no portfolio_data — skipping restore", snapshot["date"])
        return

# Sanitize any inf/nan floats baked into old snapshots before restoring
    if "positions" in portfolio_data:
        portfolio_data["positions"] = [_sanitize_floats(p) for p in portfolio_data["positions"]]
        try:
            portfolio_data["positions"] = compute_portfolio_weights(portfolio_data["positions"])
            portfolio_data["positions"] = compute_scores(portfolio_data["positions"])
            logger.info("Re-scored %d restored positions from snapshot", len(portfolio_data["positions"]))
        except Exception as e:
            logger.warning("Could not re-score restored positions: %s", e)
        try:
            portfolio_data["health_alerts"] = compute_health_alerts(portfolio_data)
        except Exception as e:
            logger.warning("Health alerts computation failed on restore: %s", e)
            portfolio_data["health_alerts"] = []
    with _session_lock:
        _session["portfolio"] = portfolio_data
        _session["portfolio_time"] = datetime.now()
        snap_date = snapshot.get("date")  # "YYYY-MM-DD"
        try:
            _session["last_enriched_at"] = datetime.strptime(snap_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            _session["last_enriched_at"] = None

    logger.info("Portfolio restored from snapshot dated %s", snapshot["date"])


# Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Brokr starting up")
    try:
        # REST-01: Restore portfolio from latest snapshot before accepting requests
        _restore_portfolio_from_snapshot()
        audit_symbol_cache()
        # Daily auto-enrichment at ~08:00 local time
        asyncio.create_task(_daily_enrichment_loop())
        yield
    except Exception as e:
        logger.error("Unhandled exception during request: %s", str(e))
    finally:
        _clear_session()
        logger.info("Brokr shutting down")


async def _daily_enrichment_loop():
    """Re-enrich portfolio once per day at approximately 08:00 local time."""
    while True:
        now = datetime.now()
        next_run = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        await asyncio.sleep((next_run - now).total_seconds())
        if _session.get("portfolio") and _session["portfolio"].get("positions"):
            logger.info("Daily enrichment task running")
            try:
                await asyncio.to_thread(_do_enrich_session)
            except Exception as e:
                logger.warning("Daily enrichment failed: %s", e)


app = FastAPI(title="Brokr", lifespan=lifespan)

# Jinja2 templates for rendered pages (login)
templates = Jinja2Templates(directory="app/templates")


# ─── Auth Middleware ───
@app.middleware("http")
async def check_session_cookie(request: Request, call_next):
    """Redirect unauthenticated requests to /login. Exempts /login, /static/*, and /health."""
    path = request.url.path
    if (
        path == "/login"
        or path.startswith("/static/")
        or path == "/health"
        or path == "/logout"
    ):
        return await call_next(request)

    cookie_value = request.cookies.get("brokr_session")
    if not cookie_value:
        return RedirectResponse(url="/login", status_code=303)

    from .auth import verify_session_cookie
    if not verify_session_cookie(cookie_value):
        response = RedirectResponse(url="/login", status_code=303)
        response.delete_cookie("brokr_session")
        return response

    return await call_next(request)


@app.on_event("startup")
async def on_startup():
    logger.info("Startup event fired")
    try:
        import socket
        await asyncio.to_thread(socket.gethostbyname, "google.com")
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
    # Snapshot restore moved to lifespan.__aenter__() for FastAPI 0.100+ compatibility


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
    if _is_operation_locked():
        raise HTTPException(status_code=409, detail="Another operation is already running")

    with _session_lock:
        portfolio = _session["portfolio"]
        if portfolio is not None:
            return portfolio

        # No cached portfolio — need active session to fetch
        if _session["trading_api"] is None:
            raise HTTPException(
                status_code=401,
                detail="Session expired or not authenticated. Please reconnect via the UI.",
            )
        if not _is_session_valid():
            raise HTTPException(
                status_code=401,
                detail="Session expired. Please refresh your connection via the UI.",
            )
        trading_api = _session["trading_api"]

    try:
        # Fetch raw portfolio from DeGiro
        raw = DeGiroClient.fetch_portfolio(trading_api)

        # Enrich with yfinance data
        positions = await asyncio.to_thread(enrich_positions, raw)

        # Compute portfolio weights
        positions = compute_portfolio_weights(positions)

        # Compute scores (defensive — scoring can fail on edge cases)
        try:
            positions = compute_scores(positions)
        except Exception as e:
            logger.warning("Score computation failed: %s", str(e))

        # Build summary
        portfolio = _build_portfolio_summary(positions, raw.get("cash_available", 0), raw)

        # Compute health alerts from the portfolio summary data (defensive)
        try:
            health_alerts = compute_health_alerts({
                "positions": portfolio["positions"],
                "sector_breakdown": portfolio.get("sector_breakdown", {}),
                "etf_allocation_pct": portfolio.get("etf_allocation_pct", 0),
                "stock_allocation_pct": portfolio.get("stock_allocation_pct", 0),
            })
            portfolio["health_alerts"] = health_alerts
        except Exception as e:
            logger.warning("Health alerts computation failed: %s", str(e))
            portfolio["health_alerts"] = []

        # Save snapshot as side effect — benchmark indexed to 100 at portfolio start (D-04)
        try:
            _save_snapshot_for_portfolio(portfolio)
        except Exception as e:
            logger.warning("Snapshot save failed (non-blocking): %s", str(e))

        with _session_lock:
            _session["portfolio"] = portfolio
            _session["portfolio_time"] = datetime.now(timezone.utc)
            _session["last_enriched_at"] = datetime.now(timezone.utc)
            portfolio["last_enriched_at"] = _session["last_enriched_at"].isoformat() if _session["last_enriched_at"] else None

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
    if _is_operation_locked():
        raise HTTPException(status_code=409, detail="Another operation is already running")

    with _session_lock:
        # If we already have enriched data, return that
        portfolio = _session["portfolio"]
        if portfolio is not None:
            # Always compute snapshot-based daily change on top of cached data
            snaps = load_snapshots()
            today_str = datetime.now().strftime("%Y-%m-%d")
            yesterday_snap = None
            for s in reversed(snaps):
                if s["date"][:10] < today_str:
                    yesterday_snap = s
                    break
            if yesterday_snap and yesterday_snap.get("total_value_eur"):
                prev = yesterday_snap["total_value_eur"]
                curr = portfolio.get("total_value_eur")
                if curr is not None and prev != 0:
                    portfolio["daily_change_pct"] = round((curr - prev) / prev * 100, 2)
                    portfolio["daily_change_eur"] = round(curr - prev, 2)
                else:
                    portfolio["daily_change_pct"] = None
                    portfolio["daily_change_eur"] = None
            else:
                portfolio["daily_change_pct"] = None
                portfolio["daily_change_eur"] = None
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
        portfolio["last_enriched_at"] = _session["last_enriched_at"].isoformat() if _session["last_enriched_at"] else None

        # snapshot-based daily change
        snaps = load_snapshots()
        today_str = datetime.now().strftime("%Y-%m-%d")
        yesterday_snap = None
        for s in reversed(snaps):
            if s["date"][:10] < today_str:
                yesterday_snap = s
                break
        if yesterday_snap and yesterday_snap.get("total_value_eur"):
            prev = yesterday_snap["total_value_eur"]
            curr = portfolio["total_value_eur"]
            portfolio["daily_change_pct"] = round((curr - prev) / prev * 100, 2)
            portfolio["daily_change_eur"] = round(curr - prev, 2)
        else:
            portfolio["daily_change_pct"] = None
            portfolio["daily_change_eur"] = None

        return portfolio

    except Exception as e:
        logger.error("Raw portfolio fetch error: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch portfolio")


def _do_enrich_session():
    """Re-enrich the current portfolio with fresh yfinance data.

    Called by both the /api/refresh-prices endpoint (via thread) and the
    daily enrichment loop (via asyncio.to_thread). Does NOT call DeGiro.
    """
    try:
        _operation_lock.set()
        with _session_lock:
            _session["enriching"] = True

        with _session_lock:
            positions = [p.copy() for p in _session["portfolio"]["positions"]]
            cash = _session["portfolio"].get("cash_available", 0)
            raw_portfolio = _session["portfolio"]

        enriched = enrich_positions({"positions": positions})
        enriched = compute_portfolio_weights(enriched)
        enriched = compute_scores(enriched)
        summary = _build_portfolio_summary(enriched, cash, raw_portfolio)
        summary = _sanitize_floats_deep(summary)
        logger.info(f"[DIAG] DEGIRO REPORTED TOTAL: {summary.get('total_value_eur', 0):.2f} EUR")
        try:
            summary["health_alerts"] = compute_health_alerts(summary)
        except Exception as e:
            logger.warning("Health alerts computation failed in enrich: %s", e)
            summary["health_alerts"] = []

        now = datetime.now(timezone.utc)
        with _session_lock:
            summary["last_enriched_at"] = now.isoformat()
            _session["portfolio"] = summary
            _session["portfolio_time"] = now
            _session["last_enriched_at"] = now

        _save_snapshot_for_portfolio(summary)
    finally:
        _operation_lock.clear()
        with _session_lock:
            _session["enriching"] = False


@app.post("/api/refresh-prices", dependencies=[Depends(verify_brok_token)])
async def refresh_prices():
    """Re-enrich current portfolio positions with fresh yfinance data.

    Does not require a DeGiro session — works from snapshot-restored portfolio.
    Runs enrichment in a background thread and returns immediately.
    """
    if _is_operation_locked():
        raise HTTPException(status_code=409, detail="Another operation is already running")

    with _session_lock:
        portfolio = _session.get("portfolio")
    if not portfolio or not portfolio.get("positions"):
        raise HTTPException(status_code=400, detail="No portfolio loaded")

    thread = threading.Thread(target=_do_enrich_session, daemon=True)
    thread.start()
    return {"status": "enrichment_started"}


@app.get("/api/enrichment-status")
async def enrichment_status():
    """Return current enrichment state — no auth required, no financial data."""
    with _session_lock:
        enriching = _session.get("enriching", False)
        last_enriched_at = _session.get("last_enriched_at")
    return {
        "enriching": enriching,
        "last_enriched_at": last_enriched_at.isoformat() if last_enriched_at else None,
    }


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


# ─── Admin ───

@app.delete("/api/admin/symbol-cache", dependencies=[Depends(verify_brok_token)])
async def delete_symbol_cache():
    """Clear the symbol resolution cache.

    Use after yfinance upgrade or when per-stock metrics all show None due to
    a rate-limiting event that poisoned the cache with bare (unresolved) symbols.
    """
    cleared = clear_symbol_cache()
    logger.info("Symbol cache cleared: %d entries removed", cleared)
    return {"cleared": cleared}


@app.post("/api/admin/reload-overrides", dependencies=[Depends(verify_brok_token)])
async def reload_symbol_overrides():
    """Reload symbol_overrides.json from disk without restarting."""
    from app.market_data import _load_symbol_overrides
    _load_symbol_overrides()
    return {"status": "ok"}


# ─── Benchmark ───

@app.get("/api/benchmark", dependencies=[Depends(verify_brok_token)])
async def get_benchmark():
    """Return benchmark comparison data: snapshots, indexed series, and attribution.

    Benchmark data is fetched fresh from yfinance — NOT stored in snapshots (D-07).
    """
    import time as _time
    global _benchmark_cache, _benchmark_cache_time

    snapshots = load_snapshots()
    if not snapshots:
        return {"snapshots": [], "benchmark_series": [], "attribution": [], "message": "No snapshots yet"}

    # Check cache before hitting yfinance (only series cached, snapshots always fresh)
    if _benchmark_cache["series"] is not None and \
            _time.time() - _benchmark_cache_time < _BENCHMARK_TTL:
        return {
            "snapshots": snapshots,   # always fresh from disk
            "benchmark_series": _benchmark_cache["series"],
            "attribution": _benchmark_cache["attribution"],
        }

    # Get date range from snapshots
    first_date = snapshots[0]["date"]
    today = datetime.now().strftime("%Y-%m-%d")

    # Fetch benchmark series (fresh, not stored)
    benchmark_series = fetch_benchmark_series(first_date, today)
    if not benchmark_series and _benchmark_cache["series"]:
        # Rate limited — serve stale series rather than returning empty
        logger.warning("Benchmark fetch returned empty — serving stale cache")
        benchmark_series = _benchmark_cache["series"]

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

    # Populate cache (series + attribution only; snapshots always served fresh)
    _benchmark_cache["series"] = benchmark_series
    _benchmark_cache["attribution"] = attribution
    _benchmark_cache_time = _time.time()

    return {
        "snapshots": snapshots,
        "benchmark_series": benchmark_series,
        "attribution": attribution,
    }


# ─── Snapshots ───

@app.get("/api/snapshots", dependencies=[Depends(verify_brok_token)])
async def list_snapshots():
    """List all snapshots (lightweight — no portfolio_data payload)."""
    snapshots = load_snapshots()
    return [
        {
            "date": s["date"],
            "total_value_eur": s.get("total_value_eur"),
            "benchmark_value": s.get("benchmark_value"),
            "benchmark_return_pct": s.get("benchmark_return_pct"),
            "has_portfolio_data": s.get("portfolio_data") is not None,
        }
        for s in snapshots
    ]


@app.delete("/api/snapshots/{date_str}", dependencies=[Depends(verify_brok_token)])
async def delete_snapshot(date_str: str):
    """Delete a snapshot file by date string (YYYY-MM-DD)."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    file_path = Path(SNAPSHOT_DIR) / f"{date_str}.json"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Snapshot not found")

    # Prevent deleting the only remaining snapshot
    all_snapshots = load_snapshots()
    if len(all_snapshots) <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the only snapshot")

    file_path.unlink()
    global _benchmark_cache_time
    _benchmark_cache_time = 0.0  # invalidate benchmark cache
    logger.info("Snapshot deleted: %s", date_str)
    return {"deleted": date_str}


@app.post("/api/snapshots/save", dependencies=[Depends(verify_brok_token)])
async def save_snapshot_now():
    """Manually trigger a snapshot save for the current portfolio."""
    with _session_lock:
        portfolio = _session.get("portfolio")
    if not portfolio:
        raise HTTPException(status_code=400, detail="No portfolio loaded")
    try:
        _save_snapshot_for_portfolio(portfolio)
        return {"saved": datetime.now().strftime("%Y-%m-%d")}
    except Exception as e:
        logger.warning("Manual snapshot save failed: %s", e)
        raise HTTPException(status_code=500, detail="Snapshot save failed")


# ─── Login / Logout ───

@app.get("/login")
async def login_get(request: Request):
    """Serve the login page."""
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login_post(request: Request):
    """Authenticate: check password, set signed session cookie on success."""
    form = await request.form()
    password = form.get("password", "")

    app_password = os.getenv("APP_PASSWORD", "")
    secret_key = os.getenv("SECRET_KEY", "")

    if not app_password or not secret_key:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Server misconfigured — APP_PASSWORD not set"},
        )

    if password == app_password:
        from .auth import make_session_cookie
        token, cookie_kwargs = make_session_cookie()
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie("brokr_session", token, **cookie_kwargs)
        return response

    return RedirectResponse(url="/login?failedattempt=yes", status_code=303)


@app.get("/logout")
async def logout():
    """Clear session cookie and redirect to /login."""
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(
        "brokr_session",
        path="/",
        httponly=True,
        samesite="lax",
    )
    return response


# ─── Static Files ───

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def root():
    return FileResponse("app/static/index.html")
