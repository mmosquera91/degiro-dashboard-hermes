"""Unit tests for degiro_client.py — _kv_list_to_dict and DeGiroClient.fetch_portfolio."""

import sys
sys.path.insert(0, 'app')

import pytest
from unittest.mock import patch, MagicMock

from degiro_client import _kv_list_to_dict, DeGiroClient


class TestDeGiroClientFromSessionId:
    """DEGIRO-02, DEGIRO-03: from_session_id behavior."""

    def test_from_session_id_returns_trading_api(self):
        """DEGIRO-02: Valid session_id returns TradingAPI instance."""
        with patch("app.degiro_client.DeGiroClient._fetch_int_account"):
            result = DeGiroClient.from_session_id("valid-session-123")
        assert result is not None
        assert hasattr(result, "connection_storage")
        assert hasattr(result, "credentials")
        # Verify session_id was set
        assert result.connection_storage.session_id == "valid-session-123"

    def test_from_session_id_with_int_account(self):
        """DEGIRO-02: Valid session_id + int_account sets int_account on credentials."""
        with patch("app.degiro_client.DeGiroClient._fetch_int_account"):
            result = DeGiroClient.from_session_id("valid-session-456", int_account=789)
        assert result.credentials.int_account == 789

    def test_from_session_id_empty_string_raises(self):
        """DEGIRO-03: Empty session_id raises ConnectionError."""
        with pytest.raises(ConnectionError, match="Session ID is required"):
            DeGiroClient.from_session_id("")

    def test_from_session_id_none_raises(self):
        """DEGIRO-03: None session_id raises ConnectionError."""
        with pytest.raises(ConnectionError, match="Session ID is required"):
            DeGiroClient.from_session_id(None)


class TestKvListToDict:
    def test_kv_list_to_dict(self):
        """Converts DeGiro key-value list to flat dict."""
        kv_list = [
            {"name": "size", "value": 64, "isAdded": True},
            {"name": "price", "value": 150.25, "isAdded": False},
            {"name": "id", "value": 12345},
        ]
        result = _kv_list_to_dict(kv_list)
        assert result == {"size": 64, "price": 150.25, "id": 12345}

    def test_kv_list_to_dict_already_dict(self):
        """Returns dict unchanged."""
        d = {"key": "value", "num": 42}
        result = _kv_list_to_dict(d)
        assert result == d
        assert result is d  # same object, not copied

    def test_kv_list_to_dict_invalid_items(self):
        """Skips non-dict and missing-name items."""
        kv_list = [
            {"name": "valid", "value": 1},
            "not a dict",
            {"value": "missing name"},
            None,
            {"name": "also_valid", "value": 2},
        ]
        result = _kv_list_to_dict(kv_list)
        assert result == {"valid": 1, "also_valid": 2}

    def test_kv_list_to_dict_empty(self):
        """Empty or None input."""
        assert _kv_list_to_dict([]) == {}
        assert _kv_list_to_dict(None) == {}


class TestDeGiroClientKvListToDict:
    """DEGIRO-01: _kv_list_to_dict converts DeGiro key-value list format to flat dict."""

    def test_normal_kv_list(self):
        """DEGIRO-01: Normal [{"name": "key", "value": x}] converts to {"key": x}."""
        from app.degiro_client import _kv_list_to_dict
        result = _kv_list_to_dict([
            {"name": "size", "value": 64},
            {"name": "price", "value": 150.5},
        ])
        assert result == {"size": 64, "price": 150.5}

    def test_empty_list(self):
        """DEGIRO-01: Empty list [] returns {}."""
        from app.degiro_client import _kv_list_to_dict
        assert _kv_list_to_dict([]) == {}

    def test_dict_passthrough(self):
        """DEGIRO-01: If already a dict, returns as-is."""
        from app.degiro_client import _kv_list_to_dict
        existing = {"foo": "bar", "baz": 123}
        assert _kv_list_to_dict(existing) is existing

    def test_non_list_input(self):
        """DEGIRO-01: Non-list input (string) returns {}."""
        from app.degiro_client import _kv_list_to_dict
        assert _kv_list_to_dict("not a list") == {}
        assert _kv_list_to_dict(None) == {}
        assert _kv_list_to_dict(42) == {}

    def test_item_missing_keys(self):
        """DEGIRO-01: Item missing "name" or "value" key is skipped."""
        from app.degiro_client import _kv_list_to_dict
        result = _kv_list_to_dict([
            {"name": "valid", "value": 1},
            {"value": 2},          # missing "name" — skipped
            {"name": "also_valid"},  # missing "value" — skipped
            {"name": "third", "value": 3},
        ])
        assert result == {"valid": 1, "third": 3}


class TestFetchPortfolio:
    def test_fetch_portfolio_happy_path(self):
        """Parses positions from raw API response."""
        mock_api = MagicMock()

        # Mock get_update response
        mock_update = {
            "portfolio": {
                "value": [
                    {
                        "name": "positionrow",
                        "value": [
                            {"name": "id", "value": 123},
                            {"name": "size", "value": 10.0},
                            {"name": "price", "value": 150.0},
                            {"name": "value", "value": 1500.0},
                            {"name": "breakEvenPrice", "value": 140.0},
                            {"name": "positionType", "value": "STOCK"},
                        ],
                    }
                ]
            },
            "cashFunds": {
                "value": [
                    {"name": "cashFund", "value": [
                        {"name": "currencyCode", "value": "EUR"},
                        {"name": "value", "value": 5000.0},
                    ]}
                ]
            },
            "totalPortfolio": {},
        }
        mock_api.get_update.call.return_value = mock_update

        # Mock get_products_info response
        mock_products = {
            "data": {
                "123": {
                    "name": "Apple Inc",
                    "isin": "US0378331005",
                    "symbol": "AAPL",
                    "currency": "USD",
                    "productType": "STOCK",
                }
            }
        }
        mock_api.get_products_info.call.return_value = mock_products

        result = DeGiroClient.fetch_portfolio(mock_api)

        assert "positions" in result
        assert len(result["positions"]) == 1
        pos = result["positions"][0]
        assert pos["name"] == "Apple Inc"
        assert pos["isin"] == "US0378331005"
        assert pos["symbol"] == "AAPL"
        assert pos["quantity"] == 10.0
        assert pos["current_price"] == 150.0
        assert pos["current_value"] == 1500.0
        assert pos["avg_buy_price"] == 140.0
        assert pos["currency"] == "USD"
        assert result["cash_available"] == 5000.0

    def test_fetch_portfolio_kv_format(self):
        """Handles DeGiro key-value list format for position rows."""
        mock_api = MagicMock()
        mock_api.get_update.call.return_value = {
            "portfolio": {
                "value": [
                    {
                        "name": "positionrow",
                        "value": [
                            {"name": "id", "value": 456},
                            {"name": "size", "value": 5.0},
                            {"name": "price", "value": 85.0},
                            {"name": "value", "value": 425.0},
                            {"name": "breakEvenPrice", "value": 80.0},
                            {"name": "positionType", "value": "ETF"},
                        ],
                    }
                ]
            },
            "cashFunds": {"value": []},
            "totalPortfolio": {},
        }
        mock_api.get_products_info.call.return_value = {
            "data": {
                "456": {
                    "name": "Vanguard S&P 500",
                    "isin": "IE00B4L5Y983",
                    "symbol": "VUSA",
                    "currency": "EUR",
                    "productType": "ETF",
                }
            }
        }

        result = DeGiroClient.fetch_portfolio(mock_api)
        assert len(result["positions"]) == 1
        pos = result["positions"][0]
        assert pos["name"] == "Vanguard S&P 500"
        assert pos["asset_type"] == "ETF"
        assert pos["quantity"] == 5.0

    def test_fetch_portfolio_skips_non_product(self):
        """Skips cash lines and non-product entries."""
        mock_api = MagicMock()
        mock_api.get_update.call.return_value = {
            "portfolio": {
                "value": [
                    {
                        "name": "positionrow",
                        "value": [
                            {"name": "id", "value": 999},
                            {"name": "size", "value": 100.0},
                            {"name": "price", "value": 1.0},
                            {"name": "value", "value": 100.0},
                            {"name": "breakEvenPrice", "value": 1.0},
                            {"name": "positionType", "value": "CASH"},
                        ],
                    },
                    {
                        "name": "positionrow",
                        "value": [
                            {"name": "id", "value": 123},
                            {"name": "size", "value": 10.0},
                            {"name": "price", "value": 150.0},
                            {"name": "value", "value": 1500.0},
                            {"name": "breakEvenPrice", "value": 140.0},
                            {"name": "positionType", "value": "STOCK"},
                        ],
                    },
                ]
            },
            "cashFunds": {"value": []},
            "totalPortfolio": {},
        }
        mock_api.get_products_info.call.return_value = {
            "data": {
                "123": {
                    "name": "Apple Inc",
                    "isin": "US0378331005",
                    "symbol": "AAPL",
                    "currency": "USD",
                    "productType": "STOCK",
                }
            }
        }

        result = DeGiroClient.fetch_portfolio(mock_api)
        # Only STOCK position should be included; CASH line skipped
        assert len(result["positions"]) == 1
        assert result["positions"][0]["name"] == "Apple Inc"

    def test_fetch_portfolio_empty(self):
        """Handles empty portfolio."""
        mock_api = MagicMock()
        mock_api.get_update.call.return_value = {
            "portfolio": {"value": []},
            "cashFunds": {"value": []},
            "totalPortfolio": {},
        }
        mock_api.get_products_info.call.return_value = {"data": {}}

        result = DeGiroClient.fetch_portfolio(mock_api)
        assert result["positions"] == []
        assert result["cash_available"] == 0.0

    def test_fetch_portfolio_raises_on_connection_error(self):
        """DEGIRO-05: DeGiroConnectionError during get_update raises RuntimeError."""
        mock_api = MagicMock()
        from degiro_connector.core.exceptions import DeGiroConnectionError
        mock_api.get_update.call.side_effect = DeGiroConnectionError("Session expired", "Session expired or 2FA required")

        with pytest.raises(RuntimeError, match="Failed to fetch portfolio"):
            DeGiroClient.fetch_portfolio(mock_api)

    def test_fetch_portfolio_missing_optional_fields(self):
        """DEGIRO-07: Position missing optional fields uses defaults."""
        mock_api = MagicMock()
        mock_api.get_update.call.return_value = {
            "portfolio": {
                "value": [
                    {
                        "name": "positionrow",
                        "value": [
                            # Only id, size, price present — no name, isin, symbol, etc.
                            {"name": "id", "value": 999},
                            {"name": "size", "value": 3.0},
                            {"name": "price", "value": 200.0},
                            {"name": "value", "value": 600.0},
                            {"name": "breakEvenPrice", "value": 190.0},
                            {"name": "positionType", "value": "STOCK"},
                        ],
                    }
                ]
            },
            "cashFunds": {"value": []},
            "totalPortfolio": {},
        }
        mock_api.get_products_info.call.return_value = {"data": {}}  # no product info

        result = DeGiroClient.fetch_portfolio(mock_api)
        assert len(result["positions"]) == 1
        pos = result["positions"][0]
        # Defaults per DEGIRO-07: name → "Product {pid}", isin → "", symbol → ""
        assert pos["name"] == "Product 999"
        assert pos["isin"] == ""
        assert pos["symbol"] == ""
        assert pos["sector"] == ""
        assert pos["country"] == ""
        assert pos["quantity"] == 3.0
        assert pos["current_price"] == 200.0
