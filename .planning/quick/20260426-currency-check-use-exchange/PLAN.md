---
name: 20260426-currency-check-use-exchange
description: Replace _price_currency_safe fast_info.currency block with exchange-suffix-based derivation in enrich_position()
status: in-progress
date: 2026-04-26
quick_id: 20260426-XXX
directory: .planning/quick/20260426-currency-check-use-exchange/
commit: 
---

# Plan: currency-check-use-exchange

## Tasks

### Task 1: Replace _price_currency_safe block in enrich_position()

**Files:**
- `app/market_data.py`

**Action:**
In `enrich_position()`, replace the `_price_currency_safe` derivation block (lines 535-542):
```python
# Determine yfinance ticker currency before fetching history
yf_currency = ""
try:
    yf_currency = (ticker.fast_info.currency or "").upper().strip()
except Exception:
    pass
pos_currency = position.get("currency", "EUR").upper().strip()
_price_currency_safe = (not yf_currency) or (yf_currency == pos_currency)
```

With:
```python
# Determine trading currency from the resolved Yahoo ticker's exchange
# suffix — this is more reliable than fast_info.currency for ETFs, which
# reports the index denomination (USD for S&P 500 ETFs), not the listing
# currency (EUR on AMS/GER for UCITS ETFs).
yf_currency = ""
_price_currency_safe = True  # default: trust price if we can't determine

_EUR_EXCHANGE_SUFFIXES = {".AS", ".PA", ".DE", ".F", ".MI", ".MC",
                           ".HE", ".SW", ".EAM", ".EPA", ".ETR"}
_GBP_EXCHANGE_SUFFIXES = {".L"}
_USD_EXCHANGE_SUFFIXES = {"", ".SI"}
_CAD_EXCHANGE_SUFFIXES = {".TO"}

# Extract suffix from resolved symbol (e.g. "SXRU.AS" → ".AS", "QUBT" → "")
if "." in yf_symbol:
    resolved_suffix = "." + yf_symbol.rsplit(".", 1)[-1]
else:
    resolved_suffix = ""

if resolved_suffix in _EUR_EXCHANGE_SUFFIXES:
    yf_currency = "EUR"
elif resolved_suffix in _GBP_EXCHANGE_SUFFIXES:
    yf_currency = "GBP"
elif resolved_suffix in _USD_EXCHANGE_SUFFIXES and resolved_suffix == "":
    # Bare ticker — fall back to fast_info.currency for confirmation
    try:
        yf_currency = (ticker.fast_info.currency or "").upper().strip()
    except Exception:
        yf_currency = ""

pos_currency = position.get("currency", "EUR").upper().strip()
if yf_currency:
    _price_currency_safe = (yf_currency == pos_currency)
# else: yf_currency unknown → keep _price_currency_safe = True (trust price)

if not _price_currency_safe:
    logger.warning(
        "Currency mismatch for %s: exchange=%s (%s), position=%s"
        " — keeping DeGiro price",
        symbol, resolved_suffix or "bare", yf_currency, pos_currency,
    )
```

**Verify:**
```bash
grep -n "_EUR_EXCHANGE_SUFFIXES" app/market_data.py
grep -n "Currency mismatch for" app/market_data.py
```

**Done:**
When the new currency derivation block is in place and the warning log fires correctly for mismatched currencies.

### Task 2: Verify behavior

**Action:**
Confirm the file still passes Python syntax check:
```bash
python3 -m py_compile app/market_data.py && echo "OK"
```

**Done:**
Syntax check passes.