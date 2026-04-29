---
name: 260429-oyv
description: 260429-daily-change-and-benchmark-style
type: quick
status: in_progress
created: "2026-04-29"
quick_id: 260429-oyv
slug: 260429-daily-change-and-benchmark-style
---

# Plan: 260429-daily-change-and-benchmark-style

Two independent changes.

## Task 1: daily_change_pct from snapshot delta

**Backend (main.py)** — `/api/portfolio-raw` endpoint (line 626)

**Files:** `app/main.py`

**Action:** After `portfolio = _build_raw_portfolio_summary(...)` and before the `return portfolio`, add snapshot-based daily change calculation.

Pseudocode:
```python
# snapshot-based daily change
from app.snapshots import load_snapshots
snaps = load_snapshots()
today_str = datetime.now().strftime("%Y-%m-%d")
yesterday_snap = None
for s in reversed(snaps):
    if s["date"][:10] < today_str:
        yesterday_snap = s
        break
if yesterday_snap and yesterday_snap.get("total_value_eur"):
    prev = yesterday_snap["total_value_eur"]
    curr = portfolio["total_value_eur"]
    portfolio["daily_change_pct"] = round((curr - prev) / prev * 100, 2)
    portfolio["daily_change_eur"] = round(curr - prev, 2)
else:
    portfolio["daily_change_pct"] = None
    portfolio["daily_change_eur"] = None
```

**Verify:** Read `app/main.py` around line 656 (after `_build_raw_portfolio_summary` call), confirm snapshot code added.

## Task 2: Benchmark chart styling

**Frontend (app.js)** — `renderBenchmark()` chart config around line 532

**Files:** `app/static/app.js`, `app/static/index.html`

**Action:** Update benchmark Chart.js datasets and scales styling.

Datasets:
- Portfolio: `borderColor: '#01696f'`, `backgroundColor: 'rgba(1,105,111,0.08)'`, `fill: true`, `tension: 0.3`, `pointRadius: 3`, `borderWidth: 2`
- Benchmark (VUSA/S&P 500): `borderColor: '#d97706'`, `backgroundColor: 'transparent'`, `fill: false`, `tension: 0.3`, `pointRadius: 3`, `borderWidth: 2`, `borderDash: [4, 3]`

Scales:
- x + y: `ticks color '#888'`, `grid color '#2a2a2a'`, `font Inter 10px`
- y: add `callback: v => '€' + Math.round(v / 1000) + 'k'`

Plugins:
- legend: `position 'bottom'`, `labels color '#888'`, `font Inter 10px`

**index.html:** Wrap benchmark section in `.card` div if not already present.

**Verify:** Confirm datasets use exact colors and `fill: true` for portfolio, `borderDash` for benchmark.

## must_haves
- [ ] `/api/portfolio-raw` response includes `daily_change_pct` and `daily_change_eur` (or nulls)
- [ ] Benchmark chart portfolio line uses `fill: true` + teal color
- [ ] Benchmark chart benchmark line uses `borderDash: [4, 3]`
- [ ] index.html benchmark section wrapped in `.card`