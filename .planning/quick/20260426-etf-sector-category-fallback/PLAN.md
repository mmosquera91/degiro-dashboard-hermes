---
name: 20260426-etf-sector-category-fallback
description: Fix ETF sector fallback in enrich_position() — use category/fundFamily instead of sector
status: complete
completed_at: "2026-04-26"
---

# ETF Sector Category Fallback

## Problem
`enrich_position()` in `app/market_data.py` assigns sector as:
```python
position["sector"] = info.get("sector", info.get("industry", None))
```

yfinance never populates "sector" for ETFs — that field is stock-only. ETFs have
"category" (e.g. "Europe Large-Cap Blend Equity") and "fundFamily" (e.g. "iShares").
Both were ignored, so all ETFs landed in "Unknown" in the sector breakdown chart.

## Change
Inside `enrich_position()`, replaced the sector assignment with ETF-aware logic:
- ETFs: try `category` → `fundFamily` → `industry` → None
- Stocks: try `sector` → `industry` → None (unchanged behavior)

## File Changed
- `app/market_data.py` — lines 343–356

## Verification
- Code inspection confirms the new logic is in place
- No other changes were made
