---
name: 260428-fix-update-prices-toast
description: Add toast notifications to Update Prices operation
status: complete
completed: 2026-04-28
---

## Summary

Replaced custom `showPriceUpdateToast`/`hidePriceUpdateToast` DOM-based toast with `ToastManager` (already used everywhere else in the app).

**Changes:**
- `app/static/app.js`: Replaced `showPriceUpdateToast(msg, variant)` and `hidePriceUpdateToast()` with direct `ToastManager.show()` calls in `handleUpdatePrices()` and `waitForEnrichmentToast()`
- Removed DOM refs for `#price-update-toast`, `#price-update-toast-msg`, `#price-update-toast-close`
- Removed event listener for close button
- `app/static/index.html`: Removed the stale `#price-update-toast` HTML element

**Behavior:**
- Click → "Updating prices…" (info, auto-dismiss 4s)
- Success → "Prices updated" (success, auto-dismiss 4s)
- Error → error message (error, stays until dismissed)
- Conflicts with other ops → "Another operation is already running..." (error)
- Timeout → "Timed out — refresh manually" (error)