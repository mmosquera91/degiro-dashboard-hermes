---
name: 20260424-portfolio-enrichment-fix
description: Fix "Failed to fetch portfolio" error after raw portfolio loads
status: complete
---

## What
Wrapped `compute_scores()` and `compute_health_alerts()` in defensive try/except in `/api/portfolio` endpoint (`app/main.py:426-446`).

## Why
When `/api/portfolio` was called after `/api/portfolio-raw`, any unhandled exception in scoring or health alert computation propagated to the top-level catch block, returning HTTP 500 "Failed to fetch portfolio". This caused the dashboard to show the error toast even though raw data had loaded.

## Changes
- `app/main.py`: Added try/except around `compute_scores()` and `compute_health_alerts()` calls with warning-level logging on failure
