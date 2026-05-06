---
status: in-progress
created: 2026-05-03
type: quick
---
# Fix 2 pre-existing test failures in test_market_data.py

## TestGetFxRate::test_get_fx_rate_direct_lookup

**Problem:** `hist["Close"]` at line 396 uses dict-like `__getitem__` access. The mock sets `mock_hist.__getitem__` to return a MagicMock whose `iloc[-1]` returns an auto-generated MagicMock (not 0.92), causing `float(...)` to produce 1.0869... instead of 0.92.

**Fix:** Replace `mock_hist.__getitem__` + series iloc chain with a single `PropertyMock` on `.Close`, matching how `hist["Close"]` actually works in pandas — `hist["Close"]` is `hist.Close` attribute access under the hood.

```python
mock_hist = MagicMock()
mock_hist.empty = False
mock_close_series = pd.Series([0.92])  # single value Series
type(mock_hist).Close = property(lambda self: mock_close_series)
```

## TestEnrichPosition::test_enrich_position_happy_path

**Problem:** `result["sector"]` returns None. The code reads `ticker.info.get("sector")` at line 1127, but `ticker` here is the result of `yf.Ticker(yf_symbol)` — not the `mock_ticker_instance` patched at `"market_data.yf.Ticker"`. The symbol "AAPL" resolves via `_resolve_symbol` to "AAPL" (no yf_symbol found), so the patch is never reached.

**Fix:** Pre-populate the resolution cache so `enrich_position` uses the patched ticker. Also pre-populate the batch price cache since the test also expects a batch price lookup at line 1237.

```python
# Before the with patch(...) block:
import market_data
with market_data._resolution_cache_lock:
    market_data._resolution_cache["AAPL:US0378331005"] = {
        "yf_symbol": "AAPL", "exchange": "", "currency": "USD", "method": "yf"
    }
```

Also, `position["currency"]` should be "USD" to match the info dictionary — the test sets no currency on the position, and `enrich_position` only sets it when it differs from the yf currency.

## Verification

```bash
PYTHONPATH=app python3 -m pytest tests/test_market_data.py::TestGetFxRate::test_get_fx_rate_direct_lookup tests/test_market_data.py::TestEnrichPosition::test_enrich_position_happy_path -v
```