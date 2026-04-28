# Quick Task: 260428-update-prices-modal-progress

## Problem
"Update Prices" only mutates the button label — invisible on mobile and inconsistent with the enrichment flow which already shows a modal progress overlay.

## Changes

### Frontend (Update Prices button component)

1. On click, fire the same modal/overlay pattern used by the enrichment progress popup:
   - Modal appears immediately on click, blocking interaction
   - Title: "Updating prices…"
   - Shows a spinner + status line (can be static: "Fetching latest market data")
   - Modal closes automatically when the API call resolves (success or error)
   - On error: swap spinner for a red message, add a Close button

2. Remove the existing button-text mutation logic entirely — the modal replaces it

3. The button itself should go into a loading/disabled state while the modal is open (prevents double-clicks), same as the enrichment button already does

### No backend changes

## Notes
- Modal is viewport-level so mobile gets it for free
- Keep the implementation consistent with enrichment modal — reuse the same component/function if one exists, don't duplicate the pattern

## Implementation Steps

1. Find the "Update Prices" button component in the frontend
2. Find the existing enrichment progress modal component
3. Reuse the enrichment modal pattern for Update Prices
4. Remove button-text mutation logic from Update Prices
5. Disable button during the API call
6. Verify no regressions
