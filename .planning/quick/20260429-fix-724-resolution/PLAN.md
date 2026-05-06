# 260429-fix-724-resolution

Fix resolution of DeGiro numeric broker symbol "724" (product ID, not ticker).

## Problem
- Broker symbol "724" is a DeGiro internal product ID, not a Yahoo ticker
- `_resolve_yf_symbol` skips numeric symbols early (line 494) and returns ""
- Position has ISIN in raw data but resolution path never reaches it

## Changes (app/market_data.py)

### Step 1 — Log raw position for numeric symbols
In `enrich_positions` loop, when `sym.isdigit()`:
```python
if sym.isdigit():
    logger.info(f"[POS_RAW_724] raw_position={pos}")
```

### Step 2 — ISIN fallback for numeric broker symbols
When `_resolve_yf_symbol` returns empty (numeric symbol skipped), fall through to ISIN:
```python
if sym.isdigit():
    pos_isin = isin or pos.get("isin", "") or pos.get("ISIN", "")
    if pos_isin:
        yf_sym = _resolve_by_isin(pos_isin, pos.get("currency", "EUR"))
        if yf_sym:
            # Cache under both "724:ISIN" and "724:" keys
```

### Step 3 — Cache both keys on resolution
Store in `_resolution_cache` under `f"{sym}:{pos_isin}"` and `f"{sym}:"` so subsequent
runs hit cache without re-resolving. Persist with `_save_symbol_cache()`.

## Verification
Next enrichment run will show `[POS_RAW_724] raw_position={...}` with ISIN field,
and if ISIN resolves, `[INFO] Resolved numeric DeGiro symbol 724 (ISIN ...) → ...`