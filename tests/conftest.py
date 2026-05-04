import sys
sys.path.insert(0, 'app')

import pytest
from unittest.mock import patch, MagicMock
from contextlib import asynccontextmanager
from fastapi.testclient import TestClient
import market_data


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Clear rate limiter state before each test to prevent cross-test pollution."""
    import app.rate_limiter as rl
    with rl._store_lock:
        rl._rate_limit_store.clear()
    yield


@pytest.fixture
def with_auth_env(monkeypatch):
    """Set required env vars for integration tests."""
    monkeypatch.setenv("APP_PASSWORD", "testpassword123")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-hmac")
    monkeypatch.setenv("BROKR_AUTH_TOKEN", "test-bearer-token-12345")
    monkeypatch.setenv("DEBUG", "false")
    yield
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("BROKR_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("DEBUG", raising=False)


@pytest.fixture
def client(with_auth_env):
    """Return TestClient with env vars set and lifespan overridden."""
    from app.main import app

    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    app.router.lifespan_context = noop_lifespan
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(autouse=True)
def fx_rate_cache():
    """Clear the FX rate cache before and after each test."""
    market_data._fx_cache.clear()
    yield market_data._fx_cache
    market_data._fx_cache.clear()


@pytest.fixture
def mock_yfinance_ticker():
    """Return a MagicMock ticker with controlled data for history() and info."""
    mock_ticker = MagicMock()
    mock_info = {
        "sector": "Technology",
        "country": "United States",
        "fiftyTwoWeekHigh": 180.0,
        "fiftyTwoWeekLow": 120.0,
        "trailingPE": 25.5,
    }
    mock_ticker.info = mock_info
    return mock_ticker


@pytest.fixture
def sample_position():
    """Return a minimal valid position dict."""
    return {
        "id": "123",
        "product_id": 123,
        "name": "Apple Inc",
        "isin": "US0378331005",
        "symbol": "AAPL",
        "currency": "USD",
        "asset_type": "STOCK",
        "quantity": 10.0,
        "avg_buy_price": 150.0,
        "current_price": 170.0,
        "current_value": 1700.0,
        "unrealized_pl": 200.0,
        "unrealized_pl_pct": 13.33,
        "sector": "Technology",
        "country": "United States",
    }


@pytest.fixture
def sample_etf_position():
    """Return a minimal ETF position dict."""
    return {
        "id": "456",
        "product_id": 456,
        "name": "Vanguard S&P 500 ETF",
        "isin": "IE00B4L5Y983",
        "symbol": "VUSA",
        "currency": "USD",
        "asset_type": "ETF",
        "quantity": 5.0,
        "avg_buy_price": 80.0,
        "current_price": 85.0,
        "current_value": 425.0,
        "unrealized_pl": 25.0,
        "unrealized_pl_pct": 6.25,
    }


@pytest.fixture
def mock_auth_env(monkeypatch):
    """Set required env vars for auth tests."""
    monkeypatch.setenv("APP_PASSWORD", "testpassword123")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-hmac")
    yield
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)


@pytest.fixture
def auth_module(mock_auth_env):
    """Return auth module with test env vars set."""
    import importlib
    import app.auth as auth
    importlib.reload(auth)
    return auth


@pytest.fixture
def sample_token(auth_module):
    """Return a valid HMAC-signed token for testing."""
    import time
    token, _ = auth_module.make_session_cookie()
    return token
