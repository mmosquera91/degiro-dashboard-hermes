# 260427-snapshot-management-api-and-ui

Add GET /api/snapshots (list lightweight) and DELETE /api/snapshots/{date_str} endpoints,
plus a Snapshot Manager UI panel in the dashboard.

## Changes

### 1. app/main.py — add two endpoints after existing /api/* routes
- `GET /api/snapshots` — list all snapshots, returns date/total_value_eur/benchmark_value/benchmark_return_pct/has_portfolio_data (no portfolio_data payload)
- `DELETE /api/snapshots/{date_str}` — delete snapshot file, validate date format, prevent deleting last snapshot, invalidate benchmark cache

### 2. app/static/index.html — replace Attribution <details> block
- Prepend new `<details id="snapshot-manager">` before the attribution block
- Attribution block unchanged structurally, only reordered

### 3. app/static/app.js — add renderSnapshotManager() and toggle hook
- `renderSnapshotManager()` fetches /api/snapshots, renders table with date/value/benchmark return/has data/delete button
- Delete button calls DELETE /api/snapshots/{date} and re-renders on success
- Hook to snapshot-manager details toggle event
