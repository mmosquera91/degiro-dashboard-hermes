# Fix: Portfolio enrichment fails with "Failed to fetch portfolio" after raw data shows

## Problem
- Dashboard shows "Failed to refresh: Failed to fetch portfolio" error toast
- Raw portfolio IS shown (from `/api/portfolio-raw`)
- No technical data populated (RSI, 52w high/low, sector, etc.)

## Root Cause
When `/api/portfolio` is called after `/api/portfolio-raw`, the enrichment chain throws an unhandled exception:
1. `enrich_positions()` may throw if yfinance calls fail
2. `compute_health_alerts()` may throw if `positions` is `None` (line 81: `for p in positions:` would TypeError)
3. Any exception propagates to the catch-all at line 479-481, returning 500 "Failed to fetch portfolio"

## Fix
Add defensive exception handling around `compute_health_alerts()` and `compute_scores()` calls in `/api/portfolio`. If these fail, return the portfolio without health alerts rather than crashing entirely.

### Changes
**app/main.py** - Wrap health alerts and scores computation in try/except:
- Line ~432: Wrap `compute_health_alerts()` call in try/except, log warning on failure
- Line ~427: Wrap `compute_scores()` call in try/except, log warning on failure

## Verification
1. Start the server
2. Connect to DeGiro
3. Verify portfolio loads with technical data populated
4. Verify no "Failed to refresh" error appears
