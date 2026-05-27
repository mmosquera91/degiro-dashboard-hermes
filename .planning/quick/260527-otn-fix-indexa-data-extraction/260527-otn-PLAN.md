---
quick_id: 260527-otn
slug: fix-indexa-data-extraction
description: Fix Indexa Capital integration — backend extracts wrong fields from Indexa API response, leaving frontend KPIs/charts empty.
status: planned
---

# Plan: Fix Indexa Capital data extraction

## Goal

Indexa tab renders empty KPIs/charts because the backend `/api/indexa/portfolio` and `/api/indexa/performance` routes extract fields that don't exist in the actual Indexa response shape. Realign extraction to the documented response shape so the frontend can display value, invested, return, performance time series, and fund table correctly.

## Scope

- `app/main.py` — `/api/indexa/portfolio` and `/api/indexa/performance` routes
- `app/schemas.py` — `IndexaPortfolioResponse` and `IndexaPerformanceResponse` field additions
- `app/static/app.js` — frontend KPI helpers that prefer the corrected flat backend fields

Out of scope:
- `app/indexa_client.py` — not touched
- DeGiro flow — not touched

## Actual Indexa response shapes (per user-provided spec)

`/portfolio`:
- `raw.portfolio = {cash_amount, instruments_amount, instruments_cost, total_amount, ...}`
- `raw.instrument_accounts[0].positions = [{amount, cost_amount, instrument: {name, isin_code, asset_class, ...}, price, titles}, ...]`
- `raw.cash_accounts[0].amount`

`/performance`:
- `raw.return = {time_return, time_return_last_week, time_return_last_month, time_return_last_year, time_return_annual, XIRR, investment, pl, total_amount, total_amounts (dict of date→value), index (dict), ...}`
- `raw.volatility`, `raw.sharpe_ratio`
- `raw.drawdowns = {max_drawdown, max_drawdown_EUR}`
- `raw.history` (monthly time series)

## Tasks

### Task 1 — Fix `/api/indexa/portfolio` extraction

In `app/main.py`:
- Pull `portfolio = raw["portfolio"]` for totals (`total_amount` → `total_value`, `instruments_cost` → `total_invested`, `cash_amount` → `cash`).
- Pull positions from `raw["instrument_accounts"][0]["positions"]` if present.
- Flatten each position to `{name, isin, amount, cost_amount, weight, asset_class, price, titles}` where `name` and `isin` come from the nested `instrument` object and `weight = amount / instruments_amount * 100` when computable.
- Return the existing `raw` payload untouched for any frontend that still reaches into it.

### Task 2 — Fix `/api/indexa/performance` extraction

In `app/main.py`:
- Convert `raw["return"]["total_amounts"]` dict to a sorted array of `{date, value}` pairs as `series`.
- Surface KPIs at the top level: `time_return`, `time_return_annual`, `time_return_last_year`, `time_return_last_month`, `time_return_last_week`, `pl`, `investment`, `total_amount`, `volatility`, `sharpe_ratio`, `max_drawdown`.
- Return `raw` untouched.

### Task 3 — Update response schemas

In `app/schemas.py`:
- Add `total_invested`, `cash` to `IndexaPortfolioResponse`.
- Add the KPI fields above to `IndexaPerformanceResponse`.
- Keep `extra="allow"` so unknown fields pass through.

### Task 4 — Update frontend KPI helpers

In `app/static/app.js`:
- `indexaInvestedTotal()`: prefer `indexaPortfolio.total_invested` and `indexaPerformance.investment` over the deep `raw.return.*` candidates.
- `indexaReturnEur()`: prefer `indexaPerformance.pl`.
- `indexaReturnPct()`: prefer `indexaPerformance.time_return * 100` when present (Indexa returns fractional, e.g. `0.527` for 52.7%).
- Keep legacy fallback paths so any pre-existing raw probes continue to work.

## Verification

- `python -m py_compile app/main.py app/schemas.py` succeeds.
- Manual: visit `/api/indexa/portfolio` and confirm `total_value`, `total_invested`, `cash`, and flattened `positions[]` are populated.
- Manual: visit `/api/indexa/performance` and confirm `series` is a sorted array and KPI fields are present.
- Manual: Indexa tab in browser renders KPIs (value, invested, return €, return %), allocation chart, performance chart, and funds table.

## Commits

- One atomic code commit covering backend + schemas + frontend.
- Final docs commit for PLAN.md, SUMMARY.md, STATE.md.
