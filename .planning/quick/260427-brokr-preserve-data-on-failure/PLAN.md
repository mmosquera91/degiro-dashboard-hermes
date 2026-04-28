# brokr-preserve-data-on-failure

Fix two error/401 paths in `loadPortfolioRaw()` that leave the dashboard blank instead of re-rendering existing `portfolioData`.

## Changes

**File:** `app/static/app.js`

### Fix 1 — catch block (network/500 errors)
After `markDataStale()`, call `renderDashboard()` if `portfolioData` exists so the last good data stays visible.

### Fix 2 — 401 handler
Before `openModal()`, call `renderDashboard()` if `portfolioData` exists so the last good data stays visible behind the auth modal.

### What was NOT changed
- `loadPortfolio()` 401 handler — already calls `renderDashboard()` via `loadPortfolioRaw()`.
- `portfolioData` is never cleared on error — preserved as-is.
