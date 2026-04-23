---
phase: 02-performance
reviewed: 2026-04-23T00:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - app/main.py
  - app/market_data.py
findings:
  critical: 1
  warning: 6
  info: 5
  total: 12
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-04-23
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Two source files were reviewed: `app/main.py` (FastAPI application) and `app/market_data.py` (yfinance enrichment). Cross-references were made to `app/degiro_client.py`, `app/scoring.py`, and `app/context_builder.py` for complete context.

One critical bug was found: `_build_raw_portfolio_summary` mutates the shared position dicts by adding fields (`current_value_eur`, `weight`, `value_score`, `momentum_score`, `buy_priority_score`) that are supposed to be computed later in the pipeline. This corrupts the data for subsequent calls to `_build_portfolio_summary`. Several defensive coding gaps were also identified, including unguarded arithmetic with potentially-None values and a throttle function with a race condition.

---

## Critical Issues

### CR-01: `_build_raw_portfolio_summary` mutates shared position objects`

**File:** `app/main.py:111-128`
**Issue:** `_build_raw_portfolio_summary` modifies the input `positions` list in-place by writing fields (`current_value_eur`, `52w_high`, `rsi`, `weight`, `value_score`, `momentum_score`, `buy_priority_score`) directly onto each position dict. These fields are supposed to be computed later in the enrichment pipeline (`enrich_positions` sets `current_value` and `unrealized_pl`, `compute_portfolio_weights` sets `weight`, `compute_scores` sets `value_score`/`momentum_score`/`buy_priority_score`). When `/api/portfolio-raw` is called first, the shared position dicts are mutated, and the subsequent `/api/portfolio` call receives positions that already have these fields pre-populated with incorrect values (e.g., `current_value_eur` set to the non-EUR value, `weight` set to 0.0, scores set to None).

The call chain:
1. `get_portfolio_raw()` calls `_build_raw_portfolio_summary(raw.get("positions", []), ...)` — mutates the raw positions
2. `get_portfolio()` later calls `_build_portfolio_summary(positions, ...)` with those same mutated dicts — uses incorrect pre-populated fields

**Fix:** Build the summary from a deep copy of the positions, not the originals:

```python
def _build_raw_portfolio_summary(positions: list, cash_available: float) -> dict:
    # Work on a copy so the caller's list is not mutated
    positions_copy = [p.copy() for p in positions]
    # ... build summary from positions_copy
```

---

## Warnings

### WR-01: `get_fx_rate` caches a failed lookup as 1.0, silently hiding errors

**File:** `app/market_data.py:87-89`
**Issue:** When both the forward and inverse FX lookups fail, the code caches `_fx_cache[key] = 1.0` and returns 1.0. This means the next call returns the cached 1.0 rate without attempting a fresh lookup, silently using an incorrect FX rate for the lifetime of the cache entry. This could cause significant misvaluation of non-EUR positions.

**Fix:** Use a sentinel value to distinguish "lookup failed" from "rate is 1.0", or do not cache on failure:

```python
with _fx_lock:
    _fx_cache[key] = None  # None = lookup failed, do not use
return 1.0
```

Or only cache successful lookups and return 1.0 uncached on failure.

---

### WR-02: `compute_rsi` divides by `avg_loss` without checking for zero

**File:** `app/market_data.py:131`
**Issue:** `rs = avg_gain / avg_loss` — if `avg_loss` is 0 (all gains, no losses), `rs` is infinite, `rsi` becomes 100, and the function returns 100.00 without indicating that RSI is technically undefined. Conversely, if `avg_gain` is 0, `rs` is 0 and RSI is 0. This is mathematically correct but the function does not distinguish between "RSI is undefined" and "RSI is 100".

**Fix:** Add explicit handling:

```python
if avg_loss.iloc[-1] == 0:
    return 100.0  # No losses = RSI 100
rs = avg_gain / avg_loss
rsi = 100 - (100 / (1 + rs))
```

---

### WR-03: `enrich_position` does unguarded arithmetic with `current_price`

**File:** `app/market_data.py:281-283`
**Issue:** Line 281 references `position["current_price"]` after lines 263-266 set it, but if yfinance returns a non-positive price the field is not set, leaving it as the initialized `None`. Line 281 would then compute `None - float(wk52_high)` which raises a TypeError (caught by the outer exception handler, so it results in all-None fields). However, this is implicit and fragile.

**Fix:** Guard the distance calculation with a None check:

```python
if wk52_high is not None and position.get("current_price", 0) > 0:
    position["distance_from_52w_high_pct"] = round(
        ((position["current_price"] - float(wk52_high)) / float(wk52_high)) * 100, 2
    )
```

---

### WR-04: `_yf_throttle` has a race condition on global state

**File:** `app/market_data.py:24-30`
**Issue:** `_yf_throttle` reads and writes `_last_yf_request` without holding `_fx_lock`. Two threads can read the same elapsed time, both sleep for `_YF_DELAY`, both update `_last_yf_request`, and both proceed to make yfinance calls — defeating the rate limit. This matters because `get_fx_rate` and `enrich_position` both call `_yf_throttle` from multiple threads via `asyncio.to_thread`.

**Fix:** Hold `_fx_lock` around the throttle logic:

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

### WR-05: `compute_portfolio_weights` and `compute_scores` do not guard against zero/None weight

**File:** `app/scoring.py:92, 102`
**Issue:** `norm_weight_inv = _min_max_normalize([-w for w in weights])` — if `weight` is None it becomes 0 via `or 1`, so `-w` is -0.0. A list of all-zero weights (possible if `current_value_eur` is 0 for all positions) would produce all 0.5 from the min-max normalization. If `current_value_eur` is mixed but some values are 0, those positions get normalized weight 0.0 but the inverse normalization still proceeds.

**Fix:** This is low severity since zero-value positions are edge cases, but adding a guard in `compute_portfolio_weights` when total is 0 (already handled) and confirming the `or 1` fallback is intentional would help.

---

### WR-06: CORS middleware allows `allow_origins=[]` from empty env var

**File:** `app/main.py:235`
**Issue:** `os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")` — if `CORS_ALLOWED_ORIGINS` is set to an empty string `""`, `.split(",")` returns `[""]`, which is truthy. FastAPI's `CORSMiddleware` with an empty origins list will accept requests with `Origin: ""`, which is not a browser-origin and may be treated as a wildcard by some clients. The intended behavior (allow no origins, fall back to localhost) would be broken.

**Fix:**

```python
cors_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")
allow_origins = cors_origins.split(",") if cors_origins else ["http://localhost:8000"]
```

---

## Info

### IN-01: Dead code in `_resolve_yf_symbol`

**File:** `app/market_data.py:104-108`
**Issue:** `suffixes_to_try` is defined but never used — the function always returns the base symbol. The comment says "yfinance usually resolves US tickers" which is why the return is unconditional, but the list and comment suggest the intent was to implement suffix-trying logic.

**Fix:** Remove the unused list, or implement the suffix logic if it was intended:

```python
# If implementing suffix logic:
for suffix in suffixes_to_try:
    candidate = symbol + suffix
    # try to resolve...
```

---

### IN-02: Typo in FX ticker map

**File:** `app/market_data.py:55`
**Issue:** `"NOK EUR": "NOKEUR=X"` — there is an accidental space in the key `"NOK EUR"`. The forward lookup `"NOK EUR"` would never match because the key is constructed as `f"{from_currency}{to_currency}"` which produces `"NOKEUR"`. The fallback inverse lookup `"EURNOK"` is also not in the ticker map, so it falls through to the `f"{key}=X"` format, which is correct by coincidence.

**Fix:** Change key to `"NOKEUR"`:

```python
"NOKEUR": "NOKEUR=X",
```

---

### IN-03: `build_hermes_context` formats RSI=0 as `"0"` not `"N/A"`

**File:** `app/context_builder.py:110`
**Issue:** `f"{p.get('rsi', 0):.0f}"` — when RSI is 0 the f-string produces `"0"` while other absent fields use `"N/A"`. This is inconsistent in the plaintext output.

**Fix:** Use the same None-guard pattern used for other fields:

```python
f"{p.get('rsi', 0):.0f}".rjust(5) if p.get("rsi") is not None else "N/A".rjust(5)
```

---

### IN-04: Duplicate portfolio summary building logic

**File:** `app/main.py:85-145` and `148-206`
**Issue:** `_build_raw_portfolio_summary` and `_build_portfolio_summary` share ~40 lines of near-identical logic (total_value, total_invested, total_pl, allocation percentages, winners/losers sorting). The differences are: (a) raw uses `current_value`, enriched uses `current_value_eur`; (b) enriched computes sector_breakdown and top_candidates; (c) enriched receives already-enriched positions.

**Fix:** Extract a common `_compute_portfolio_totals(positions)` helper that both functions call.

---

### IN-05: `_build_raw_portfolio_summary` returns early with winners/losers unsafely sliced

**File:** `app/main.py:102-108`
**Issue:** `sorted_by_pl[:5]` and `sorted_by_pl[-5:][::-1]` — if `sorted_by_pl` has fewer than 5 elements (e.g., 2 positions), slicing still works correctly in Python. However, if `sorted_by_pl` is empty (no positions with `unrealized_pl_pct`), both slices produce empty lists and no error is raised. This is correct behavior but worth noting that the "top 5" naming implies there are at least 5.

**Fix:** No fix required — this is safe but the comment could be clarified.

---

_Reviewed: 2026-04-23_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
