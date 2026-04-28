# 260428-skip-yf-delay-on-batch-hit

## Problem
After batch price fetch via yf.download(), enrich_position() still calls
_yf_throttle() before ticker.history() at line 993 even when the price came
from the batch and no yfinance call for price was made. This adds ~0.2s per
position unnecessarily.

## Fix
- Removed unconditional _yf_throttle() at line 993 (before ticker.history())
- Added _yf_throttle() inside the else block (line 1024), only when fetching
  price from history (price_batch miss AND cached_price miss/stale/wrong currency)
- The throttle at line 900 (before ticker.info) is preserved — ticker.info
  always runs for fundamental data

## Result
- price_batch hit + currency-safe: no throttle, no sleep
- cached_price hit + currency-safe: no throttle, no sleep
- price_batch miss + cached_price miss/stale: throttle before history fetch
- ticker.info always throttled (always called for sector/country/PE/52w from info)
