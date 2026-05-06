---
name: 260428-fix-isin-lse-fallback-eur-positions
description: Fix ISIN LSE fallback for EUR-position ETFs — 3-layer fix (competing exchanges block, self-healing suffix retry, bundled overrides)
status: completed
---

Three-layer fix applied:

1. **Competing exchanges block in `_resolve_by_isin()` second pass** (`market_data.py:249-253, 290-291`):
   - Added `_competing_exchanges` set built from `currency_map` excluding `position_currency`
   - Second pass now skips any exchange in `_competing_exchanges` — EUR positions can never fall back to LSE or US

2. **Self-healing suffix retry in `enrich_position()`** (`market_data.py:895-918`):
   - After evicting stale cache on currency mismatch, before keeping DeGiro price, tries `.AS`, `.DE`, `.PA`, `.MI` suffixes directly
   - Only fires for IE/LU ISINs with EUR position and yf_currency mismatch
   - On success: updates cache and replaces ticker — position gets full RSI/52w metrics

3. **Permanent bundled overrides** (`bundled_overrides.json`):
   ```
   IE00B53L4350 → SXRU.DE
   IE00BYWQWR46 → ESPO.AS
   IE00BKM4H312 → QDIV.AS
   IE00BL0BMZ89 → GOAT.AS
   IE00B42NKQ00 → IUES.AS
   IE00BZCQB185 → NDIA.AS
   IE00BMC38736 → SMH.AS
   IE00BJ38QD84 → R2US.AS
   ```
   All 7 known-bad instruments resolve via override immediately on next enrichment.

**Post-push actions required:**
1. `DELETE /api/admin/symbol-cache` — evict stale `.L` entries
2. Run Update Prices — all 7 should resolve via bundled_overrides instantly, no currency mismatch warnings