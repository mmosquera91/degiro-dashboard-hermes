---
quick_id: 260527-otn
slug: fix-indexa-data-extraction
status: complete
commit: 3b259c7
completed_at: 2026-05-27
---

# Summary: Fix Indexa Capital data extraction

## Outcome

Indexa tab KPIs and charts will now populate because the backend extracts
the right fields from the actual Indexa response shape.

## Changes

- `app/main.py`
  - `/api/indexa/portfolio` reads totals from `raw.portfolio` and positions from
    `raw.instrument_accounts[0].positions`. Each position is flattened to
    `{name, isin, amount, cost_amount, weight, asset_class, price, titles}`
    with `weight = amount / instruments_amount * 100`.
  - `/api/indexa/performance` converts `raw.return.total_amounts` (dict) into a
    sorted `series` array of `{date, value}` pairs and surfaces top-level KPIs:
    `time_return`, `time_return_annual`, `time_return_last_year`,
    `time_return_last_month`, `time_return_last_week`, `pl`, `investment`,
    `total_amount`, `volatility`, `sharpe_ratio`, `max_drawdown`.
  - Added `from typing import Any` (needed by the new typed local).
- `app/schemas.py`
  - Added `total_invested`, `cash` to `IndexaPortfolioResponse`.
  - Added the KPI fields above to `IndexaPerformanceResponse`.
  - Kept `extra="allow"` so the `raw` payload and any future fields pass through.
- `app/static/app.js`
  - `indexaInvestedTotal()` now prefers `indexaPortfolio.total_invested` and
    `indexaPerformance.investment`.
  - `indexaReturnEur()` prefers `indexaPerformance.pl`.
  - `indexaReturnPct()` prefers `indexaPerformance.time_return * 100` (Indexa
    returns fractional values).
  - Legacy `raw.return.*` fallbacks retained.

## Verification

- `python3 -m py_compile app/main.py app/schemas.py` → OK
- `node` syntax-check of `app/static/app.js` → OK
- No Indexa tests existed pre-change; none added (out of scope).

## Manual smoke (recommended)

1. Restart backend (hot-reload should pick this up): `docker compose -f docker-compose.dev.yml restart backend`
2. Open `/api/indexa/portfolio` — confirm `total_value`, `total_invested`,
   `cash`, and a flat `positions[]` array with `name`/`isin`/`amount`/`weight`.
3. Open `/api/indexa/performance` — confirm `series` is a sorted array and
   `pl`, `investment`, `time_return`, `volatility` etc. are present.
4. Open the Indexa tab in the browser — KPIs, allocation doughnut, performance
   line chart, and funds table should all render with real data.

## Out of scope (not touched)

- `app/indexa_client.py` — untouched.
- DeGiro flow — untouched.

## Commit

`3b259c7` — fix(indexa): extract correct fields from Indexa API response
