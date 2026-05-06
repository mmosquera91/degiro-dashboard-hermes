---
name: 260429-update-prices-persistent-toast
description: Persistent top-center toast with circular spinner for Update Prices
status: pending
created: 2026-04-29
---

**Goal:** Replace the brief auto-dismiss "Updating prices…" info toast with a persistent top-center toast that shows a CSS circular spinner for the full duration of the operation.

## Changes

### 1. `app/static/style.css` — Add top-center toast variant

Add `.toast-top-center` CSS:
- `position: fixed; top: 16px; left: 50%; transform: translateX(-50%);`
- Other styles match existing `.toast` (same colors, radius, shadow, animations)

### 2. `app/static/app.js` — ToastManager enhancements

**Add `showProgressToast(message)` method** to ToastManager:
- Creates a toast with class `.toast-top-center` (top-center positioning)
- Adds `.enrichment-spinner` div (CSS circular spinner from enrichment modal)
- Text shows the message passed in
- Returns the toast element so caller can update it

**Add `updateToast(toast, {message, icon, variant})` method** to ToastManager:
- Updates toast message, icon (lucide name), and variant class
- Re-renders lucide icons after icon swap

**Modify `handleUpdatePrices()`:**
- Replace `ToastManager.show("Updating prices…", "info")` with `ToastManager.showProgressToast("Updating prices…")`
- Store the progress toast reference
- On success: call `updateToast(progressToast, {message: "Prices updated", icon: "check-circle", variant: "success"})` then `setTimeout(() => ToastManager.dismiss(progressToast), 2500)`
- On error: call `updateToast(progressToast, {message: e.message, icon: "alert-circle", variant: "error"})` — toast stays, user must click close

### 3. No HTML changes needed

All markup created via JS.
