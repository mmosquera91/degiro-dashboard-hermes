"""Unit tests for degiro_client.py — _kv_list_to_dict and DeGiroClient.fetch_portfolio."""

import sys
sys.path.insert(0, 'app')

import pytest
from unittest.mock import patch, MagicMock

from degiro_client import _kv_list_to_dict, DeGiroClient


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
