---
name: 20260426-fix-double-fx-conversion
description: Fix double FX conversion in DeGiro portfolio fetch
type: quick
status: complete
date: 2026-04-26
---

## Done

- `app/degiro_client.py:702-710` — Replaced `current_value = float(pos.get("value", ...))`
  fallback with deterministic `current_price × quantity` computation when price is available.
- Removed obsolete `if current_value == 0 ...` fallback block (superseded).

## Effect
`current_value` is now always in native trading currency (e.g. USD). `enrich_positions()`
FX conversion applies exactly once → dashboard total matches DeGiro app value.
