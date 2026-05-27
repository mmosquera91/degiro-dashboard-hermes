---
quick_id: 20260527-ie
slug: indexa-enhancements
status: in-progress
started_at: 2026-05-27
---

# Indexa Capital Tab Enhancements

## Goal
Enhance the Indexa Capital tab with additional KPI metrics, richer funds table, and improved performance chart formatting.

## Changes

### 1. Fix accent-teal CSS bug
- `style.css`: add `.kpi-card.accent-teal { border-top-color: var(--teal); }`

### 2. Add 3 new KPI cards (HTML + JS)
New cards: Annual Return, Volatility, Sharpe Ratio
- `index.html`: add 3 cards to `indexa-kpi-grid`
- `style.css`: update `indexa-kpi-grid` from `repeat(5,1fr)` to `repeat(4,1fr)` (2×4 layout)
- `app.js`: populate new KPIs in `renderIndexaKPIs()`

### 3. Funds table: add Cost + Gain/Loss columns
- `index.html`: add `<th>Cost</th>` and `<th>Gain/Loss</th>` before Weight%
- `app.js`: extend `indexaFundEntries()` to include `cost_amount`
- `app.js`: update `renderIndexaFunds()` to render cost and gain/loss with color

### 4. Performance chart: EUR Y-axis formatting
- `app.js`: add `ticks.callback` to Y scale to show `€` prefix with compact notation
