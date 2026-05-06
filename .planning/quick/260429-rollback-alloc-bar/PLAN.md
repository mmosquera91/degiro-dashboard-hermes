---
name: 260429-rollback-alloc-bar
description: Rollback d686b9f and re-apply simplified CSS-only alloc bar fix
type: quick
---

## Task
Rollback commit d686b9f and apply simplified CSS-only allocation bar fix (no new HTML elements, no new JS).

## Steps

### 1. Rollback
```bash
git revert d686b9f --no-edit
```

### 2. style.css — Replace `.allocation-bar-row` entirely with:
```css
.allocation-bar-row {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-4) var(--space-5);
  box-shadow: var(--shadow-sm);
  margin-bottom: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.allocation-bar-header {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
}
```
Remove: `grid-template-columns`, `align-items`, `gap:20px` from `.allocation-bar-row`.
Keep: `.allocation-bar-left`, `.allocation-bar-right`, `.bar-container` unchanged.

### 3. index.html — Add `kpi-card` class to row 2 cards:
- `id="card-top-holding"` → `class="card kpi-card"`
- `id="card-top5-weight"` → `class="card kpi-card"`
- `id="card-hhi"` → `class="card kpi-card"`

### 4. app.js — NO changes needed.

### 5. Commit
