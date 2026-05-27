"""Indexa Capital API client — read-only, token-in-header.

Indexa Capital is a Spanish robo-advisor. This client wraps the v1 REST API
at https://api.indexacapital.com using a personal access token passed via the
X-AUTH-TOKEN header. On 401, attempts a one-shot token refresh via
GET /auth/refresh-token before propagating the error.
"""

import asyncio
import logging
import os
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

INDEXA_BASE_URL = "https://api.indexacapital.com"
_CACHE_TTL = 300.0  # 5 minutes — Indexa portfolios change infrequently


class IndexaClient:
    """Async HTTP client for Indexa Capital read-only endpoints."""

    def __init__(self, base_url: str = INDEXA_BASE_URL) -> None:
        self._base_url = base_url
        self._token: Optional[str] = os.getenv("INDEXA_API_TOKEN") or None
        self._account_number: Optional[str] = os.getenv("INDEXA_ACCOUNT") or None
        self._client = httpx.AsyncClient(base_url=base_url, timeout=30.0)
        self._lock = asyncio.Lock()
        self._cache: dict[str, tuple[Any, float]] = {}

    def _headers(self) -> dict[str, str]:
        if not self._token:
            raise RuntimeError("INDEXA_API_TOKEN is not configured")
        return {
            "X-AUTH-TOKEN": self._token,
            "Accept": "application/json",
        }

    async def _refresh_token(self) -> None:
        """GET /auth/refresh-token with current token; update self._token from response."""
        response = await self._client.get(
            "/auth/refresh-token",
            headers=self._headers(),
        )
        response.raise_for_status()
        data = response.json()
        new_token = data.get("token") or data.get("jwt") or data.get("access_token")
        if not new_token:
            raise RuntimeError("Indexa refresh-token response did not contain a token")
        self._token = new_token
        logger.info("Indexa token refreshed")

    async def _request(self, method: str, path: str) -> Any:
        """Issue a request; on 401 refresh the token once and retry."""
        response = await self._client.request(method, path, headers=self._headers())
        if response.status_code == 401:
            logger.info("Indexa returned 401 — refreshing token and retrying")
            await self._refresh_token()
            response = await self._client.request(method, path, headers=self._headers())
        response.raise_for_status()
        return response.json()

    async def _ensure_account(self) -> str:
        """Return the cached account number; auto-detect via /users/me if missing."""
        if self._account_number:
            return self._account_number
        async with self._lock:
            if self._account_number:
                return self._account_number
            data = await self._request("GET", "/users/me")
            accounts = data.get("accounts") if isinstance(data, dict) else None
            if not accounts:
                raise RuntimeError("Indexa /users/me returned no accounts")
            first = accounts[0]
            account_number = first.get("account_number") if isinstance(first, dict) else None
            if not account_number:
                raise RuntimeError("Indexa /users/me account entry missing account_number")
            self._account_number = account_number
            logger.info("Indexa account auto-detected")
            return self._account_number

    def _cached(self, key: str) -> Any | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        value, ts = entry
        if time.monotonic() - ts >= _CACHE_TTL:
            return None
        return value

    def _store(self, key: str, value: Any) -> None:
        self._cache[key] = (value, time.monotonic())

    async def get_portfolio(self) -> dict[str, Any]:
        cached = self._cached("portfolio")
        if cached is not None:
            return cached
        account = await self._ensure_account()
        data = await self._request("GET", f"/accounts/{account}/portfolio")
        self._store("portfolio", data)
        return data

    async def get_performance(self) -> dict[str, Any]:
        cached = self._cached("performance")
        if cached is not None:
            return cached
        account = await self._ensure_account()
        data = await self._request("GET", f"/accounts/{account}/performance")
        self._store("performance", data)
        return data

    async def get_cash_transactions(self) -> list:
        cached = self._cached("cash_transactions")
        if cached is not None:
            return cached
        account = await self._ensure_account()
        data = await self._request("GET", f"/accounts/{account}/cash-transactions")
        self._store("cash_transactions", data)
        return data

    async def get_user_info(self) -> dict[str, Any]:
        cached = self._cached("user_info")
        if cached is not None:
            return cached
        data = await self._request("GET", "/users/me")
        self._store("user_info", data)
        return data
