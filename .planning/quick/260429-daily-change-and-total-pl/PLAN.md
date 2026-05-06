---
name: 260429-daily-change-and-total-pl
description: Daily change % badge with EUR, plus total P&L sub-line on Portfolio card
status: complete
---

Two changes — backend already done (daily_change_pct was in main.py), focus is frontend:

1. Daily badge: show `▲ 2.34% (€123.45)` instead of `▲ 2.34% today`
2. Total P&L sub-line: add `id="kpi-portfolio-pl"` below `#kpi-portfolio-sub` in index.html
3. CSS: `.pl-total { color: var(--green); font-size: 0.72rem; font-weight: 500; margin-top: 2px; }`