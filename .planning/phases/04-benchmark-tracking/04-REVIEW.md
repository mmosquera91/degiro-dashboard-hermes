---
phase: 04-benchmark-tracking
reviewed: 2026-04-23T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - app/snapshots.py
  - app/main.py
  - app/context_builder.py
  - app/static/app.js
  - app/static/index.html
  - app/static/style.css
findings:
  critical: 1
  warning: 2
  info: 1
  total: 4
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-04-23
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

The phase 4 benchmark tracking implementation was reviewed. One critical bug was found in the attribution formula in `app/snapshots.py` where the `direction` multiplier inverts the sign of negative returns, causing losing positions to appear as outperformance. Two warnings and one info-level issue were also identified. No security vulnerabilities or credential exposure issues were found.

## Critical Issues

### CR-01: Inverted sign in relative_contribution for losing positions

**File:** `app/snapshots.py:151-156`
**Issue:** The `compute_attribution` function uses `direction = 1 if position_return >= 0 else -1` to flip the sign of relative contribution for negative returns. However, this inverts the intended meaning: a position that loses 10% while the benchmark is flat shows as +1.0% relative contribution instead of -1.0%. The double negation in `(position_return - benchmark_return) * direction` when both `position_return` and `direction` are negative produces a positive result, which contradicts the expected behavior of showing underperformance as a negative contribution.

**Affected code:**
```python
direction = 1 if position_return >= 0 else -1

relative_contribution = round(
    (position_return - benchmark_return) * weight * direction,
    4,
)
```

**Example demonstrating the bug:**
- position_return = -10%, benchmark_return = 0%, weight = 10%
- direction = -1 (since position_return < 0)
- relative_contribution = (-10 - 0) * 0.10 * (-1) = +1.0%
- Expected: -1.0% (the position underperformed by 10 percentage points)

**Fix:** Remove the `direction` multiplier from the relative_contribution formula:
```python
relative_contribution = round(
    (position_return - benchmark_return) * weight,
    4,
)
```

The `direction` logic should be removed entirely from the relative_contribution calculation. The formula `position_return - benchmark_return` already correctly expresses relative performance (negative means underperformance). The current `direction` flip was likely added to adjust sign for display purposes, but it corrupts the mathematical meaning.

---

## Warnings

### WR-01: Inconsistent sorting between backend and frontend for attribution

**File:** `app/snapshots.py:166` and `app/static/app.js:386-390`
**Issue:** The backend sorts attribution by `absolute_contribution` in descending order (largest positive values first, negative values last). The frontend sorts by `Math.abs()` of absolute_contribution (largest magnitude first regardless of sign). This means the frontend could show the biggest loser at the top while the backend API returns the biggest winner first.

**Backend (`app/snapshots.py:166`):**
```python
return sorted(attribution, key=lambda x: x["absolute_contribution"], reverse=True)
```

**Frontend (`app/static/app.js:386-390`):**
```javascript
const sorted = [...attribution].sort((a, b) => {
  const av = Math.abs(a.absolute_contribution || 0);
  const bv = Math.abs(b.absolute_contribution || 0);
  return bv - av;
});
```

**Fix:** Align frontend sorting with backend by removing the `Math.abs()` wrapper:
```javascript
const sorted = [...attribution].sort((a, b) => {
  const av = a.absolute_contribution || 0;
  const bv = b.absolute_contribution || 0;
  return bv - av;
});
```

---

### WR-02: Missing validation for date range ordering in fetch_benchmark_series

**File:** `app/snapshots.py:88-124`
**Issue:** `fetch_benchmark_series` does not validate that `start_date` precedes `end_date`. If the caller passes dates in the wrong order or if `datetime.now().strftime()` produces a date equal to `first_date` (possible in same-day scenarios), `yfinance.download` returns an empty DataFrame without warning. The function returns `[]` silently, which may cause charts to not render or attribution to use stale benchmark data.

**Affected code:**
```python
def fetch_benchmark_series(start_date: str, end_date: str) -> list[dict]:
    # No validation that start_date < end_date
    _yf_throttle()
    try:
        data = yf.download(ticker, start=start_date, end=end_date, progress=False)
    except Exception as e:
        logger.warning("yfinance benchmark fetch failed: %s", e)
        return []
```

**Fix:** Add validation to ensure proper date ordering:
```python
def fetch_benchmark_series(start_date: str, end_date: str) -> list[dict]:
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        logger.warning("Invalid date format: %s or %s", start_date, end_date)
        return []

    if start_dt >= end_dt:
        logger.warning("start_date %s must be before end_date %s", start_date, end_date)
        return []
```

---

## Info

### IN-01: CSS syntax error with double dash in custom property

**File:** `app/static/style.css:674`
**Issue:** Line 674 contains `var(----border, #2a2a2a)` with a double dash prefix. CSS custom property names must start with a single dash followed by at least one other character. Browsers will silently ignore this declaration, causing the border color to fall back to the second argument `#2a2a2a`.

**Affected code:**
```css
.comparison-table th,
.comparison-table td {
  padding: 0.5rem 0.75rem;
  text-align: right;
  border-bottom: 1px solid var(----border, #2a2a2a);  /* typo: double dash */
}
```

The same typo appears at line 708 for `.attribution-table`.

**Fix:** Correct the variable name to `--border`:
```css
border-bottom: 1px solid var(--border, #2a2a2a);
```

---

_Reviewed: 2026-04-23_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
