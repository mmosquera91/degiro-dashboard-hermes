---
name: fix-benchmark-date-range
status: complete
date: 2026-04-27
---

## Summary

Fixed `fetch_benchmark_series()` in `app/snapshots.py`:
- Added `timedelta` import
- Padded `end_dt` +1 day so yfinance's exclusive end boundary captures today
- When date range < 7 days, padded `start_dt` back 7 days to ensure trading data coverage
- Updated `yf.download()` to use padded fetch dates
- Filtered output loop to skip dates < original `start_date` (excludes padding from chart)

Committed as `644ae9e`.