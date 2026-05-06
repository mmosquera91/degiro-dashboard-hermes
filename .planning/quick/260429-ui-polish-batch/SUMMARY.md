---
name: 260429-ui-polish-batch
description: UI polish batch — allocation bar grid, alert cards top-border, EUR delta in winners/losers, cash amber tint
type: quick
status: complete
---

## Summary

Single commit (cc68afb) touching 3 files, 89 insertions, 90 deletions.

### Changes Applied

1. **Allocation bar (style.css + index.html)**: Replaced old 3-column flex layout (allocation-bar-left / bar-container / allocation-bar-right) with `.allocation-bar-header` 3-column grid + standalone bar. HTML restructured to match.

2. **Alert cards (style.css)**: Replaced `border-left: 3px solid` with `border-top: 2px solid` + `border-radius: var(--radius-lg)` + tinted backgrounds for warn (gold) and critical (red).

3. **Section titles (style.css)**: Added `border-top: 1px solid var(--border)` to `.section-title`. Added `.buy-radar-section .section-title` and `.winners-losers-section .section-title` with `border-top` + `padding-top: 8px`.

4. **Winners/Losers EUR delta (app.js)**: Restructured wl-item HTML to show name + symbol inline, right-aligned div with % and EUR P&L sub-line. `unrealized_pl_eur` derived via `deriveEurPl()` lookup from `portfolioData.positions` by symbol.

5. **Cash card amber tint (app.js)**: After setting kpi-cash value, if `cashPct < 1` apply gold `border-top-color`, tinted `background`, and gold `color` on sub label.
