# Manual Snapshot Button

Add a "Save Snapshot Now" button to trigger manual portfolio snapshots.

## Changes

### app/main.py
Add POST /api/snapshots/save endpoint that calls _save_snapshot_for_portfolio().

### app/static/index.html
Add "Save Snapshot Now" button in snapshot-manager <details> section.

### app/static/app.js
Add click handler for btn-save-snapshot that calls POST /api/snapshots/save.