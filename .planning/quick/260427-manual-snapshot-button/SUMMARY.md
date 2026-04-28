---
name: manual-snapshot-button
description: Add manual snapshot save button and API endpoint
type: project
status: complete
---

# Manual Snapshot Button — Complete

Added POST /api/snapshots/save endpoint and "Save Snapshot Now" button in the Snapshot Manager UI.

**Changes:**
- `app/main.py`: Added `/api/snapshots/save` endpoint
- `app/static/index.html`: Added save button above snapshot table
- `app/static/app.js`: Added click handler for save button