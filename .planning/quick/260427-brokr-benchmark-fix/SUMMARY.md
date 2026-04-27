---
name: brokr-benchmark-fix
description: Fix renderBenchmark() destroyed immediately by renderDashboard()
type: quick
status: complete
---

## Done

Moved `renderDashboard()` in `loadPortfolio()` (app/static/app.js:224) to execute **before** the benchmark fetch, so `charts.benchmark` created by `renderBenchmark()` is never destroyed by `renderCharts()`.

**Before:** portfolioData → fetchBenchmarkData → renderBenchmark → renderAttribution → **renderDashboard (DESTROYS benchmark)**
**After:** portfolioData → **renderDashboard** → fetchBenchmarkData → renderBenchmark → renderAttribution

## Diff
```diff
-      portfolioData = await res.json();
-
-      // Fetch benchmark data
-      const bmData = await fetchBenchmarkData();
-      if (bmData) {
-        benchmarkData = bmData;
-        renderBenchmark(bmData);
-        renderAttribution(bmData);
-      }
-
-      renderDashboard();
-      showEnriching(false);
+      portfolioData = await res.json();
+
+      renderDashboard();
+
+      // Fetch benchmark data
+      const bmData = await fetchBenchmarkData();
+      if (bmData) {
+        benchmarkData = bmData;
+        renderBenchmark(bmData);
+        renderAttribution(bmData);
+      }
+
+      showEnriching(false);
```

## Verification
- `renderDashboard()` only uses `portfolioData` (already set before it runs) ✓
- `renderBenchmark()` still has access to `portfolioData` via closure ✓
- `charts.benchmark` created AFTER `renderDashboard()` — no longer destroyed ✓
