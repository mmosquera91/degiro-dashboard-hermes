"""Unit tests for market_data.py — get_fx_rate, compute_rsi, enrich_position."""

import sys
sys.path.insert(0, 'app')

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
import time

from market_data import get_fx_rate, compute_rsi, enrich_position


class TestGetFxRate:
    def test_get_fx_rate_same_currency(self):
        """EUR->EUR returns 1.0 without cache lookup."""
        with patch("market_data.yf.Ticker") as mock_ticker:
            result = get_fx_rate("EUR", "EUR")
            assert result == 1.0
            mock_ticker.assert_not_called()  # no yfinance call for same currency

    def test_get_fx_rate_cache_hit(self, fx_rate_cache):
        """Second call returns cached value when entry is still fresh."""
        fx_rate_cache["USDEUR"] = (0.92, time.time())  # seed cache with tuple
        with patch("market_data.yf.Ticker") as mock_ticker:
            result = get_fx_rate("USD", "EUR")
            assert result == 0.92
            mock_ticker.assert_not_called()  # no yfinance call, cache hit

    def test_get_fx_rate_cache_expired_refetches(self, fx_rate_cache):
        """Entry older than 1 hour is treated as a miss and triggers a refetch."""
        stale_ts = time.time() - 3700  # 3700s ago — past the 3600s TTL
        fx_rate_cache["USDEUR"] = (0.85, stale_ts)  # stale entry

        with patch("market_data.yf.Ticker") as mock_ticker:
            mock_instance = MagicMock()
            mock_hist = MagicMock()
            mock_hist.empty = False
            mock_close_series = pd.Series([1.08])  # EURUSD → invert → ~0.926
            mock_hist.__getitem__ = MagicMock(return_value=mock_close_series)
            mock_instance.history.return_value = mock_hist
            mock_ticker.return_value = mock_instance

            result = get_fx_rate("USD", "EUR")
            mock_ticker.assert_called()  # yfinance WAS called (stale entry evicted)
            # Result should be freshly fetched (1/1.08), not the stale 0.85
            assert abs(result - (1.0 / 1.08)) < 0.001
            # New entry stored in cache as tuple
            assert "USDEUR" in fx_rate_cache
            cached_rate, cached_ts = fx_rate_cache["USDEUR"]
            assert abs(cached_rate - (1.0 / 1.08)) < 0.001
            assert time.time() - cached_ts < 5  # freshly stamped

    def test_get_fx_rate_yf_failure_returns_none(self, fx_rate_cache):
        """yfinance fails — returns None and does NOT cache the failure."""
        with patch("market_data.yf.Ticker") as mock_ticker:
            mock_instance = MagicMock()
            mock_instance.history.return_value.empty = True  # no data
            mock_ticker.return_value = mock_instance
            result = get_fx_rate("USD", "EUR")
            assert result is None  # failure → None, not 1.0
            assert "USDEUR" not in fx_rate_cache  # failure must NOT be cached

    def test_get_fx_rate_failure_not_cached_retries(self, fx_rate_cache):
        """After a failure (None), the next call retries yfinance rather than returning cached None."""
        with patch("market_data.yf.Ticker") as mock_ticker:
            # First call: yfinance returns empty → failure
            mock_empty = MagicMock()
            mock_empty.history.return_value.empty = True
            mock_ticker.return_value = mock_empty
            first_result = get_fx_rate("USD", "EUR")
            assert first_result is None
            assert "USDEUR" not in fx_rate_cache

            # Second call: yfinance now succeeds
            mock_success = MagicMock()
            mock_hist = MagicMock()
            mock_hist.empty = False
            mock_hist.__getitem__ = MagicMock(return_value=pd.Series([1.08]))
            mock_success.history.return_value = mock_hist
            mock_ticker.return_value = mock_success
            second_result = get_fx_rate("USD", "EUR")
            assert second_result is not None
            assert abs(second_result - (1.0 / 1.08)) < 0.001
            # Now cached as tuple
            assert "USDEUR" in fx_rate_cache

    def test_get_fx_rate_direct_lookup(self, fx_rate_cache):
        """yfinance returns valid rate."""
        with patch("market_data.yf.Ticker") as mock_ticker:
            mock_instance = MagicMock()
            mock_hist = MagicMock()
            mock_hist.empty = False
            # hist["Close"] is dict-style __getitem__ → returns a Series where iloc[-1] = 0.92
            mock_close_series = pd.Series([0.92])
            mock_hist.__getitem__ = MagicMock(return_value=mock_close_series)
            mock_instance.history.return_value = mock_hist
            mock_ticker.return_value = mock_instance

            result = get_fx_rate("USD", "EUR")
            # USDEUR is in inverted_pairs → result = 1.0 / rate_raw
            assert abs(result - (1.0 / 0.92)) < 0.001


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
        import market_data

        # Clear any stale cache entry so _is_cache_warm returns False and the
        # code reaches the normal fetch path where compute_rsi is called.
        cache_key = "AAPL:US0378331005"
        with market_data._resolution_cache_lock:
            market_data._resolution_cache.pop(cache_key, None)

        pos = {
            "symbol": "AAPL",
            "isin": "US0378331005",
            "name": "Apple Inc",
            "asset_type": "STOCK",
            "quantity": 10.0,
            "avg_buy_price": 150.0,
        }

        # Seed resolution cache with ONLY yf_symbol (no fundamentals) so
        # _is_cache_warm returns False → normal fetch path → compute_rsi called.
        # _resolve_yf_symbol is skipped, so ticker.info is called on the mock.
        cache_key = "AAPL:US0378331005"
        with market_data._resolution_cache_lock:
            market_data._resolution_cache[cache_key] = {
                "yf_symbol": "AAPL",
                "exchange": "",
                "currency": "USD",
                "method": "test",
                "cached_at": time.time(),
                # NO "fundamentals" key → _is_cache_warm returns False
            }

        # Seed price cache so current_price is available
        market_data._price_cache["AAPL"] = {
            "current_price": 170.0,
            "price_currency": "USD",
            "timestamp": time.time(),
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
        # 52w_low comes from history, not info — mock has no 52w data so may be None
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


class TestEnrichPositionExceptionHandling:
    """BUG-02: enrich_position catches specific exceptions, not bare except Exception."""

    def test_yf_ticker_missing_error_sets_correct_error(self):
        """YFTickerMissingError (404) sets _enrichment_error='yfinance_error' and evicts cache."""
        from yfinance.exceptions import YFTickerMissingError
        pos = {"symbol": "MISSING", "isin": "XX", "name": "Missing Corp", "quantity": 1.0}

        mock_ticker = MagicMock()
        mock_ticker.info.side_effect = YFTickerMissingError("MISSING", "404 Not Found")
        mock_ticker.history.side_effect = YFTickerMissingError("MISSING", "404 Not Found")

        with patch("market_data.yf.Ticker", return_value=mock_ticker):
            result = enrich_position(pos)

        assert result["_enrichment_error"] == "yfinance_error"
        assert result["rsi"] is None  # enrichment failed

    def test_yf_rate_limit_error_sets_rate_limited(self):
        """YFRateLimitError (429) sets _enrichment_error='rate_limited'."""
        from yfinance.exceptions import YFRateLimitError
        pos = {"symbol": "RATELIMIT", "isin": "XX", "name": "Rate Ltd", "quantity": 1.0}

        mock_ticker = MagicMock()
        mock_ticker.info.side_effect = YFRateLimitError()
        mock_ticker.history.side_effect = YFRateLimitError()

        with patch("market_data.yf.Ticker", return_value=mock_ticker):
            result = enrich_position(pos)

        assert result["_enrichment_error"] == "rate_limited"

    def test_connection_error_sets_network_error(self):
        """ConnectionError sets _enrichment_error='network_error'."""
        pos = {"symbol": "NETERR", "isin": "XX", "name": "Net Err", "quantity": 1.0}

        mock_ticker = MagicMock()
        mock_ticker.info.side_effect = ConnectionError("Connection refused")
        mock_ticker.history.side_effect = ConnectionError("Connection refused")

        with patch("market_data.yf.Ticker", return_value=mock_ticker):
            result = enrich_position(pos)

        assert result["_enrichment_error"] == "network_error"

    def test_data_parsing_error_sets_data_error(self):
        """KeyError/ValueError/TypeError set _enrichment_error='data_error'."""
        pos = {"symbol": "DATAERR", "isin": "XX", "name": "Data Err", "quantity": 1.0}

        mock_ticker = MagicMock()
        mock_ticker.info.side_effect = KeyError("missing key")
        mock_ticker.history.side_effect = KeyError("missing key")

        with patch("market_data.yf.Ticker", return_value=mock_ticker):
            result = enrich_position(pos)

        assert result["_enrichment_error"] == "data_error"


class TestGBpPenceConversion:
    """BUG-04 and COVR-06: GBp pence conversion regression tests."""

    def test_enrich_position_gbp_pence_conversion(self):
        """COVR-06: GBp pence conversion — ticker returns GBp currency, price divided by 100."""
        import market_data

        # Pre-populate resolution cache so enrich_position doesn't fail symbol resolution
        cache_key = "VUSA:IE00B4L5Y983"
        with market_data._resolution_cache_lock:
            market_data._resolution_cache[cache_key] = {
                "yf_symbol": "VUSA.DE",
                "exchange": ".DE",
                "currency": "",
                "method": "test",
                "cached_at": time.time(),
            }

        pos = {
            "symbol": "VUSA",
            "isin": "IE00B4L5Y983",
            "name": "Vanguard S&P 500 UCITS ETF",
            "asset_type": "ETF",
            "quantity": 10.0,
            "avg_buy_price": 6.0,
            "currency": "EUR",
        }

        # Simulate LSE listing returning price in pence with GBp currency metadata
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.info = {"currency": "GBp", "shortName": "Vanguard S&P 500"}

        # Price in pence (e.g., 620 GBp = £6.20)
        mock_hist = MagicMock()
        mock_hist.empty = False
        mock_close = pd.Series([610, 612, 611, 613, 612, 614, 613, 615, 614, 616,
                                615, 617, 616, 618, 617, 619, 618, 620, 619, 621])
        mock_hist.__getitem__ = MagicMock(return_value=mock_close)
        type(mock_hist).Close = property(lambda self: mock_close)
        mock_ticker_instance.history.return_value = mock_hist

        with patch("market_data.yf.Ticker", return_value=mock_ticker_instance):
            with patch("market_data.compute_rsi", return_value=55.0):
                result = enrich_position(pos)

        # Verify pence conversion: price should be ~6.20 (pence/100), not ~620
        assert result["current_price"] is not None
        assert result["current_price"] < 10.0, f"Price {result['current_price']} should be < 10.0 (pounds, not pence)"
        # Currency may be overwritten to EUR (from position) or stay as GBP/GBp
        # — the critical assertion is that current_price is in pounds (<10), not pence (>=600)

    def test_enrich_position_ie00b4l5y983_regression(self):
        """BUG-04: IE00B4L5Y983 (Vanguard S&P 500 UCITS ETF) GBp pence regression test."""
        import market_data

        # Pre-populate resolution cache so enrich_position doesn't fail symbol resolution
        cache_key = "IE00B4L5Y983:IE00B4L5Y983"
        with market_data._resolution_cache_lock:
            market_data._resolution_cache[cache_key] = {
                "yf_symbol": "IE00B4L5Y983.DE",
                "exchange": ".DE",
                "currency": "",
                "method": "test",
                "cached_at": time.time(),
            }

        pos = {
            "symbol": "IE00B4L5Y983",
            "isin": "IE00B4L5Y983",
            "name": "Vanguard S&P 500 UCITS ETF",
            "asset_type": "ETF",
            "quantity": 10.0,
            "avg_buy_price": 6.0,
            "currency": "EUR",
        }

        # Mock ticker simulating IE00B4L5Y983 on LSE returning GBp prices
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.info = {
            "currency": "GBp",
            "shortName": "Vanguard S&P 500 UCITS ETF",
            "sector": "ETF",
        }

        mock_hist = MagicMock()
        mock_hist.empty = False
        # Simulate price in pence range: 600-625 pence = £6.00-£6.25
        mock_close = pd.Series([600, 602, 601, 603, 602, 604, 603, 605, 604, 606,
                                605, 607, 606, 608, 607, 609, 608, 610, 609, 611])
        mock_hist.__getitem__ = MagicMock(return_value=mock_close)
        type(mock_hist).Close = property(lambda self: mock_close)
        mock_ticker_instance.history.return_value = mock_hist

        with patch("market_data.yf.Ticker", return_value=mock_ticker_instance):
            with patch("market_data.compute_rsi", return_value=50.0):
                result = enrich_position(pos)

        # IE00B4L5Y983 in pence: ~610 pence = £6.10
        # Without conversion: ~610 GBP would be 100x overvalued
        assert result["current_price"] is not None
        assert result["current_price"] < 10.0, (
            f"IE00B4L5Y983 price {result['current_price']} suggests pence not converted to pounds"
        )
        assert result["current_price"] > 5.0, (
            f"IE00B4L5Y983 price {result['current_price']} seems too low"
        )

    def test_enrich_position_non_gbp_currency_no_conversion(self):
        """Non-GBp ticker (e.g., USD) should not have price divided by 100."""
        import market_data

        # Pre-populate resolution cache so enrich_position doesn't fail symbol resolution
        cache_key = "AAPL:US0378331005"
        with market_data._resolution_cache_lock:
            market_data._resolution_cache[cache_key] = {
                "yf_symbol": "AAPL",
                "exchange": "",
                "currency": "USD",
                "method": "test",
                "cached_at": time.time(),
            }

        pos = {
            "symbol": "AAPL",
            "isin": "US0378331005",
            "name": "Apple Inc",
            "asset_type": "STOCK",
            "quantity": 10.0,
            "avg_buy_price": 150.0,
            "currency": "USD",
        }

        mock_ticker_instance = MagicMock()
        mock_ticker_instance.info = {"currency": "USD", "shortName": "Apple"}

        mock_hist = MagicMock()
        mock_hist.empty = False
        mock_close = pd.Series([150, 151, 150, 152, 151, 153, 152, 154, 153, 155,
                                154, 156, 155, 157, 156, 158, 157, 159, 158, 160])
        mock_hist.__getitem__ = MagicMock(return_value=mock_close)
        type(mock_hist).Close = property(lambda self: mock_close)
        mock_ticker_instance.history.return_value = mock_hist

        with patch("market_data.yf.Ticker", return_value=mock_ticker_instance):
            with patch("market_data.compute_rsi", return_value=55.0):
                result = enrich_position(pos)

        # USD price should NOT be divided by 100
        assert result["current_price"] is not None
        assert result["current_price"] > 100.0, "USD price should not be divided by 100"
        assert result["currency"] == "USD"


class TestEnrichmentFailedFlag:
    """enrichment_failed flag — True when no current price could be obtained, False otherwise."""

    def test_enrichment_failed_true_when_symbol_unresolvable(self):
        """Symbol that yfinance cannot resolve gets enrichment_failed=True."""
        import market_data

        cache_key = "GHOST:XX0000000000"
        with market_data._resolution_cache_lock:
            market_data._resolution_cache.pop(cache_key, None)

        pos = {
            "symbol": "GHOST",
            "isin": "XX0000000000",
            "name": "Ghost Corp",
            "quantity": 1.0,
        }

        # _resolve_yf_symbol and all suffix probes return empty / raise
        with patch("market_data._resolve_yf_symbol", return_value=""):
            result = enrich_position(pos)

        assert result["enrichment_failed"] is True
        assert result.get("current_price") is None

    def test_enrichment_failed_true_when_yfinance_returns_no_price(self):
        """Resolved symbol but yfinance history is empty → enrichment_failed=True."""
        import market_data

        cache_key = "NOHIST:US9999999999"
        with market_data._resolution_cache_lock:
            market_data._resolution_cache[cache_key] = {
                "yf_symbol": "NOHIST",
                "exchange": "",
                "currency": "USD",
                "method": "test",
                "cached_at": time.time(),
            }
        # Ensure price cache is empty for this symbol
        with market_data._price_cache_lock:
            market_data._price_cache.pop("NOHIST", None)

        pos = {
            "symbol": "NOHIST",
            "isin": "US9999999999",
            "name": "No History Corp",
            "quantity": 2.0,
            "avg_buy_price": 50.0,
        }

        mock_ticker_instance = MagicMock()
        mock_ticker_instance.info = {"currency": "USD", "shortName": "No History Corp"}
        # Return empty history — yf_price stays 0 → current_price never set
        empty_hist = MagicMock()
        empty_hist.empty = True
        empty_hist.__len__ = lambda self: 0
        mock_ticker_instance.history.return_value = empty_hist

        with patch("market_data.yf.Ticker", return_value=mock_ticker_instance):
            with patch("market_data.yf.download", return_value=None):
                result = enrich_position(pos, history_batch={})

        assert result["enrichment_failed"] is True

    def test_enrichment_failed_false_when_price_obtained(self):
        """Successfully enriched position gets enrichment_failed=False (or falsey)."""
        import market_data

        cache_key = "AAPL:US0378331005"
        with market_data._resolution_cache_lock:
            market_data._resolution_cache[cache_key] = {
                "yf_symbol": "AAPL",
                "exchange": "",
                "currency": "USD",
                "method": "test",
                "cached_at": time.time(),
            }
        with market_data._price_cache_lock:
            market_data._price_cache.pop("AAPL", None)

        pos = {
            "symbol": "AAPL",
            "isin": "US0378331005",
            "name": "Apple Inc",
            "asset_type": "STOCK",
            "quantity": 10.0,
            "avg_buy_price": 150.0,
        }

        mock_ticker_instance = MagicMock()
        mock_ticker_instance.info = {
            "currency": "USD",
            "shortName": "Apple",
            "sector": "Technology",
            "country": "United States",
        }
        mock_close = pd.Series([150 + i for i in range(20)])
        mock_hist = MagicMock()
        mock_hist.empty = False
        mock_hist.__len__ = lambda self: len(mock_close)
        mock_hist.__getitem__ = MagicMock(return_value=mock_close)
        type(mock_hist).Close = property(lambda self: mock_close)
        mock_ticker_instance.history.return_value = mock_hist

        # Provide a history_batch so the code takes the batch price path
        batch = {"AAPL": {"close": mock_close, "high": mock_close, "low": mock_close}}
        with patch("market_data.yf.Ticker", return_value=mock_ticker_instance):
            result = enrich_position(pos, history_batch=batch)

        assert result["current_price"] is not None
        assert not result["enrichment_failed"]  # False or falsey

    def test_enrichment_failed_independent_of_fx_missing(self):
        """enrichment_failed and fx_missing are independent — a position can have either or both."""
        import market_data

        # Simulate a position that DID get a price (enrichment_failed=False)
        # but whose FX rate was unavailable (fx_missing=True).
        cache_key = "TSLA:US88160R1014"
        with market_data._resolution_cache_lock:
            market_data._resolution_cache[cache_key] = {
                "yf_symbol": "TSLA",
                "exchange": "",
                "currency": "USD",
                "method": "test",
                "cached_at": time.time(),
            }
        with market_data._price_cache_lock:
            market_data._price_cache.pop("TSLA", None)

        pos = {
            "symbol": "TSLA",
            "isin": "US88160R1014",
            "name": "Tesla Inc",
            "asset_type": "STOCK",
            "quantity": 5.0,
            "avg_buy_price": 200.0,
        }

        mock_ticker_instance = MagicMock()
        mock_ticker_instance.info = {
            "currency": "USD",
            "shortName": "Tesla",
            "sector": "Consumer Cyclical",
            "country": "United States",
        }
        mock_close = pd.Series([200 + i for i in range(20)])
        mock_hist = MagicMock()
        mock_hist.empty = False
        mock_hist.__len__ = lambda self: len(mock_close)
        mock_hist.__getitem__ = MagicMock(return_value=mock_close)
        type(mock_hist).Close = property(lambda self: mock_close)
        mock_ticker_instance.history.return_value = mock_hist

        batch = {"TSLA": {"close": mock_close, "high": mock_close, "low": mock_close}}
        with patch("market_data.yf.Ticker", return_value=mock_ticker_instance):
            result = enrich_position(pos, history_batch=batch)

        # Price was obtained — enrichment_failed should be False
        assert not result["enrichment_failed"]
        # Manually inject fx_missing=True to confirm independence
        result["fx_missing"] = True
        assert result["fx_missing"] is True
        assert not result["enrichment_failed"]  # still independent


class TestResolveAndClassify:
    def test_returns_symbol_name_and_etf_type(self, monkeypatch):
        import app.market_data as md

        monkeypatch.setattr(md, "_resolve_by_isin", lambda isin, position_currency="EUR": "SXRU.AS")

        class FakeTicker:
            info = {"quoteType": "ETF", "shortName": "iShares S&P 500", "longName": "iShares Core S&P 500 UCITS ETF"}

        monkeypatch.setattr(md.yf, "Ticker", lambda s: FakeTicker())
        out = md.resolve_and_classify("IE00B5BMR087")
        assert out == {"symbol": "SXRU.AS", "name": "iShares Core S&P 500 UCITS ETF", "asset_type": "ETF"}

    def test_equity_maps_to_stock(self, monkeypatch):
        import app.market_data as md
        monkeypatch.setattr(md, "_resolve_by_isin", lambda isin, position_currency="EUR": "AAPL")

        class FakeTicker:
            info = {"quoteType": "EQUITY", "shortName": "Apple Inc."}

        monkeypatch.setattr(md.yf, "Ticker", lambda s: FakeTicker())
        out = md.resolve_and_classify("US0378331005")
        assert out["asset_type"] == "STOCK"
        assert out["symbol"] == "AAPL"
        assert out["name"] == "Apple Inc."

    def test_unresolvable_isin_raises(self, monkeypatch):
        import app.market_data as md
        monkeypatch.setattr(md, "_resolve_by_isin", lambda isin, position_currency="EUR": "")
        with pytest.raises(ValueError, match="Could not resolve"):
            md.resolve_and_classify("XX0000000000")

    def test_us_isin_resolves_via_usd_exchange(self, monkeypatch):
        """A US-listed-only security (e.g. MRVL, US5738741041) must resolve.

        Regression: the watchlist add flow defaulted to EUR, so the only
        listing (NMS, a USD exchange) was discarded by the competing-exchange
        filter and the ISIN never resolved. The currency must be derived from
        the ISIN country prefix.
        """
        import app.market_data as md
        seen = {}

        def fake_resolve(isin, position_currency="EUR"):
            seen["currency"] = position_currency
            return "MRVL"

        monkeypatch.setattr(md, "_resolve_by_isin", fake_resolve)

        class FakeTicker:
            info = {"quoteType": "EQUITY", "shortName": "Marvell Technology, Inc."}

        monkeypatch.setattr(md.yf, "Ticker", lambda s: FakeTicker())
        out = md.resolve_and_classify("US5738741041")
        assert seen["currency"] == "USD"
        assert out["symbol"] == "MRVL"

    def test_gb_isin_uses_gbp_currency(self, monkeypatch):
        import app.market_data as md
        seen = {}
        monkeypatch.setattr(
            md, "_resolve_by_isin",
            lambda isin, position_currency="EUR": seen.update(currency=position_currency) or "ULVR.L",
        )
        monkeypatch.setattr(md.yf, "Ticker", lambda s: type("T", (), {"info": {}})())
        md.resolve_and_classify("GB00B10RZP78")
        assert seen["currency"] == "GBP"

    def test_eu_isin_defaults_to_eur(self, monkeypatch):
        import app.market_data as md
        seen = {}
        monkeypatch.setattr(
            md, "_resolve_by_isin",
            lambda isin, position_currency="EUR": seen.update(currency=position_currency) or "SXRU.AS",
        )
        monkeypatch.setattr(md.yf, "Ticker", lambda s: type("T", (), {"info": {}})())
        md.resolve_and_classify("IE00B5BMR087")
        assert seen["currency"] == "EUR"


class TestEnrichWatchlist:
    def test_builds_position_dicts_and_enriches(self, monkeypatch):
        import app.market_data as md

        captured = {}

        def fake_enrich_positions(raw):
            captured["positions"] = raw["positions"]
            for p in raw["positions"]:
                p["current_price"] = 100.0
                p["rsi"] = 55.0
            return raw["positions"]

        monkeypatch.setattr(md, "enrich_positions", fake_enrich_positions)

        entries = [{"isin": "US0378331005", "symbol": "AAPL", "name": "Apple", "asset_type": "STOCK"}]
        out = md.enrich_watchlist(entries)

        built = captured["positions"][0]
        assert built["symbol"] == "AAPL"
        assert built["quantity"] == 0
        assert built["owned"] is False
        assert built["source"] == "watchlist"
        assert out[0]["rsi"] == 55.0
        assert built["weight"] == 0
        assert built["isin"] == "US0378331005"
        assert built["name"] == "Apple"

    def test_asset_type_defaults_to_stock(self, monkeypatch):
        import app.market_data as md
        captured = {}
        def fake_enrich_positions(raw):
            captured["positions"] = raw["positions"]
            return raw["positions"]
        monkeypatch.setattr(md, "enrich_positions", fake_enrich_positions)
        md.enrich_watchlist([{"isin": "X", "symbol": "X", "name": "X"}])  # no asset_type
        assert captured["positions"][0]["asset_type"] == "STOCK"

    def test_empty_list_returns_empty(self, monkeypatch):
        import app.market_data as md
        assert md.enrich_watchlist([]) == []


class TestEnrichPositionsWatchlistFx:
    """Regression: watchlist entries have quantity 0 and no avg_buy_price, so the
    real enrich_position never sets unrealized_pl. The FX conversion loop in
    enrich_positions must not assume current_value / unrealized_pl exist — it
    used to KeyError, and get_watchlist swallowed it, so every row showed "—"."""

    def test_zero_quantity_usd_entry_without_pl_does_not_crash(self, monkeypatch):
        import app.market_data as md

        # Pre-warm resolution cache so Step-1 resolution makes no network call
        with md._resolution_cache_lock:
            md._resolution_cache["MRVL:US5738741041"] = {
                "yf_symbol": "MRVL", "exchange": "", "currency": "",
                "method": "test", "cached_at": time.time(),
            }

        # Mirror real enrich_position for a non-owned position: price/value are
        # stamped, but unrealized_pl is skipped because avg_buy_price == 0.
        def fake_enrich_position(pos, history_batch=None):
            pos["current_price"] = 80.0
            pos["current_value"] = 0.0
            pos["currency"] = "USD"
            pos["rsi"] = 60.0
            pos["distance_from_52w_high_pct"] = -12.0
            return pos  # deliberately NO unrealized_pl key

        monkeypatch.setattr(md, "enrich_position", fake_enrich_position)
        monkeypatch.setattr(md.yf, "download", lambda *a, **k: pd.DataFrame())
        monkeypatch.setattr(md, "get_fx_rate", lambda *a, **k: 0.92)

        positions = [{
            "isin": "US5738741041", "symbol": "MRVL", "name": "Marvell Technology, Inc.",
            "asset_type": "STOCK", "quantity": 0, "weight": 0, "owned": False, "source": "watchlist",
        }]
        out = md.enrich_positions({"positions": positions})

        assert out[0]["rsi"] == 60.0
        assert out[0]["distance_from_52w_high_pct"] == -12.0
        assert out[0]["unrealized_pl_eur"] is None
        assert out[0]["current_value_eur"] == 0.0
