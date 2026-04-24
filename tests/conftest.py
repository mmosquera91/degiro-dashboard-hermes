import pytest
from unittest.mock import patch, MagicMock
import market_data


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
