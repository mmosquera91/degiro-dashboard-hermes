# brokr-health-sector-alert

Fix sector concentration health alert to exclude ETF positions, which produce false positives due to fund manager names being used as sector labels.

## Changes

**app/health_checks.py:**

1. Line 28: Change `_check_sector_weighting(sector_breakdown)` → `_check_sector_weighting(positions)`
2. `_check_sector_weighting` function (line 60): Replace `sector_breakdown: dict` parameter with `positions: list`. Filter to `asset_type != "ETF"`, compute `stock_sector_breakdown` from stocks only, and update message to say "Stock sector concentration: {sector} is {pct:.1f}% of stock holdings".
