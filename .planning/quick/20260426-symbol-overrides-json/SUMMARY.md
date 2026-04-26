---
name: 20260426-symbol-overrides-json
description: Symbol override file for hard-to-resolve DeGiro positions
type: quick
status: complete
date: 2026-04-26
---

## Summary

Implemented user-maintained ISIN → Yahoo ticker override file with hot-reload endpoint.

## Changes Applied

- **app/market_data.py**: Added `_load_symbol_overrides()` loader, called at startup, and override check as the first step in `_resolve_yf_symbol()` before cache lookup.
- **app/main.py**: Added `POST /api/admin/reload-overrides` hot-reload endpoint.
- **entrypoint.sh**: Touch `/data/symbol_overrides.json` on container start.

## Testing

- Syntax verified: no errors
- Import verified: `app.market_data` module loads correctly