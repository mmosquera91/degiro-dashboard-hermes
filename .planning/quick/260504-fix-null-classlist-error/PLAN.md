---
phase: quick-260504-fix-null-classlist-error
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - app/static/app.js
autonomous: true
requirements: []
must_haves:
  truths:
    - "No 'Cannot read properties of null' errors in browser console"
    - "Dashboard loads without crashing"
  artifacts:
    - path: "app/static/app.js"
      provides: "null-guarded classList accesses"
  key_links:
    - from: "app/static/app.js (DOM refs)"
      to: "openModal(), closeModal(), showLoading()"
      via: "elCredModal, elLoadingOverlay, elCredError direct access"
---

<objective>
Fix "Cannot read properties of null (reading classList)" error in app.js by adding null checks to DOM element classList accesses.
</objective>

<context>
@app/static/app.js

## Analysis

All DOM element references are queried at module load (lines 58-78). These IDs must exist in index.html:

```javascript
const elDashboard = $("#dashboard");
const elEmptyState = $("#empty-state");
const elCredModal = $("#cred-modal");
const elLoadingOverlay = $("#loading-overlay");
const elCredError = $("#cred-error");
const elBtnConnect = $("#btn-connect");
const elConnectText = $("#connect-text");
const elConnectSpinner = $("#connect-spinner");
const elBtnRefresh = $("#btn-refresh");
const elBtnUpdatePrices = $("#btn-update-prices");
const elBtnExport = $("#btn-export");
const elBtnPrivacy = $("#btn-privacy");
const elBtnEmptyConnect = $("#btn-empty-connect");
const elLastRefresh = $("#last-refresh");
const elPositionsBody = $("#positions-body");
const elEnrichmentModal = $("#enrichment-modal");
const elEnrichmentModalContent = $("#enrichment-modal-content");
const elEnrichmentStatus = $("#enrichment-status");
const elEnrichmentError = $("#enrichment-error");
const elEnrichmentErrorMsg = $("#enrichment-error-msg");
const elEnrichmentClose = $("#enrichment-close");
```

These elements are used directly without null checks in:

| Element | Used In |
|---------|---------|
| elCredModal | openModal() line 157, closeModal() line 165, bindEvents line 96 |
| elLoadingOverlay | showLoading() line 421, loadPortfolioRaw() line 272 |
| elBtnRefresh | bindEvents line 89, setOperationActive() line 411, 415 |
| elBtnUpdatePrices | handleUpdatePrices() line 322, setOperationActive() lines 400, 414 |
| elBtnPrivacy | togglePrivacyMode() line 172 |
| elEnrichmentClose | bindEvents line 95 |
| elEnrichmentModal | showEnrichmentModal() line 431, closeEnrichmentModal() line 435 |

The auth token refactoring (`_ensureAuthToken`) is async but only called inside `apiFetch()`. The crash happens at DOM initialization time (DOMContentLoaded event fires before any async fetch), so the auth token is not the root cause. The elements themselves may be missing from the HTML or being accessed before the DOM is ready.

</context>

<tasks>

<task type="auto">
  <name>Task 1: Add null-check guards to openModal and closeModal</name>
  <files>app/static/app.js</files>
  <action>
Edit the `openModal()` function at line 156 to add null checks before classList access:

```javascript
function openModal() {
  if (elCredModal) elCredModal.classList.remove("hidden");
  if (elCredError) elCredError.classList.add("hidden");
  const sessionError = $("#session-error");
  if (sessionError) sessionError.classList.add("hidden");
  const sessionForm = $("#session-form");
  if (sessionForm) sessionForm.reset();
  const sessionIdInput = $("#session-id");
  if (sessionIdInput) sessionIdInput.focus();
}
```

Edit the `closeModal()` function at line 164 to add null check:

```javascript
function closeModal() {
  if (elCredModal) elCredModal.classList.add("hidden");
}
```
</action>
  <verify>
grep -n "elCredModal.classList" app/static/app.js
</verify>
  <done>openModal() and closeModal() guard all classList accesses with null checks</done>
</task>

<task type="auto">
  <name>Task 2: Guard showLoading() null accesses</name>
  <files>app/static/app.js</files>
  <action>
Edit the `showLoading()` function at line 419:

```javascript
function showLoading(on) {
  if (!elLoadingOverlay) return;
  if (on) {
    elLoadingOverlay.classList.remove("hidden");
  } else {
    elLoadingOverlay.classList.add("hidden");
  }
}
```
</action>
  <verify>
grep -n "elLoadingOverlay.classList" app/static/app.js
</verify>
  <done>showLoading() guards elLoadingOverlay with null check</done>
</task>

<task type="auto">
  <name>Task 3: Guard enrichment modal functions</name>
  <files>app/static/app.js</files>
  <action>
Edit `showEnrichmentModal()` at line 427:

```javascript
function showEnrichmentModal(msg) {
  if (!elEnrichmentModal) return;
  if (elEnrichmentStatus) elEnrichmentStatus.textContent = msg;
  if (elEnrichmentModalContent) elEnrichmentModalContent.classList.remove("hidden");
  if (elEnrichmentError) elEnrichmentError.classList.add("hidden");
  elEnrichmentModal.classList.remove("hidden");
}
```

Edit `closeEnrichmentModal()` at line 434:

```javascript
function closeEnrichmentModal() {
  if (!elEnrichmentModal) return;
  elEnrichmentModal.classList.add("hidden");
  if (elEnrichmentModalContent) elEnrichmentModalContent.classList.remove("hidden");
  if (elEnrichmentError) elEnrichmentError.classList.add("hidden");
}
```
</action>
  <verify>
grep -n "elEnrichmentModal.classList\|elEnrichmentModalContent.classList\|elEnrichmentError.classList" app/static/app.js
</verify>
  <done>Enrichment modal functions guard all classList accesses</done>
</task>

<task type="auto">
  <name>Task 4: Guard elBtnRefresh and elBtnUpdatePrices in setOperationActive</name>
  <files>app/static/app.js</files>
  <action>
The `setOperationActive()` at line 407 uses elBtnRefresh and elBtnUpdatePrices directly. Verify the existing guards at lines 400 and 404 already guard elBtnUpdatePrices. Add guard for elBtnRefresh at line 411 and 415:

Current code:
```javascript
if (active) {
  disableUpdatePrices();
  if (elBtnRefresh) elBtnRefresh.disabled = true;
} else {
  // Re-enable only if we have portfolio data
  if (portfolioData) enableUpdatePrices();
  if (elBtnRefresh && portfolioData) elBtnRefresh.disabled = false;
}
```

Line 411 already has `if (elBtnRefresh)` guard. Line 415 also has `if (elBtnRefresh && portfolioData)`. Both are already guarded. No change needed.
</action>
  <verify>
grep -n "elBtnRefresh.disabled\|elBtnUpdatePrices.disabled" app/static/app.js
</verify>
  <done>setOperationActive guards elBtnRefresh and elBtnUpdatePrices</done>
</task>

<task type="auto">
  <name>Task 5: Verify togglePrivacyMode guard</name>
  <files>app/static/app.js</files>
  <action>
At line 169, `togglePrivacyMode()` calls `elBtnPrivacy.classList.toggle("active", privacyMode)` at line 172. Check if elBtnPrivacy could be null. Since `elBtnPrivacy` is defined at line 69 as `const elBtnPrivacy = $("#btn-privacy")`, if the HTML does not have `#btn-privacy`, this would be null.

Add guard:
```javascript
function togglePrivacyMode() {
  privacyMode = !privacyMode;
  document.body.classList.toggle("privacy-mode", privacyMode);
  if (elBtnPrivacy) {
    elBtnPrivacy.classList.toggle("active", privacyMode);
    const icon = elBtnPrivacy.querySelector("i");
    if (icon) {
      icon.setAttribute("data-lucide", privacyMode ? "eye-off" : "eye");
      lucide.createIcons({ nodes: [elBtnPrivacy] });
    }
  }
}
```
</action>
  <verify>
grep -n "elBtnPrivacy.classList" app/static/app.js
</verify>
  <done>togglePrivacyMode guards elBtnPrivacy with null check</done>
</task>

<task type="auto">
  <name>Task 6: Guard bindEvents elBtn* accesses</name>
  <files>app/static/app.js</files>
  <action>
At line 88, `bindEvents()` calls `.addEventListener` on `elBtnRefresh`, `elBtnUpdatePrices`, `elBtnEmptyConnect`, `elBtnExport`, `elBtnPrivacy` without checking if they are null. If any of these elements are missing from the HTML, the script would throw "Cannot read properties of null".

Wrap the entire `bindEvents` function to guard all element accesses:

```javascript
function bindEvents() {
  if (!elBtnRefresh && !elBtnUpdatePrices && !elBtnEmptyConnect && !elBtnExport && !elBtnPrivacy) {
    return; // No elements found, skip binding
  }
  if (elBtnRefresh) elBtnRefresh.addEventListener("click", () => { _lastTableHash = null; openModal(); });
  if (elBtnUpdatePrices) elBtnUpdatePrices.addEventListener("click", handleUpdatePrices);
  if (elBtnEmptyConnect) elBtnEmptyConnect.addEventListener("click", openModal);
  if (elBtnExport) elBtnExport.addEventListener("click", exportHermesContext);
  if (elBtnPrivacy) elBtnPrivacy.addEventListener("click", togglePrivacyMode);
  const modalClose = $("#modal-close");
  if (modalClose) modalClose.addEventListener("click", closeModal);
  if (elEnrichmentClose) elEnrichmentClose.addEventListener("click", closeEnrichmentModal);
  if (elCredModal) {
    elCredModal.addEventListener("click", (e) => {
      if (e.target === elCredModal) closeModal();
    });
  }
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
  });
  const sessionForm = $("#session-form");
  if (sessionForm) sessionForm.addEventListener("submit", handleSession);
  // ... rest of filter/sort code
}
```

Note: $$(".filter-tab") and $$("#positions-table th[data-sort]") are fine since `$$` returns querySelectorAll which is never null (empty NodeList if no matches).
</action>
  <verify>
grep -n "\.addEventListener" app/static/app.js | grep elBtn
</verify>
  <done>bindEvents guards all elBtn* event listener attachments</done>
</task>

</tasks>

<verification>
Run: `grep -c "\.classList" app/static/app.js` and verify all classList usages are guarded or on known-non-null elements (elDashboard, elEmptyState, elPositionsBody are checked against undefined before use in renderDashboard and renderPositions).

The auth token issue is not causing this crash because `_ensureAuthToken()` is only called inside `apiFetch()` which is async and only triggered after user actions or data loads, not during DOM initialization.
</verification>

<success_criteria>
- No "Cannot read properties of null (reading classList)" errors in browser console
- Dashboard loads and displays without crashing
- All button click handlers are still wired correctly
</success_criteria>

<output>
After completion, create `.planning/quick/260504-fix-null-classlist-error/SUMMARY.md`
</output>