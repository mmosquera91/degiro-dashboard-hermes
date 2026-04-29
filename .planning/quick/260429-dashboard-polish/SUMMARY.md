---
name: 260429-dashboard-polish-summary
status: complete
---

Restored card styling to allocation bar and row 2 concentration cards.

**Changes:**
- `app/static/style.css`: Added CSS vars (radius-lg, space-3/4/5, shadow-sm/md, surface-offset), updated `.card` to use radius-lg + shadow + hover, added `.card-label` (font-weight 500, text-xs), `.card-value` (clamp, tabular-nums), `.card-sub` (text-xs), `.hhi-pill` with green/gold/red pill classes, `.allocation-dot` and footer labels, swapped bar-stocks/teal and bar-etfs/gold, updated `.allocation-bar-row` and `.allocation-bar-title` styling, changed `.summary-row-centered` to grid with 3 equal columns
- `app/static/index.html`: Updated allocation bar title to "ALLOCATION — STOCKS VS ETFS", added footer dots+labels to allocation bar, added `hhi-pill` class to HHI card-sub span
- `app/static/app.js`: Allocation labels simplified (no prefix text), top5 weight now neutral (no colour), HHI uses pill class instead of inline colour on value