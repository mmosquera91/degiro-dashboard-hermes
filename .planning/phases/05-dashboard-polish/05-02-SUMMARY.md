# Phase 05 Plan 02: Error States and Responsive CSS — Summary

## What Was Built

Stale data indicator with warning badge, positions table error state with retry button, and responsive CSS improvements for 420px mobile and 768px tablet viewports.

## What Was Done

### Tasks Completed

1. **Add stale indicator HTML and CSS** (Commit: `62f9306`)
   - Added `stale-badge` span in header-right (index.html line 27)
   - Added `.stale-badge` CSS with amber warning styling (style.css line 78)
   - Added `.positions-error` CSS for error state (style.css line 94)

2. **Add stale indicator JS logic to app.js** (Commit: `200cd8b`)
   - Added `lastSuccessfulRefresh` state variable (line 15)
   - Added `markDataStale()`, `clearStaleIndicator()`, `formatTimeSince()` functions (lines 893-912)
   - Updated `loadPortfolio()` catch block to call `markDataStale()` and `ToastManager.show()` (line 239)
   - Updated `loadPortfolioRaw()` catch block to call `markDataStale()` (line 270)
   - Added `lastSuccessfulRefresh = Date.now()` at end of `renderDashboard()` (line 487)

3. **Add positions table error state to renderPositions()** (Commit: `200cd8b`)
   - Updated `renderPositions()` to check `!portfolioData.positions` and show error state with Retry button (line 613)

4. **Add responsive CSS improvements** (Commit: `0afd28a`)
   - 768px: 2-column summary cards grid, hide btn-label and last-refresh, smaller stale badge font
   - 420px: single column layout, full-width modal (`calc(100vw - 32px)`), reduced font sizes
   - Added sticky `col-name` header for positions table horizontal scroll on mobile

## Files Modified

| File | Change | Commit |
|------|--------|--------|
| `app/static/index.html` | Added stale-badge span in header-right | `62f9306` |
| `app/static/style.css` | Added stale badge CSS, positions-error CSS, responsive breakpoints | `62f9306` + `0afd28a` |
| `app/static/app.js` | Added stale indicator functions, updated catch blocks, positions error state | `200cd8b` |

## Deviations from Plan

None — plan executed exactly as specified.

## Verification

```bash
grep -n 'id="stale-badge"' app/static/index.html   # 27: stale-badge span
grep -n "\.stale-badge" app/static/style.css       # 78: .stale-badge CSS
grep -n "markDataStale" app/static/app.js           # 239, 270, 893: stale functions
grep -n "positions-error" app/static/app.js         # 613: error state
grep -n "positions-error" app/static/style.css      # 94: error CSS
grep -n "@media (max-width: 420px)" app/static/style.css  # 674: mobile breakpoint
grep -n "@media (max-width: 768px)" app/static/style.css  # 657: tablet breakpoint
```

## Threat Mitigation

| Threat | Disposition | Mitigation |
|--------|-------------|------------|
| T-05-02 (Tampering via onclick) | mitigated | `onclick="loadPortfolioRaw()"` is a safe function call, not user input |

## Success Criteria

- [x] index.html contains stale-badge element in header-right
- [x] style.css contains .stale-badge CSS
- [x] app.js contains markDataStale(), clearStaleIndicator(), formatTimeSince()
- [x] loadPortfolio() catch block calls markDataStale() and ToastManager.show()
- [x] renderDashboard() sets lastSuccessfulRefresh on success
- [x] renderPositions() shows error state with retry when portfolioData.positions is missing
- [x] style.css has responsive breakpoint at 768px (2-col grid)
- [x] style.css has responsive breakpoint at 420px (single column, modal full-width)
- [x] Positions table has sticky Name column on mobile

## Test/Verification Notes

Manual verification steps:
1. Load dashboard, then disconnect network and trigger refresh — verify stale badge appears with timestamp
2. Clear localStorage/cache to lose portfolio data, refresh — verify "Failed to load positions" with retry button
3. Resize to 420px — verify single column, no overflow, modal is full-width
4. Resize to 768px — verify 2-column summary cards
5. On mobile 420px, scroll positions table horizontally — verify Name column stays visible (sticky)