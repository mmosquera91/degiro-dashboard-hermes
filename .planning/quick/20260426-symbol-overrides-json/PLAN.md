# 20260426-symbol-overrides-json

Symbol override file for hard-to-resolve positions.

## Changes

### app/market_data.py

1. Added `SYMBOL_OVERRIDES_PATH`, `_symbol_overrides` dict, `_symbol_overrides_lock`, and `_load_symbol_overrides()` function after the existing cache path definitions.
2. Called `_load_symbol_overrides()` at the end of `_load_symbol_cache()` so overrides are loaded at startup.
3. Added override check as the first step in `_resolve_yf_symbol()` (before cache lookup), using ISIN as key. When an override is found, it is also cached so subsequent calls are fast via the normal cache path.

### app/main.py

4. Added `POST /api/admin/reload-overrides` endpoint that calls `_load_symbol_overrides()` to reload the file without restart.

### entrypoint.sh

5. Added `touch /data/symbol_overrides.json` so the path is always valid on first deploy.

## Usage

Populate `/data/symbol_overrides.json` with ISIN → Yahoo ticker mappings:

```json
{
    "IE00BMCX4Z88": "SXRU.AS",
    "IE00BYX5NX33": "6RV.DE",
    "LU1681043910": "O9T.DE"
}
```

Call `POST /api/admin/reload-overrides` or restart to apply changes.