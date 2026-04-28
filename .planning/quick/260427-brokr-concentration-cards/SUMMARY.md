---
name: brokr-concentration-cards
description: Add three concentration metric cards (Top Holding, Top 5 Weight, HHI) to portfolio dashboard summary
status: complete
---

## Summary

Added three concentration metric cards to the portfolio dashboard summary section.

## Changes

- **app/static/index.html**: Added three card elements (`card-top-holding`, `card-top5-weight`, `card-hhi`) to the summary grid after the positions card
- **app/static/app.js**: Added `renderConcentration()` function that computes and renders:
  - Top holding weight + name
  - Top 5 concentration with amber/red color coding
  - HHI score with color coding and diversification subtitle
- Called `renderConcentration()` from `renderDashboard()` after `renderSummary()`

## Verification

- Cards are placed in the summary section alongside existing cards (total-value, total-pl, etc.)
- IDs match spec: `card-top-holding`, `card-top5-weight`, `card-hhi`
- Color thresholds match spec: positive (<40/<1500), amber (40-60/1500-2500), negative (>60/>2500)