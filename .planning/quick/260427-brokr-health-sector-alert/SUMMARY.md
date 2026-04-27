---
name: brokr-health-sector-alert
description: Fix sector concentration health alert to exclude ETFs
type: quick
status: complete
completed: 2026-04-27
---

## Done

- `app/health_checks.py`: Changed `_check_sector_weighting` to accept `positions` instead of `sector_breakdown`, filter to `asset_type != "ETF"`, compute stock-only sector breakdown, and updated alert message to say "Stock sector concentration: {sector} is {pct:.1f}% of stock holdings".
- Verified: Python syntax valid, imports clean.
