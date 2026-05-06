---
name: 260429-dashboard-rows-redesign-summary
status: complete
---

Replaced the dashboard's top two rows with the new 6-KPI-card layout plus allocation bar.

**Changes:**
- `app/static/index.html`: Replaced `summary-cards` section with new `kpi-grid` (6 cards) and `allocation-bar-row` (full-width). Row 2 (concentration cards) left unchanged.
- `app/static/style.css`: Added `.kpi-grid` (6-col grid), `.kpi-card`, accent strips (teal/green/gold), badge styles, `.allocation-bar-row`, updated responsive breakpoints.
- `app/static/app.js`: New `renderSummary()` populates 6 KPI cards with correct data and colours. HHI pill colour thresholds updated to green <1000 / amber 1000–1800 / red >1800.

**Note:** DeGiro API does not expose realized gains. `kpi-realized` uses `true_total_pl` (portfolio+cash minus net deposits) as a proxy when deposits exist; otherwise shows "—" with "no deposit data".
