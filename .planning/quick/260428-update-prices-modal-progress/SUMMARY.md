---
name: 260428-update-prices-modal-progress
description: Replace Update Prices button text mutation with modal progress overlay
type: quick
status: complete
completed: "2026-04-28"
---

## Summary

Replaced the Update Prices button's inline text mutation ("Updating...") with a proper modal progress overlay, consistent with the enrichment flow pattern.

## Changes

- **app/static/index.html**: Added `#price-update-modal` modal markup after enriching banner
- **app/static/style.css**: Added `.price-update-spinner` and error state styles for the modal
- **app/static/app.js**:
  - Added `elPriceUpdateModal`, `elPriceUpdateModalContent`, `elPriceUpdateError`, `elPriceUpdateErrorMsg`, `elPriceUpdateClose` DOM refs
  - Added `showPriceUpdateModal()` and `closePriceUpdateModal()` helper functions
  - Updated `handleUpdatePrices()` to show modal immediately, remove button-label mutation, show error in modal with Close button on failure
  - Bound `elPriceUpdateClose` click to `closePriceUpdateModal`

## Files Changed

- `app/static/index.html` (HTML)
- `app/static/style.css` (CSS)
- `app/static/app.js` (JS)

## Verification

- Button remains disabled during the API call
- Modal appears immediately on click with spinner
- Success: modal auto-closes
- Error: error message shown in modal with Close button
