# Problem

`_infer_currency_from_isin()` returns "USD" for US-ISIN stocks (US prefix). When DeGiro holds
US stocks on European exchanges (PTX=Palantir Frankfurt, 6RV=AppLovin Frankfurt, O9T=ARM Hamburg),
the price field is already in EUR. But setting currency="USD" causes the FX conversion layer to fire
on an already-EUR price → double conversion → ~5% portfolio undercount.

`exchangeId` is already fetched and stored in the position dict. It is the most reliable source
for determining the trading currency of a position.

# Solution

Two changes in `app/degiro_client.py`:

1. Add `_EXCHANGE_ID_CURRENCY` dict and `_currency_from_exchange_id()` function near
   `_infer_currency_from_isin()`.

2. In `fetch_portfolio()`, prepend `_currency_from_exchange_id(exchange_id)` to the currency
   fallback chain so exchangeId is consulted first, before product currency fields and before
   ISIN inference.

# Changes

## CHANGE 1 — Add exchange ID → currency lookup

After `_infer_currency_from_isin()` (around line 487), add:

    _EXCHANGE_ID_CURRENCY: dict[str, str] = {
        # EUR exchanges
        "200": "EUR",  # Euronext Amsterdam
        "394": "EUR",  # Euronext Paris
        "645": "EUR",  # Xetra (Deutsche Börse)
        "72":  "EUR",  # Frankfurt
        "2":   "EUR",  # Hamburg
        "3":   "EUR",  # Berlin
        "4":   "EUR",  # Düsseldorf
        "5":   "EUR",  # Munich
        "6":   "EUR",  # Stuttgart
        "109": "EUR",  # Helsinki
        "296": "EUR",  # Borsa Italiana (Milan)
        "750": "EUR",  # Bolsa de Madrid
        "490": "EUR",  # Euronext Brussels
        "314": "EUR",  # Euronext Lisbon
        "194": "SEK",  # Stockholm
        "518": "NOK",  # Oslo
        "735": "DKK",  # Copenhagen
        # CHF
        "455": "CHF",  # SIX Swiss Exchange
        # GBP
        "663": "GBP",  # London Stock Exchange
        # USD
        "676": "USD",  # NASDAQ
        "13":  "USD",  # NYSE
        "14":  "USD",  # NASDAQ (alternate)
        "75":  "USD",  # NASDAQ (alternate)
        "71":  "USD",  # NYSE MKT (AMEX)
        # CAD
        "130": "CAD",  # Toronto Stock Exchange
        # SGD
        "737": "SGD",  # Singapore Exchange
    }

    def _currency_from_exchange_id(exchange_id: str) -> str:
        """Return the trading currency for a DeGiro exchangeId.
        Returns empty string if unknown, so caller falls through."""
        return _EXCHANGE_ID_CURRENCY.get(str(exchange_id), "")

## CHANGE 2 — Prepend exchangeId lookup to currency chain

In `fetch_portfolio()`, replace the currency chain (lines 753-761):

    "currency": (
        prod.get("currency")
        or prod.get("tradingCurrency")
        or pos.get("currency")
        or pos.get("currencyCode")
        or _infer_currency_from_isin(prod.get("isin", ""))
        or DeGiroClient._infer_currency_from_symbol(prod.get("symbol", pos.get("symbol", "")))
        or "EUR"
    ),

With:

    "currency": (
        _currency_from_exchange_id(pos.get("exchangeId", ""))
        or prod.get("currency")
        or prod.get("tradingCurrency")
        or pos.get("currency")
        or pos.get("currencyCode")
        or _infer_currency_from_isin(prod.get("isin", ""))
        or DeGiroClient._infer_currency_from_symbol(prod.get("symbol", pos.get("symbol", "")))
        or "EUR"
    ),

Note: `pos.get("exchangeId")` is used because `exchangeId` is extracted from `pos` in lines 746-752,
not from `prod`. The local variable `exchange_id` is not yet in scope at this point in the dict
comprehension, so we use `pos.get("exchangeId", "")` directly.
