---
name: 20260429-portfolio-deviation-diagnostic
description: Add [DIAG] logging to surface ~2% portfolio deviation source
status: complete
---

## Done
- `price_source` field added to all enrichment paths: `"batch"` (fresh yf.download), `"cache"` (_price_cache hit), or missing (no price)
- Per-position `[DIAG]` log line: symbol, qty, price, value_eur, src, ccy
- `[DIAG] TOTAL COMPUTED:` logged after enrichment
- `[DIAG] DEGIRO REPORTED TOTAL:` logged in `_do_enrich_session()` before saving snapshot

## What to look for in logs
1. `price_source="cache"` on any symbol → stale price leaking through
2. `currency != "EUR"` with no FX conversion → raw USD/GBP price summed as EUR
3. `qty=0` or `price=None` → position contributing 0 to total
4. One symbol with a suspiciously large value gap → likely the ~2% source
