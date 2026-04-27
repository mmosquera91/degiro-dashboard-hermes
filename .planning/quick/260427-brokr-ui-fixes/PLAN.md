---
name: brokr-ui-fixes
description: Apply 5 UI fixes to brokr dashboard (remove currency chart, remove daily change card, add total P&L combined, center concentration cards, fix privacy button icon color)
type: quick
status: complete
---

Apply five small frontend fixes to app/static/ (HTML + app.js + CSS).

1. Remove currency exposure chart (HTML card + JS renderCharts block)
2. Remove daily change card (HTML card + JS renderSummary block)
3. Add Total P&L (Combined) card alongside existing Total P&L card
4. Wrap concentration cards (top holding, top 5 weight, HHI) in centered flex row
5. Fix #btn-privacy icon color: muted default, full text on hover, teal when active

No backend changes.
