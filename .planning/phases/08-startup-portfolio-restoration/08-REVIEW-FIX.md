---
phase: 08-startup-portfolio-restoration
fixed_at: 2026-04-24T00:00:00Z
review_path: .planning/phases/08-startup-portfolio-restoration/08-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 08: Code Review Fix Report

**Fixed at:** 2026-04-24T00:00:00Z
**Source review:** .planning/phases/08-startup-portfolio-restoration/08-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 2 (WR-01, WR-02)
- Fixed: 2
- Skipped: 0

## Fixed Issues

### WR-01: Blocking DNS call inside async startup handler

**Files modified:** `app/main.py`
**Commit:** 093f6fe
**Applied fix:** Wrapped `socket.gethostbyname("google.com")` in `await asyncio.to_thread()` to avoid blocking the asyncio event loop.

### WR-02: Misleading error message on portfolio fetch

**Files modified:** `app/main.py`
**Commit:** 093f6fe
**Applied fix:** Split the session validation into two separate checks:
- `if _session["trading_api"] is None`: raises "Session expired or not authenticated. Please reconnect via the UI." (actual invalid/missing session)
- `if not _is_session_valid()`: raises "Session expired. Please refresh your connection via the UI." (valid session but expired credentials)

This accurately distinguishes between a missing/invalid session and a valid session whose DeGiro credentials have simply expired.

---

_Fixed: 2026-04-24T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_