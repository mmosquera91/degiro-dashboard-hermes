---
phase: 05
slug: dashboard-polish
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-24
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Manual browser testing (no automated framework in project) |
| **Config file** | none — frontend-only phase |
| **Quick run command** | N/A — manual verification |
| **Full suite command** | N/A — manual verification |
| **Estimated runtime** | ~5 minutes for full verification |

---

## Sampling Rate

- **After every task commit:** Manual browser test of the modified feature
- **After every plan wave:** Manual verification of all implemented features
- **Before `/gsd-verify-work`:** Full manual suite must pass
- **Max feedback latency:** N/A (manual testing)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 05-01 | 1 | DASH-01 | T-05-01 | XSS mitigation via esc() | manual | N/A | N/A | ⬜ pending |
| 05-01-02 | 05-01 | 1 | DASH-01 | T-05-01 | XSS mitigation via esc() | manual | N/A | N/A | ⬜ pending |
| 05-01-03 | 05-01 | 1 | DASH-01 | T-05-01 | XSS mitigation via esc() | manual | N/A | N/A | ⬜ pending |
| 05-02-01 | 05-02 | 2 | DASH-02 | — | N/A | manual | N/A | N/A | ⬜ pending |
| 05-02-02 | 05-02 | 2 | DASH-02 | — | N/A | manual | N/A | N/A | ⬜ pending |
| 05-02-03 | 05-02 | 2 | DASH-02 | — | N/A | manual | N/A | N/A | ⬜ pending |
| 05-02-04 | 05-02 | 2 | DASH-03 | — | N/A | manual | N/A | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] Wave 0 is not applicable for this phase — frontend-only implementation requires no test infrastructure setup

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Toast appears on alert() call sites | DASH-01 | No test framework for frontend JS | Load app, trigger portfolio error (line 267 replacement), export success (line 810 replacement), export error (line 820 replacement) — verify toasts appear top-right |
| Toast auto-dismiss after 4s | DASH-01 | UI timing test | Trigger toast, observe it dismisses after ~4 seconds |
| Toast stacking max 3 | DASH-01 | UI state test | Trigger 4+ toasts rapidly, verify only 3 visible and oldest dismisses |
| Stale badge on API failure | DASH-02 | UI state test | Disconnect network or return 500, trigger refresh, verify stale badge + last valid data visible |
| Positions error state | DASH-02 | UI state test | Cause portfolio load failure, verify "Failed to load positions" with retry button |
| Responsive at 420px | DASH-03 | Visual/responsive test | Use browser devtools set to 420px, verify single column, no horizontal overflow |
| Responsive at 768px | DASH-03 | Visual/responsive test | Use browser devtools set to 768px, verify 2-column grid |
| Sticky column on mobile | DASH-03 | Visual test | At 420px, scroll positions table horizontally, verify Name column stays visible |

---

## Validation Sign-Off

- [x] All tasks have manual verification (no automated framework available)
- [x] Wave 0 is not applicable — no test infrastructure setup required
- [x] Manual verification checklist covers all phase requirements
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending