---
name: 260504-fix-null-classlist-error
description: Fix "Cannot read properties of null (reading classList)" in dashboard
type: quick
status: complete
date: 2026-05-04
---

## Summary

Fixed JS error "Cannot read properties of null (reading classList)" in app/static/app.js by adding null guards to all DOM element accesses that could be null if the corresponding HTML IDs are missing.

## Changes Made

- **openModal()** — guarded `elCredModal`, `elCredError`, `$("#session-error")`, `$("#session-form")`, `$("#session-id")`
- **closeModal()** — guarded `elCredModal`
- **togglePrivacyMode()** — wrapped entire body in `if (elBtnPrivacy)`
- **showLoading()** — early return if `elLoadingOverlay` is null
- **showEnrichmentModal()** — guarded `elEnrichmentModal`, `elEnrichmentStatus`, `elEnrichmentModalContent`, `elEnrichmentError`
- **closeEnrichmentModal()** — guarded `elEnrichmentModal`, `elEnrichmentModalContent`, `elEnrichmentError`
- **bindEvents()** — added early return if all elBtn* elements are null; guarded each addEventListener call
- **renderDashboard()** — guarded `elBtnExport.style.display`
- **handleSession()** — guarded `btn`, `txt`, `spin`, `err` in try/finally blocks
- **snapshot-manager / btn-save-snapshot** — guarded getElementById calls with null checks

## Root Cause

The auth token refactoring (`_ensureAuthToken`) was not the cause — it's only called inside `apiFetch()` which is triggered by user actions, not at DOM initialization. The real issue was that several DOM elements were accessed directly without null checks, and if the HTML was missing any of those IDs, the script would throw.

## Verification

All `.classList` and `.addEventListener` accesses are now either on non-null elements (e.g., `document.body`, `$$()` results) or guarded with explicit null checks.
