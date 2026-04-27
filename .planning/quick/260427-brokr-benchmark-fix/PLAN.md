# brokr-benchmark-fix

Move `renderDashboard()` before the benchmark fetch in `loadPortfolio()` so that `charts.benchmark` (created by `renderBenchmark()`) is never destroyed by `renderCharts()`.

## Current order in loadPortfolio()
1. portfolioData = await res.json()
2. fetchBenchmarkData()
3. renderBenchmark(bmData) ← creates charts.benchmark
4. renderAttribution(bmData)
5. renderDashboard() ← calls renderCharts() which does Object.values(charts).forEach(c => c.destroy()), DESTROYING charts.benchmark

## Fix
1. portfolioData = await res.json()
2. renderDashboard() ← renders non-benchmark charts, safe
3. fetchBenchmarkData()
4. renderBenchmark(bmData) ← benchmark chart created AFTER renderDashboard, never destroyed
5. renderAttribution(bmData)

No other changes to this function. Do not touch renderBenchmark() itself.
