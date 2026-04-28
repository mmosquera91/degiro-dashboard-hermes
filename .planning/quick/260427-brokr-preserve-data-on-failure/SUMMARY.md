---
name: brokr-preserve-data-on-failure
status: complete
---

## Summary

Fixed two error paths in `loadPortfolioRaw()` in `app/static/app.js` to preserve and re-render the last known `portfolioData` instead of leaving the dashboard blank.

### Changes made

1. **catch block** (network/500): Added `if (portfolioData) { renderDashboard(); }` after `markDataStale()` — re-renders last good data on error.
2. **401 handler**: Added `if (portfolioData) renderDashboard();` before `openModal()` — keeps last good data visible behind the auth modal.

### Files changed
- `app/static/app.js` — 2 edits, no other files touched.
