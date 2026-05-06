---
name: 260429-update-prices-persistent-toast
description: Persistent top-center toast with circular spinner for Update Prices
status: complete
completed: 2026-04-29
---

## Summary

Added persistent top-center toast with circular spinner for Update Prices, matching enrichment modal visual language.

**Changes:**

### `app/static/style.css`
- Added `.toast-top-center` class: `position: fixed; top: 16px; left: 50%; transform: translateX(-50%)` — centers toast at top of screen

### `app/static/app.js`
- **ToastManager** gained two new methods:
  - `showProgressToast(message)` — creates a persistent top-center toast with CSS circular spinner (`.enrichment-spinner`) and message text. No auto-dismiss.
  - `updateToast(toast, {message, icon, variant})` — swaps spinner for lucide icon, updates message and variant class, adds close button on error variant
- **handleUpdatePrices()** now uses the progress toast:
  - Click → `showProgressToast("Updating prices…")` — persistent, spinner visible
  - Success → `updateToast(..., {message: "Prices updated", icon: "check-circle", variant: "success"})` + auto-dismiss after 2.5s
  - Error → `updateToast(..., {message: e.message, icon: "alert-circle", variant: "error"})` — stays until user clicks close
