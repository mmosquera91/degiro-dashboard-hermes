# Fix double FX conversion in DeGiro portfolio

## Problem
DeGiro's portfolio API `value` field is pre-converted to account base currency (EUR).
`fetch_portfolio()` stored it as `current_value`, then `enrich_positions()` applied
FX conversion again — double conversion, ~11% under.

## Fix
In `app/degiro_client.py` `fetch_portfolio()`, always derive `current_value` from
`current_price × quantity` (in native trading currency) instead of using DeGiro's
pre-converted `value` field. `enrich_positions()` then applies FX exactly once.

## Changed
`app/degiro_client.py` — the "Combine position + product data" loop in `fetch_portfolio()`
