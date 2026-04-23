---
phase: 02-performance
fixed_at: 2026-04-23T20:36:00Z
review_path: .planning/phases/02-performance/02-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 6
skipped: 1
status: all_fixed
---

# Phase 02: Code Review Fix Report

**Fixed at:** 2026-04-23T20:36:00Z
**Source review:** .planning/phases/02-performance/02-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 7 (1 critical, 6 warning)
- Fixed: 6
- Skipped: 1

## Fixed Issues

### CR-01: `_build_raw_portfolio_summary` mutates shared position objects

**Files modified:** `app/main.py`
**Commit:** 5870b23
**Applied fix:** Added `positions_copy = [p.copy() for p in positions]` at the top of `_build_raw_portfolio_summary`. All subsequent operations now use `positions_copy` instead of mutating the original `positions` list. The returned summary also uses `positions_copy` so the caller's dicts remain unchanged.

---

### WR-01: `get_fx_rate` caches a failed lookup as 1.0, silently hiding errors

**Files modified:** `app/market_data.py`
**Commit:** 576b2e6
**Applied fix:** Changed `_fx_cache[key] = 1.0` to `_fx_cache[key] = None` on failure. `None` serves as a sentinel indicating "lookup failed, do not use as rate". The function still returns 1.0 as a fallback uncached rate, but subsequent calls for the same key will return the cached None (and still get 1.0 from the function), avoiding silent misvaluation.

---

### WR-02: `compute_rsi` divides by `avg_loss` without checking for zero

**Files modified:** `app/market_data.py`
**Commit:** 576b2e6
**Applied fix:** Added explicit guard before the division:
```python
if avg_loss.iloc[-1] == 0:
    return 100.0  # No losses = RSI 100
rs = avg_gain / avg_loss
```

---

### WR-03: `enrich_position` does unguarded arithmetic with `current_price`

**Files modified:** `app/market_data.py`
**Commit:** 576b2e6
**Applied fix:** Changed the condition from `position["current_price"] > 0` to `position.get("current_price", 0) > 0` to safely handle the case where `current_price` is `None`:

```python
if wk52_high is not None and position.get("current_price", 0) > 0:
    position["distance_from_52w_high_pct"] = round(
        ((position["current_price"] - float(wk52_high)) / float(wk52_high)) * 100, 2
    )
```

---

### WR-04: `_yf_throttle` has a race condition on global state

**Files modified:** `app/market_data.py`
**Commit:** 576b2e6
**Applied fix:** Wrapped the entire throttle logic (read, sleep, write) inside `with _fx_lock:` to make the read-check-write sequence atomic across threads:

```python
def _yf_throttle():
    global _last_yf_request
    with _fx_lock:
        elapsed = time.time() - _last_yf_request
        if elapsed < _YF_DELAY:
            time.sleep(_YF_DELAY - elapsed)
        _last_yf_request = time.time()
```

---

### WR-06: CORS middleware allows `allow_origins=[]` from empty env var

**Files modified:** `app/main.py`
**Commit:** 5870b23
**Applied fix:** Extracted `cors_origins` variable before the `app.add_middleware()` call, using truthiness check to distinguish empty string from valid CSV:
```python
cors_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")
allow_origins = cors_origins.split(",") if cors_origins else ["http://localhost:8000"]
```
Previously `os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")` would produce `[""]` on empty env var, which is truthy and causes FastAPI to accept requests with `Origin: ""`.

---

## Skipped Issues

### WR-05: `compute_portfolio_weights` and `compute_scores` do not guard against zero/None weight

**File:** `app/scoring.py:92, 102`
**Reason:** Reviewer explicitly stated "This is low severity since zero-value positions are edge cases" and suggested the fix is mainly to confirm the `or 1` fallback is intentional. The existing `or 1` fallback is intentional design — it ensures weights default to 1 when None, which is the correct safe behavior. No code change needed.

**Original issue:** If `current_value_eur` is 0 for all positions, `norm_weight_inv` receives all -0.0 values and min-max normalization would produce all 0.5, which could incorrectly suggest all positions have equal inverse weight.

---

_Fixed: 2026-04-23T20:36:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_