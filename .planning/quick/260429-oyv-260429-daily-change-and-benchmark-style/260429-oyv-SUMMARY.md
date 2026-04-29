---
name: 260429-oyv
description: 260429-daily-change-and-benchmark-style
type: quick
status: complete
completed: "2026-04-29"
---

# Summary: 260429-daily-change-and-benchmark-style

## Changes Applied

### Task 1: daily_change_pct from snapshot delta

**`app/main.py`** — `/api/portfolio-raw` endpoint (lines 657-672)

Added snapshot-based daily change calculation after `_build_raw_portfolio_summary()` returns:
- Finds the most recent snapshot with `date[:10] < today_str` (yesterday or earlier)
- If found, computes `daily_change_pct` as percentage change and `daily_change_eur` as absolute change
- Falls back to `None` for both fields if no prior snapshot exists

**Frontend (`app/static/app.js`)** — `dailyBadge` already uses `d.daily_change_pct != null` check with `fmtPct()` and `badge-positive`/`badge-negative` classes — no changes needed.

### Task 2: Benchmark chart styling

**`app/static/app.js`** — `renderBenchmark()` chart config (lines 532-586)

Updated Chart.js config:
- Portfolio line: `fill: true`, `backgroundColor: rgba(1,105,111,0.08)`, `tension: 0.3`, `borderWidth: 2`
- Benchmark (S&P 500) line: `borderDash: [4, 3]`, `fill: false`, `tension: 0.3`, `borderWidth: 2`
- Y-axis ticks: `callback: v => '€' + Math.round(v / 1000) + 'k'`
- Legend: `position: "bottom"`, `size: 10`

**`app/static/index.html`** — Benchmark section wrapped in `.card` div.

## Verification

- [x] `/api/portfolio-raw` response includes `daily_change_pct` and `daily_change_eur` (or nulls when no prior snapshot)
- [x] Benchmark chart portfolio line uses `fill: true` + teal color
- [x] Benchmark chart benchmark line uses `borderDash: [4, 3]`
- [x] index.html benchmark section wrapped in `.card`

## Commit

`0aefb4f` — feat: add snapshot-based daily_change_pct and restyle benchmark chart