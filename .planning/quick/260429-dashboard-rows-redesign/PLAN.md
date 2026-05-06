---
name: 260429-dashboard-rows-redesign
description: Replace top two dashboard rows with 6 KPI cards + allocation bar
type: quick
---

Replace the current summary-cards row with a new 6-column KPI grid, add a full-width allocation bar between row 1 and row 2, and add HHI pill colour logic. No changes to row 2 (concentration cards).

--- FILES TO CHANGE ---

1. app/static/index.html
   - Replace the `<section class="summary-cards">` block (lines 72-111) with:
     a. New row-1 grid div: `kpi-grid` with 6 `kpi-card` divs
     b. New full-width allocation-bar div between row 1 and the existing `summary-row-centered` section
   - Each kpi-card has: card-label, card-value (main), card-sub, optional badge, optional accent-strip div
   - Keep the `summary-row-centered` section (lines 113-130) unchanged

2. app/static/style.css
   - Add `--space-3: 12px` variable if not present (gap value from current summary-cards)
   - Add `.kpi-grid`: `display: grid; grid-template-columns: repeat(6, 1fr); gap: var(--space-3);`
   - Add `.kpi-card`: same base card styles as `.card`, plus `display: flex; flex-direction: column; gap: 4px;`
   - Add `.kpi-card .card-label`: same as existing `.card-label`
   - Add `.kpi-card .card-value`: `font-size: 1.5rem; font-weight: 600;`
   - Add `.kpi-card .card-sub`: `font-size: 0.78rem; color: var(--text-dim);`
   - Add `.kpi-card .badge`: pill style badge (small rounded bg, appropriate color)
   - Add `.accent-strip`: 2px top border via `border-top: 2px solid COLOR`
   - Add `.accent-teal { border-top-color: var(--teal); }`
   - Add `.accent-green { border-top-color: var(--green); }`
   - Add `.accent-gold { border-top-color: #d97706; }`
   - Add `.allocation-bar-row`: full-width card, flex layout (space-between), contains left/right labels and the bar
   - Add `.allocation-bar-row .bar-container`: flex: 1, centered, max-width 400px
   - Add `.allocation-bar-row .bar`: height 10px, rounded, background var(--border), flex row (no direction flip — ETF on left, STOCK on right as two segments)
   - Add `.allocation-bar-row .bar-etf`: background var(--teal)
   - Add `.allocation-bar-row .bar-stock`: background #d97706
   - Add `.hhi-pill` with colour logic (inline style from JS, or CSS classes .hhi-low/med/high)
   - Update responsive at 768px: `.kpi-grid { grid-template-columns: repeat(3, 1fr); }`
   - Update responsive at 420px: `.kpi-grid { grid-template-columns: repeat(2, 1fr); }`

3. app/static/app.js
   - In renderSummary(), after populating existing fields, update/populate the 6 new KPI cards:
     Card 1 (Portfolio): `fmtEur(d.total_value + (d.cash_available || 0))` with `private-value`
     Card 2 (Invested): `fmtEur(d.total_value)` with `private-value`; sub: `"{n} positions"`
     Card 3 (Cash): `fmtEur(d.cash_available)` with `private-value`; sub: `"{pct}% of portfolio"` where pct = cash/total*100
     Card 4 (Unrealized P&L): `fmtEur(d.unrealized_pl_total)` with `private-value`; accent-green; sub: badge with `fmtPct(d.unrealized_pl_total_pct)` with ▲/▼ prefix based on sign
     Card 5 (Realized P&L): use `d.true_total_pl` (proxy for realized+unrealized since DeGiro doesn't separate); accent-gold; sub: "closed trades"
       - Note: `true_total_pl` is only set when `total_deposit_withdrawal > 0`, otherwise null
       - When null, show "—" with sub "no deposit data"
     Card 6 (Positions): `d.num_positions`; sub: "{n} ETFs · {m} stocks" derived by counting positions[i].asset_type
   - For the allocation bar row: update the left/right labels with euro amounts and percentages (stocks on left, ETFs on right as per spec)
   - Add HHI pill colour logic in renderConcentration(): set background colour inline on the pill based on hhi value thresholds

--- DATA NOTES ---
- `d.total_value`: sum of position values (excludes cash)
- `d.cash_available`: cash balance in EUR
- `d.unrealized_pl_total`: total_value - total_invested
- `d.unrealized_pl_total_pct`: unrealized_pl_total / total_invested * 100
- `d.true_total_pl`: total_value + cash - total_deposit_withdrawal (only when deposits exist)
- `d.num_positions`: count of positions
- ETF allocation: `d.etf_allocation_pct`, stock: `d.stock_allocation_pct`
- Count ETFs/stocks: positions.filter(p => p.asset_type === "ETF"/"STOCK").length
- DeGiro has no realized gains data — true_total_pl is used as proxy label "Realized P&L" but note it reflects total P&L vs cost basis

--- STYLE NOTES ---
- Positive P&L: color var(--green)
- Negative P&L: color var(--red)
- Badge: small rounded pill with coloured background (green-dim/red-dim/teal-dim)
- accent-strip: 2px border-top with the accent color
- Cards without accent: no strip (border-top transparent or absent)
- Max-width 1200px on main content, centered (margin-inline: auto)
