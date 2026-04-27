Normalise dates to YYYY-MM-DD in renderBenchmark() maps

In app/static/app.js, in the renderBenchmark() function, normalise all dates
to YYYY-MM-DD strings before building the maps, so exact-match lookups work
regardless of whether yfinance returns "2026-04-27" or "2026-04-27 00:00:00"
or "2026-04-27T00:00:00Z".

Changes:
- Add normDate helper: d => (d || '').slice(0, 10)
- Normalise firstSnapDate, portfolioByDate keys, benchmarkByDate keys, allDates
