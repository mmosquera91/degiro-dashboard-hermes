---
name: 260428-fix-update-prices-toast
description: Add toast notifications to Update Prices operation
status: pending
created: 2026-04-28
---

Add toast/chip notifications to Update Prices button click:

1. **Find Update Prices handler** — locate where the button's onClick is handled
2. **Add toast logic** — inject toast calls at: click (updating), success (auto-dismiss 3s), error (persistent)
3. **Use document.body** — append toast to body for visibility regardless of scroll/container state
4. **No changes** to enrichment flow, lock logic, or backend