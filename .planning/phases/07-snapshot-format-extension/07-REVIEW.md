---
phase: 07-snapshot-format-extension
reviewed: 2026-04-24T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - app/snapshots.py
  - app/main.py
  - docker-compose.yml
  - tests/test_snapshots.py
findings:
  critical: 1
  warning: 2
  info: 1
  total: 4
status: issues_found
---

# Phase 07: Code Review Report

**Reviewed:** 2026-04-24
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

The snapshot save/load implementation is generally well-structured with appropriate security measures (date validation, atomic writes, path validation). Tests provide good coverage including atomicity, backward compatibility, and edge cases. One critical race condition and two warnings were identified.

---

## Critical Issues

### CR-01: Uncaught OSError in load_snapshots (TOCTOU race condition)

**File:** `app/snapshots.py:87`
**Issue:** `load_snapshots()` catches `ValueError` and `JSONDecodeError` but not `OSError`. If a snapshot file is deleted between the `glob()` call and `open()`, an uncaught `OSError` propagates, crashing the entire function. This can happen in production if snapshots are cleaned by an external process or during concurrent access.

**Fix:**
```python
# Line 87: Add OSError to exception handling
except (ValueError, json.JSONDecodeError, OSError) as e:
    logger.warning("Skipping invalid snapshot file %s: %s", file_path, e)
    continue
```

---

## Warnings

### WR-01: Potential division by zero in fetch_benchmark_series

**File:** `app/snapshots.py:171`
**Issue:** `first_price = float(data["Close"].iloc[0])` could cause `ZeroDivisionError` at line 177 if yfinance returns a zero price for the first trading day. While rare, this would crash the entire benchmark fetch.

**Fix:**
```python
first_price = float(data["Close"].iloc[0])
if first_price == 0:
    logger.warning("First benchmark price is 0 — cannot index series")
    return []
```

### WR-02: Silent fallback to 0.0 for missing perf_ytd in compute_attribution

**File:** `app/snapshots.py:204`
**Issue:** If a position lacks `perf_ytd` data, it silently contributes 0.0 to attribution rather than signaling a data quality issue. This could mask missing enrichment data.

**Fix:**
```python
position_return = pos.get("perf_ytd")
if position_return is None:
    logger.debug("Position %s missing perf_ytd, using 0.0", pos.get("name", "unknown"))
    position_return = 0.0
```

---

## Info

### IN-01: Healthcheck unauthenticated HTTP GET

**File:** `docker-compose.yml:14`
**Issue:** The healthcheck calls `http://localhost:8000/health` without authentication. While `/health` is intentionally unauthenticated (returns `{"status": "ok"}`), this means anyone with network access to the host can trigger health checks. Low severity since the endpoint returns only a status string and the service runs on `network_mode: host`.

**Fix:** No fix required — this is by design (FastAPI liveness probe). Acknowledged as acceptable risk.

---

## Pass Verdict

| File | Status | Notes |
|------|--------|-------|
| `app/snapshots.py` | **FLAG** | 1 critical (OSError), 2 warnings |
| `app/main.py` | **PASS** | Snapshot integration correctly uses non-blocking try-except, date validation applied |
| `docker-compose.yml` | **PASS** | Healthcheck appropriate; snapshot volume correctly configured |
| `tests/test_snapshots.py` | **PASS** | Good coverage: atomicity (SNAP-03), backward compat (SNAP-02), portfolio_data (SNAP-01) |

### Security Checklist (PASS)
- Date format validation prevents path traversal (`datetime.strptime` on line 38, 82, 112)
- Atomic write pattern prevents corrupt snapshots (temp file + rename at lines 55-60)
- JSON loading is safe from injection
- Benchmark ticker fetched from env var but passed directly to yfinance (acceptable; ticker syntax validated by yfinance API)

---

_Reviewed: 2026-04-24_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
