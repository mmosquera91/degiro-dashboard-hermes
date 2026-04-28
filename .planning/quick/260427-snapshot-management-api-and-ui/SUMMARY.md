---
name: 260427-snapshot-management-api-and-ui
status: complete
---

# 260427-snapshot-management-api-and-ui — Complete

Added snapshot list/delete API and management UI panel.

## Changes

- `GET /api/snapshots` — lightweight list endpoint (no portfolio_data payload)
- `DELETE /api/snapshots/{date}` — delete snapshot with guard against deleting last snapshot
- Snapshot Manager `<details>` panel in dashboard, lazy-loads on open
- `renderSnapshotManager()` renders table with delete buttons
- Benchmark cache invalidated on delete
