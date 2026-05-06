---
name: 260428-fix-ucits-etf-gbp-pence-inflation
status: complete
---

## Summary
Fixed 100× price inflation for LSE-listed instruments where yfinance returns prices in
GBp (pence) but code was treating them as GBP pounds.

## Changes Implemented

### app/market_data.py (lines 1109-1125)
Added GBp (pence) safety net in `enrich_position()` right after `yf_price` is
determined and before it is stored in the position:

```python
if yf_price > 0:
    ticker_currency = ""
    try:
        ticker_currency = ticker.info.get("currency", "") or ""
        if not ticker_currency:
            ticker_currency = getattr(ticker.fast_info, "currency", "") or ""
    except Exception:
        pass
    if ticker_currency == "GBp":
        yf_price = yf_price / 100.0
        yf_currency = "GBP"
    position["current_price"] = round(yf_price, 4)
    ...
```

- yfinance `info.currency` correctly returns `"GBp"` for LSE tickers (confirmed: EWG.L → GBp)
- Detecting and converting before storing ensures all downstream FX conversion and
  caching uses the correct pound-denominated price

### bundled_overrides.json
Skipped — the 7 ETFs (ESP0, QDVD, VVGM, QDVF, QDV5, VVSM, ZPRR) are NOT present in
bundled_overrides.json (which is ISIN-keyed). They resolve via ISIN scan/suffix order.
The ISIN scan correctly routes IE/LU ISINs to .DE first (VVGM, QDVF, QDV5, VVSM,
ZPRR already use .DE in practice). The GBp safety net handles any remaining .L
resolution (e.g. if ISIN scan fails and suffix scan picks up .L).

## After Fix
- DELETE /api/admin/symbol-cache to clear any stale .L resolution cache entries
- Run Update Prices — LSE tickers will no longer show 100× inflated values
- Portfolio total should match DeGiro

## Verification
- `python3 -c "import ast; ast.parse(open('app/market_data.py').read())"` → Syntax OK
- Manual test: EWG.L price 114.4 GBp → correctly converted to 1.144 GBP
