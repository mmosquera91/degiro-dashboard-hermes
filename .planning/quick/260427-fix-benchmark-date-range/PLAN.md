# Plan: fix-benchmark-date-range

Fix `fetch_benchmark_series()` to handle:
1. Weekend/holiday gaps when start/end are 1 day apart
2. New portfolios less than 7 days old

Changes in `app/snapshots.py`:
- Add `timedelta` import
- Pad `end_dt` +1 day for yfinance's exclusive end boundary
- If range < 7 days, pad `start_dt` back to 7 days before end
- Use padded dates for `yf.download()` call
- Filter output to exclude padded days from chart