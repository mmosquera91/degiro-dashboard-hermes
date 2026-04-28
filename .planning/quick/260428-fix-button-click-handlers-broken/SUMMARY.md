---
name: 260428-fix-button-click-handlers-broken
description: Fix operationActive not reset after loadPortfolio success
type: project
status: complete
---

# Quick Task: 260428-fix-button-click-handlers-broken

## Summary

Fixed: `operationActive` was never reset to `false` after successful portfolio loads, causing `handleUpdatePrices` to always return early.

## Root Cause

In `loadPortfolio()`, the success path (200 OK) called `showEnriching(false)` but never called `setOperationActive(false)`. Since `setOperationActive(false)` was only called in error/401/409 branches, `operationActive` remained `true` forever after initial page load.

When user clicked "Update Prices":
- `handleUpdatePrices()` checked `if (operationActive)` at line 307
- Found `operationActive === true` → returned early, did nothing
- No network request, no UI feedback

## Fix

Added `setOperationActive(false)` after `showEnriching(false)` in `loadPortfolio()` success path (line 240).

## Verification

- JS syntax check: pass
- Audit confirmed all referenced functions exist and are declared before use
- Event listeners properly attached after DOMContentLoaded
- Button IDs match HTML (`#btn-update-prices`)
- `operationActive` now properly reset after successful load

## Commit

`TBD` — fix: reset operationActive after successful portfolio load in loadPortfolio()
