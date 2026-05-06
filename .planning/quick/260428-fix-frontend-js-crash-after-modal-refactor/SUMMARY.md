---
name: 260428-fix-frontend-js-crash-after-modal-refactor
description: Add missing showEnrichmentModal/closeEnrichmentModal functions
type: project
status: complete
---

# Quick Task: 260428-fix-frontend-js-crash-after-modal-refactor

## Summary

Fixed: Missing `showEnrichmentModal()` and `closeEnrichmentModal()` functions in app/static/app.js.

## Root Cause

Commit `334132c` introduced `showEnriching()` which calls `showEnrichmentModal()` and `closeEnrichmentModal()`, but those two functions were never defined. The script died at DOMContentLoaded when `showEnriching(true)` was called from `loadPortfolioRaw()`.

## Fix

Added the two missing functions between `showEnriching` and the Benchmark Data section in app/static/app.js (after line 361):

- `showEnrichmentModal(msg)` — sets status text, shows modal, hides error
- `closeEnrichmentModal()` — hides modal, resets content/error visibility

## Verification

- JS syntax check: pass (no errors in console on page load)
- `/api/portfolio` fires: confirmed after fix applied
- No modal/toast logic was changed — only crash fix

## Commit

`6f0dcd1` — fix: add missing showEnrichmentModal/closeEnrichmentModal functions