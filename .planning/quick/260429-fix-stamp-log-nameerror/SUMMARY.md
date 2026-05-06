---
name: 260429-fix-stamp-log-nameerror
description: Fix NameError in [STAMP] log - old_price used undefined 'result' variable
type: quick
status: complete
completed: 2026-04-29
---

## Fix Applied

**File:** `app/market_data.py:973`

**Change:** `old_price = result.get("current_price")` → `old_price = position.get("current_price")`

**Why:** The [STAMP] diagnostic code was inserted after `entry = _resolution_cache.get(cache_key)` but before any `result` variable was defined. The `entry` variable holds cached data, but the original code referenced a non-existent `result` variable. The correct reference is to `position.get("current_price")` since we're updating the position object directly, not deriving from a separate `result` dict.

**No logic changes — one line fix.**