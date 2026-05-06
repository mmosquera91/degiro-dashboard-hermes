"""In-memory IP-based rate limiter for brute-force protection."""

import threading
import time
from fastapi import Request, HTTPException

# Rate limiter state: IP -> list of request timestamps
_rate_limit_store: dict[str, list[float]] = {}
_store_lock = threading.Lock()

# Config
MAX_ATTEMPTS = 5
WINDOW_SECONDS = 60.0


def _get_client_ip(request: Request) -> str:
    """Extract client IP, preferring X-Forwarded-For if behind a proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _clean_old_timestamps(timestamps: list[float], now: float) -> list[float]:
    """Remove timestamps outside the window."""
    return [ts for ts in timestamps if now - ts < WINDOW_SECONDS]


def check_rate_limit(request: Request) -> str:
    """FastAPI dependency that enforces rate limiting on auth endpoints.

    Returns the client IP on success. Raises HTTPException 429 if limit exceeded.
    """
    ip = _get_client_ip(request)
    now = time.time()

    with _store_lock:
        if ip in _rate_limit_store:
            _rate_limit_store[ip] = _clean_old_timestamps(_rate_limit_store[ip], now)

        count = len(_rate_limit_store.get(ip, []))

        if count >= MAX_ATTEMPTS:
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests. Limit is {MAX_ATTEMPTS} attempts per {int(WINDOW_SECONDS)} seconds.",
            )

        _rate_limit_store.setdefault(ip, []).append(now)

    return ip