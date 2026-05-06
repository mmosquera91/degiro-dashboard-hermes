# RSI and momentum_score enrichment fix

## Problem
RSI and momentum_score are null for a subset of positions in `/api/portfolio-raw`. Frontend shows `—` for these nulls.

## Root Causes

1. **Cache-hit fast path (lines 951-1009)** skips ALL yfinance calls — returns position with `rsi=None` because `compute_rsi` is never called. The cache stores fundamentals but not RSI/perf metrics.

2. **`hist = ticker.history(period="1y")` returns < 14 rows** for sparse-data symbols (newly listed, ETFs on certain European exchanges). `compute_rsi` returns `None` when `len(hist_close) < period + 1`.

3. **`momentum_score` is computed in `scoring.py`** (not in `market_data.py`), so any position that skips `enrich_position` or has all-null perf fields will get `momentum_score=None`.

## Fix (single change in market_data.py)

**Location:** lines 1195-1212 (after `hist = ticker.history(period="1y")` block)

**Before:**
```python
# RSI
position["rsi"] = compute_rsi(close, period=14)

# Performance
perf = _compute_performance(close)
position["perf_30d"] = perf["perf_30d"]
position["perf_90d"] = perf["perf_90d"]
position["perf_ytd"] = perf["perf_ytd"]
```

**After:**
```python
# RSI — fallback if 1y history is sparse
rsi = compute_rsi(close, period=14)
if rsi is None:
    _yf_throttle()
    fallback_hist = yf.Ticker(yf_symbol).history(period="3mo", interval="1d")
    if fallback_hist is not None and len(fallback_hist) >= 14:
        fc = fallback_hist["Close"]
        delta = fc.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        if loss.iloc[-1] > 0:
            rs = gain.iloc[-1] / loss.iloc[-1]
            rsi = float(100 - (100 / (1 + rs)))
            rsi = round(rsi, 2)
    if rsi is None:
        logger.warning("RSI unavailable for %s — insufficient history (1y=%d, 3mo=%d)",
            symbol, len(close), len(fallback_hist) if fallback_hist is not None else 0)
position["rsi"] = rsi

# Performance
perf = _compute_performance(close)
position["perf_30d"] = perf["perf_30d"]
position["perf_90d"] = perf["perf_90d"]
position["perf_ytd"] = perf["perf_ytd"]
```

## What was NOT changed (intentional)

- **Cache-hit path (lines 951-1009):** Adding RSI to the persistent cache would require schema migration. The cache stores price/fundamentals only — extending it for RSI is out of scope.
- **momentum_score:** Already computed correctly in `scoring.py`. If `perf_30d/90d/ytd` are populated, `momentum_score` will compute correctly.

## Verification
- Syntax check: `python3 -c "import ast; ast.parse(open('app/market_data.py').read())"`
- RSI fallback is exercised only when `compute_rsi` returns `None` (sparse history case)
- WARN-level log makes gaps visible without crashing enrichment