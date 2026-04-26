---
name: 20260426-currency-infer-from-symbol
description: Add _infer_currency_from_symbol() to degiro_client.py and wire it into fetch_portfolio() currency resolution chain as fallback before hardcoded "EUR"
date: 2026-04-26
status: in-progress
slug: currency-infer-from-symbol
quick_id: 20260426-xxx
---

## Tasks

### 1. Add _KNOWN_USD_SYMBOLS and _infer_currency_from_symbol() to degiro_client.py

**File:** `app/degiro_client.py`

**Action:** After `_infer_currency_from_isin()` (line ~487), add the following class-level constant and static method to the `DeGiroClient` class:

```python
    # Well-known US tickers that commonly appear in European DeGiro portfolios.
    # This list is a catch-all for when product info is unavailable.
    # Pattern: bare uppercase alpha symbols that trade on US exchanges only.
    _KNOWN_USD_SYMBOLS = {
        "UNH", "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META",
        "TSLA", "BRK-B", "JPM", "V", "MA", "JNJ", "WMT", "PG", "HD",
        "CVX", "XOM", "LLY", "ABBV", "MRK", "PFE", "TMO", "ABT", "DHR",
        "COST", "AVGO", "ORCL", "ACN", "TXN", "NEE", "RTX", "HON", "UPS",
        "CAT", "GS", "MS", "BAC", "WFC", "C", "BLK", "SCHW", "AXP",
        "QUBT", "RGTI", "LWLG", "ONDS", "POET", "CRGO",
    }

    @staticmethod
    def _infer_currency_from_symbol(symbol: str) -> str:
        """Infer trading currency from well-known US stock symbols.
        Returns 'USD' if recognised, '' otherwise.
        """
        if not symbol:
            return ""
        return "USD" if symbol.upper() in DeGiroClient._KNOWN_USD_SYMBOLS else ""
```

**Verify:** grep for `_KNOWN_USD_SYMBOLS` in `app/degiro_client.py` — should find the constant.

### 2. Update currency resolution chain in fetch_portfolio()

**File:** `app/degiro_client.py`

**Action:** In the position dict inside `fetch_portfolio()` (around line 721), update the `currency` field to add `_infer_currency_from_symbol()` as the final fallback before "EUR":

Change from:
```python
                    "currency": (
                        prod.get("currency")
                        or prod.get("tradingCurrency")
                        or pos.get("currency")
                        or pos.get("currencyCode")
                        or _infer_currency_from_isin(prod.get("isin", ""))
                        or "EUR"
                    ),
```

To:
```python
                    pos_isin = prod.get("isin", "")
                    "currency": (
                        prod.get("currency")
                        or prod.get("tradingCurrency")
                        or pos.get("currency")
                        or pos.get("currencyCode")
                        or _infer_currency_from_isin(pos_isin)
                        or DeGiroClient._infer_currency_from_symbol(prod.get("symbol", pos.get("symbol", "")))
                        or "EUR"
                    ),
```

Note: Extract `pos_isin = prod.get("isin", "")` before the expression to avoid repeating the `prod.get("isin", "")` call twice.

**Verify:** The currency chain should include `DeGiroClient._infer_currency_from_symbol(...)` as the second-to-last fallback before "EUR".

## Done

When both changes are applied and verified, commit with message: `fix(market_data): infer USD from well-known US symbols when product info unavailable`