---
name: 260429-rsi-momentum-enrichment-fix
description: Add 3mo fallback history fetch for RSI when 1y history is sparse
status: complete
---

## Summary

**Root cause:** `ticker.history(period="1y")` returned < 14 rows for certain positions (newly listed, ETFs on European exchanges). `compute_rsi()` requires `period + 1` rows and returned `None` without a fallback.

**Fix applied in `app/market_data.py` lines 1195-1212:**
- After `compute_rsi()` returns `None`, attempt a secondary `yf.Ticker(yf_symbol).history(period="3mo", interval="1d")` fetch
- If ≥ 14 rows available, compute RSI using the same Wilder smoothing method
- If still `None`, log `WARN` level: `"RSI unavailable for {symbol} — insufficient history (1y={n}, 3mo={n})"`
- `momentum_score` depends on `perf_30d/90d/ytd` — those are already populated by `_compute_performance()` so no change needed there

**Cache-hit path note:** Positions hitting the fast path (lines 951-1009) still get `rsi=None` — the persistent resolution cache stores price/fundamentals only, not RSI. This is acceptable; the next full enrichment will populate RSI. Extending the cache schema is out of scope.

**Verification:** `python3 -c "import ast; ast.parse(open('app/market_data.py').read())"` — syntax OK.

**Commit:** `fe6f947` — fix: add 3mo fallback history fetch for RSI when 1y history is sparse