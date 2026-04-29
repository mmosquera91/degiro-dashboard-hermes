# 260429-cleanup-ccy-and-724

Quick fix for two issues in the stamp path and resolution cache diagnostics.

## Changes

### 1. Fix ccy= empty on all 27 US stamped positions

**File:** `app/market_data.py` (enrich_position fast-path stamp block, ~line 986)

**Problem:** The stamp path sets `current_price` and `current_value` but never sets `currency`. For US positions resolved via the batch path, `yf_currency` is derived from exchange suffix — but plain US symbols have no suffix, so `yf_currency` ends up empty or reverts to `position.get("currency")` which may also be empty (DeGiro sometimes sends `currency=NULL` for US positions).

**Fix:** After stamping price, set currency via:
- If `yf_currency` is set → use it
- Otherwise → default to `"USD"` (all US batch symbols are USD-denominated)

```python
if yf_currency:
    position["currency"] = yf_currency
else:
    position["currency"] = "USD"
```

### 2. Position 724: RES_PROBE diagnostic logs

**File:** `app/market_data.py` (enrich_positions Step 2, ~line 1391)

**Problem:** Broker symbol "724" returns `[YFSYM] IONQ → None` — the resolution cache has no entry for it. Need to probe what key format is actually stored.

**Fix:** Add two probe logs at the start of Step 2:
```python
logger.info(f"[RES_PROBE] '724' → {_resolution_cache.get('724')}")
logger.info(f"[RES_PROBE] '724:*' keys: {[k for k in _resolution_cache if k.startswith('724')]}")
```

### 3. Remove confirmed diagnostic logs (cleanup)

**File:** `app/market_data.py`

Remove these confirmed diagnostic lines that add noise to production logs:
- `[BATCH_PROBE]` probe lines
- `[BATCH_KEYS]` sample keys log
- `[BATCH_OUTPUT]` price_batch keys log
- `[BATCH_INPUT]` unique_yf_symbols log

Keep:
- `[RES_PROBE]` (newly added for 724 investigation)
- `[YFSYM]` (confirms US stock IONQ in cache)
- `[DIAG]` TOTAL COMPUTED summary (deviation audit)
- `[STAMP]` warnings (genuine misses)