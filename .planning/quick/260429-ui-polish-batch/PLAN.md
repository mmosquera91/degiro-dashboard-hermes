# 260429-ui-polish-batch

Single commit touching style.css, index.html, app.js.
No new dependencies. No structural rewrites.

## Changes

1. **Allocation bar (style.css)**: Replace `.allocation-bar-row` with new grid-based layout. Add `.allocation-bar-header` with 3-column grid, `.allocation-bar-title` center styles, standalone `.allocation-bar`, `.bar-stocks`, `.bar-etfs`. Remove old `.allocation-bar-left/.right/.bar-container` blocks.
2. **Allocation bar (index.html)**: Replace allocation-bar-row HTML to match new CSS class structure with `.allocation-bar-header` + left/center/right columns + standalone bar.
3. **Row 2 cards (index.html)**: Add `kpi-card` to `card-top-holding`, `card-top5-weight`, `card-hhi` divs.
4. **Alert cards (style.css)**: Replace `.alert-card` base + warn/critical with top-border + tinted background variant.
5. **Section titles (style.css)**: Add `border-top: 1px solid var(--border)` to `.section-title`. Add `.buy-radar-section .section-title` and `.winners-losers-section .section-title` with `border-top: 1px solid var(--border); padding-top: 8px`.
6. **Winners/Losers EUR delta (app.js)**: In `renderWinnersLosers()`, restructure wl-item HTML to show name/symbol inline, then right-aligned div with % and EUR delta sub-line. Derive `unrealized_pl_eur` from `current_price - avg_buy_price) * quantity`.
7. **Cash card amber tint (app.js)**: After setting kpi-cash value, apply gold border-top + tinted background if cashPct < 1.
