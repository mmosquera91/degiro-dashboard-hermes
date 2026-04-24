"""Unit tests for market_data.py — get_fx_rate, compute_rsi, enrich_position."""

import sys
sys.path.insert(0, 'app')

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

from market_data import get_fx_rate, compute_rsi, enrich_position


class TestGetFxRate:
    def test_get_fx_rate_same_currency(self):
        """EUR->EUR returns 1.0 without cache lookup."""
        with patch("market_data.yf.Ticker") as mock_ticker:
            result = get_fx_rate("EUR", "EUR")
            assert result == 1.0
            mock_ticker.assert_not_called()  # no yfinance call for same currency

    def test_get_fx_rate_cache_hit(self, fx_rate_cache):
        """Second call returns cached value."""
        fx_rate_cache["USDEUR"] = 0.92  # seed cache
        with patch("market_data.yf.Ticker") as mock_ticker:
            result = get_fx_rate("USD", "EUR")
            assert result == 0.92
            mock_ticker.assert_not_called()  # no yfinance call, cache hit

    def test_get_fx_rate_yf_failure(self, fx_rate_cache):
        """yfinance fails, returns 1.0 fallback."""
        with patch("market_data.yf.Ticker") as mock_ticker:
            mock_instance = MagicMock()
            mock_instance.history.return_value.empty = True  # no data
            mock_ticker.return_value = mock_instance
            result = get_fx_rate("USD", "EUR")
            assert result == 1.0  # fallback

    def test_get_fx_rate_direct_lookup(self, fx_rate_cache):
        """yfinance returns valid rate."""
        with patch("market_data.yf.Ticker") as mock_ticker:
            mock_instance = MagicMock()
            mock_hist = MagicMock()
            mock_hist.empty = False
            # hist["Close"] returns a Series where iloc[-1] = 0.92
            mock_close_series = MagicMock()
            mock_close_series.iloc = MagicMock()
            mock_close_series.iloc.__getitem__ = MagicMock(return_value=0.92)
            mock_hist.__getitem__ = MagicMock(return_value=mock_close_series)
            mock_instance.history.return_value = mock_hist
            mock_ticker.return_value = mock_instance

            result = get_fx_rate("USD", "EUR")
            assert result == 0.92


class TestComputeRsi:
    def test_compute_rsi_happy_path(self):
        """Verify RSI calculation with known input."""
        # Create a monotonically increasing price series
        prices = pd.Series([100, 102, 101, 103, 102, 104, 103, 105, 104, 106, 105, 107, 106, 108, 107])
        result = compute_rsi(prices, period=14)
        assert result is not None
        assert isinstance(result, float)
        assert 0 <= result <= 100

    def test_compute_rsi_insufficient_data(self):
        """Less than period+1 data returns None."""
        prices = pd.Series([100, 101, 102])
        result = compute_rsi(prices, period=14)
        assert result is None

    def test_compute_rsi_no_losses(self):
        """Monotonically increasing prices -> RSI 100."""
        prices = pd.Series([100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114])
        result = compute_rsi(prices, period=14)
        assert result == 100.0


class TestEnrichPosition:
    def test_enrich_position_happy_path(self, mock_yfinance_ticker):
        """Enriches with yfinance data from info dict."""
        pos = {
            "symbol": "AAPL",
            "isin": "US0378331005",
            "name": "Apple Inc",
            "asset_type": "STOCK",
            "quantity": 10.0,
            "avg_buy_price": 150.0,
        }

        # Provide proper history mock so compute_rsi gets a real Series
        mock_hist = MagicMock()
        mock_hist.empty = False
        mock_close = pd.Series([100, 102, 101, 103, 102, 104, 103, 105, 104, 106,
                                 105, 107, 106, 108, 107, 109, 108, 110, 109, 111])
        mock_hist.__getitem__ = MagicMock(return_value=mock_close)
        # Make hist["Close"] return a real Series for compute_rsi
        type(mock_hist).Close = property(lambda self: mock_close)

        mock_ticker_instance = MagicMock()
        mock_ticker_instance.info = mock_yfinance_ticker.info
        mock_ticker_instance.history.return_value = mock_hist
        mock_ticker_instance.history.return_value.empty = False

        with patch("market_data.yf.Ticker", return_value=mock_ticker_instance):
            with patch("market_data.compute_rsi") as mock_rsi:
                mock_rsi.return_value = 55.0
                result = enrich_position(pos)

        assert result["sector"] == "Technology"
        assert result["country"] == "United States"
        assert result["52w_high"] is not None
        assert result["52w_low"] is not None
        assert result["rsi"] == 55.0

    def test_enrich_position_no_symbol(self):
        """Missing symbol returns position unchanged."""
        pos = {"name": "Unknown", "quantity": 5.0}
        with patch("market_data.logger") as mock_logger:
            result = enrich_position(pos)
        assert result["name"] == "Unknown"
        mock_logger.warning.assert_called()

    def test_enrich_position_yf_failure(self):
        """yfinance failure sets fields to None gracefully."""
        pos = {"symbol": "FAIL", "isin": "XX", "name": "Fail Corp", "quantity": 1.0}
        with patch("market_data.yf.Ticker") as mock_ticker:
            mock_instance = MagicMock()
            mock_instance.info = {}  # empty info
            mock_instance.history.side_effect = Exception("Network error")
            mock_ticker.return_value = mock_instance
            result = enrich_position(pos)
        # All yfinance-dependent fields should be None
        assert result["rsi"] is None
        assert result["perf_30d"] is None
        assert result["perf_90d"] is None
        assert result["perf_ytd"] is None
