---
quick_id: 20260527-ie
slug: indexa-enhancements
status: complete
commit: 1523bd6
completed_at: 2026-05-27
---

# Summary: Indexa Capital Tab Enhancements

## Outcome

The Indexa tab now shows 8 KPI cards (up from 5), a richer funds table with cost basis and gain/loss, EUR-formatted performance chart Y-axis, and fixes the missing `accent-teal` CSS rule.

## Changes

- `app/static/index.html`
  - Added 3 KPI cards: Annual Return (`indexa-kpi-annual-return`), Volatility (`indexa-kpi-volatility`), Sharpe Ratio (`indexa-kpi-sharpe`)
  - Funds table: added Asset Class, Cost, Gain/Loss columns (thead colspan updated from 4 to 7)

- `app/static/app.js`
  - `renderIndexaKPIs()`: populates annual return (`time_return_annual * 100`), volatility (`volatility * 100`), and Sharpe ratio with sign-colour coding
  - `indexaFundEntries()`: extracts `cost_amount` and `asset_class` from positions
  - `renderIndexaFunds()`: renders Asset Class as formatted label, Cost (private-value), and Gain/Loss with positive/negative colour class; added `fmtAssetClass()` helper
  - `renderIndexaPerformanceChart()`: Y-axis callback formats ticks as `€Xk` / `€X`

- `app/static/style.css`
  - Added `.kpi-card.accent-teal { border-top-color: var(--teal); }` (bug fix — class was used but undefined)
  - Added `.kpi-card.accent-red` and `.kpi-card.accent-blue` for new cards
  - `indexa-kpi-grid`: `repeat(5,1fr)` → `repeat(4,1fr)` for 2-row layout
