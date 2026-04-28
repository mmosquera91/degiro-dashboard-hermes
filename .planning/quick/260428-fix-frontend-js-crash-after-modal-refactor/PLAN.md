Fix: Add missing showEnrichmentModal/closeEnrichmentModal functions

The refactor commit 334132c introduced `showEnriching()` which calls
`showEnrichmentModal()` and `closeEnrichmentModal()`, but those two
functions were never defined in app.js. The script dies at
DOMContentLoaded because showEnriching is called inside loadPortfolioRaw()
before the missing references are reached.

Fix: add the missing `showEnrichmentModal()` and `closeEnrichmentModal()`
functions between showEnriching and the Benchmark Data section (after line 361).