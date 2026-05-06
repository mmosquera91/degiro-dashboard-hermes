---
name: 260429-rollback-alloc-bar
description: Rollback d686b9f and re-apply simplified CSS-only alloc bar fix
type: quick
status: complete
---

## Summary

Reverted commit d686b9f via `git revert --no-edit` then applied the simplified spec:

**style.css** — `.allocation-bar-row` replaced with flex-column layout, gap 10px; new `.allocation-bar-header` grid class added; removed old grid/flex properties.

**index.html** — `kpi-card` class added to `card-top-holding`, `card-top5-weight`, `card-hhi`.

**app.js** — no changes.

Committed as `41d04bd`.
