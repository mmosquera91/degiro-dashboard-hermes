---
name: 260429-dashboard-polish
description: Restore card styling to allocation bar and row 2 concentration cards per mock
type: quick
---

Restore allocation bar and row 2 card styling from mock.

--- FILES CHANGED ---

1. app/static/style.css
   - Added CSS variables: --radius-lg: 12px, --space-3/4/5, --shadow-sm/md, --surface-offset
   - Updated .card: radius-lg, padding var(--space-4) var(--space-5), box-shadow var(--shadow-sm), hover shadow transition
   - Added .card-label: font-size var(--text-xs), font-weight 500, color color-text-muted
   - Added .card-value: clamp(), font-weight 700, letter-spacing -0.02em, tabular-nums
   - Added .card-sub: font-size var(--text-xs), color text-muted
   - Updated .allocation-bar-row: radius-lg, var(--space-4/5) padding, box-shadow var(--shadow-sm)
   - Updated .allocation-bar: height 8px, border-radius 999px, background surface-offset
   - Updated .allocation-bar-title: font-size var(--text-xs), letter-spacing 0.05em, text-transform uppercase
   - Added .bar-stocks (teal) / .bar-etfs (gold) swapped from original
   - Added .allocation-dot (8px circle) + .dot-teal/.dot-gold + .allocation-footer-label
   - Added .hhi-pill with .diversified/.concentrated/.high-risk colour classes
   - Updated .summary-row-centered: display:grid, repeat(3,1fr) instead of flex

2. app/static/index.html
   - Updated allocation bar title: "ALLOCATION — STOCKS VS ETFS"
   - Added footer dots+labels to allocation bar (dot-teal left, dot-gold right)
   - Added hhi-pill class to HHI card-sub span

3. app/static/app.js
   - renderSummary: allocation labels simplified (no "Stocks" / "ETFs" prefixes)
   - renderConcentration: top5 weight now neutral (no colour), hhi uses pill class instead of inline colour on value

--- STYLING SUMMARY ---
- Allocation bar: full card with radius-lg + shadow-sm, 8px track, 999px bar radius, grid 1fr auto 1fr header
- Row 2 cards: same .card base class as row 1 (radius-lg, shadow, hover)
- HHI pill: green/gold/red backgrounds on pill span, not on value
- Top 5: neutral colour on value