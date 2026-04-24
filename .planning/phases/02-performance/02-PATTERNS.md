# Phase 02: Performance - Pattern Map

**Mapped:** 2026-04-23
**Files analyzed:** 2
**Analogs found:** 2 / 2

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/main.py` (PERF-01) | controller | async-to-sync bridge | existing `enrich_positions` call at line 341 | self-referential |
| `app/main.py` (PERF-02) | controller | request-response | `_session_lock` write pattern at lines 272-276 | exact (same lock, same file) |
| `app/market_data.py` (PERF-03) | utility | file-I/O + caching | `get_fx_rate()` itself before fix | self-referential |

## Pattern Assignments

### `app/main.py` - PERF-01: `asyncio.to_thread()` for `enrich_positions`

**Fix location:** Line 341 in `get_portfolio()` async endpoint

**Current pattern (blocking - H-01 in CONCERNS.md):**
```python
# Line 341 - BLOCKING: sync enrich_positions inside async function stalls event loop
positions = await enrich_positions(raw)
```

**Fix pattern (non-blocking):**
```python
# Line 341 - Offload blocking yfinance loop to thread pool via stdlib asyncio.to_thread
positions = await asyncio.to_thread(enrich_positions, raw)
```

**Import needed:** `asyncio` is already available via Python stdlib (3.9+); no new imports required.

**Pattern source:** Python 3.12 stdlib `asyncio.to_thread()` — research confirms this is the recommended sync-to-async bridge (replaces `run_in_executor`).

---

### `app/main.py` - PERF-02: Session cache read-check-return under lock

**Fix location:** Lines 323-334 in `get_portfolio()` — `_is_session_valid()` called outside the lock

**Current pattern (race condition - M-02 in CONCERNS.md):**
```python
# Lines 323-327 - Lock held for cache read, but _is_session_valid() called AFTER unlock
with _session_lock:
    portfolio = _session["portfolio"]
    if portfolio is not None:
        return portfolio

# BUG: _is_session_valid() reads _session WITHOUT the lock (M-02)
if not _is_session_valid():
    raise HTTPException(...)

# Lines 334-341 - Lock reacquired for trading_api access
with _session_lock:
    ...
```

**Fix pattern (lock-wrapped read-check-return):**
```python
# Move _is_session_valid() call INSIDE the lock
with _session_lock:
    portfolio = _session["portfolio"]
    if portfolio is not None:
        return portfolio

    # _is_session_valid() now reads _session while lock is HELD (fixes TOCTOU race)
    if not _is_session_valid():
        raise HTTPException(...)
    trading_api = _session["trading_api"]
```

**Lock pattern source:** Existing `_session_lock` usage at lines 272-276 (auth endpoint) and 299-303 (session auth) — same lock, same pattern for write operations.

**Concrete lock usage to copy from lines 272-276:**
```python
with _session_lock:
    _session["trading_api"] = trading_api
    _session["session_time"] = datetime.now()
    _session["portfolio"] = None
    _session["portfolio_time"] = None
```

---

### `app/market_data.py` - PERF-03: FX cache thread-safety with `threading.RLock`

**Fix location:** Module-level globals at lines 15-19, `get_fx_rate()` at lines 31-80

**Current pattern (no lock - M-03/M-04 in CONCERNS.md):**
```python
# Lines 15-19 - No lock protecting _fx_cache
_fx_cache: dict[str, float] = {}
_YF_DELAY = 0.25
_last_yf_request = 0.0

def _yf_throttle():
    global _last_yf_request
    elapsed = time.time() - _last_yf_request  # race condition: no lock
    if elapsed < _YF_DELAY:
        time.sleep(_YF_DELAY - elapsed)
    _last_yf_request = time.time()
```

**Fix pattern (RLock around cache reads/writes):**
```python
import threading

# Add reentrant lock at module level (after line 15)
_fx_cache: dict[str, float] = {}
_fx_lock = threading.RLock()  # reentrant lock protects cache reads/writes
_YF_DELAY = 0.25
_last_yf_request = 0.0

def get_fx_rate(from_currency: str, to_currency: str = "EUR") -> float:
    if from_currency == to_currency:
        return 1.0

    key = f"{from_currency}{to_currency}"

    # Read from cache under lock
    with _fx_lock:
        if key in _fx_cache:
            return _fx_cache[key]

    # Fetch outside lock (rate limiting happens inside to_thread per D-02)
    rate = _fetch_fx_rate(from_currency, to_currency)

    # Write to cache under lock
    with _fx_lock:
        _fx_cache[key] = rate

    return rate
```

**Pattern source:** The `_yf_throttle()` function at lines 22-28 already uses `time.sleep()` which blocks (acceptable inside `to_thread` per D-02). The RLock pattern is standard Python stdlib (`threading.RLock`) — no external analog needed.

**RLock rationale:** Reentrant because `get_fx_rate()` may be called from within a function that already holds `_fx_lock` (nested calls). Standard `threading.Lock` would deadlock; `RLock` allows same thread to re-acquire.

---

## Shared Patterns

### Threading Lock Pattern

**Source:** `app/main.py` lines 31, 272-276, 299-303, 352-354, 418-419

**Pattern:**
```python
_session_lock = threading.Lock()

# Usage with context manager (always use 'with' to avoid leaked locks)
with _session_lock:
    # read or write _session dict
    _session["trading_api"] = trading_api
```

**Apply to:** All session cache access in main.py, FX cache access in market_data.py

### Async-to-Sync Bridge Pattern

**Source:** Python 3.12 stdlib `asyncio.to_thread()`

**Pattern:**
```python
# Inside async function — offload synchronous blocking work to thread pool
result = await asyncio.to_thread(synchronous_function, arg1, arg2)
```

**Apply to:** PERF-01 fix in main.py line 341

---

## No Analog Found

All files have direct analogs within the existing codebase or are self-referential fixes. No external pattern sources needed.

| File | Reason |
|------|--------|
| `app/main.py` PERF-01 | `asyncio.to_thread()` is stdlib — no project analog exists, but stdlib pattern is well-established |
| `app/main.py` PERF-02 | Fix is within same file using the same `_session_lock` already in use |
| `app/market_data.py` PERF-03 | `threading.RLock` is stdlib — no project analog for cache locking yet |

---

## Modification Summary

| Concern ID | Severity | Fix | File | Lines |
|------------|----------|-----|------|-------|
| H-01 | CRITICAL | `asyncio.to_thread(enrich_positions, raw)` | main.py | 341 |
| M-02 | MEDIUM | Move `_is_session_valid()` call inside `_session_lock` | main.py | 323-334 |
| M-03 | MEDIUM | Add `threading.RLock` around `_fx_cache` reads/writes | market_data.py | 15-80 |
| M-04 | MEDIUM | Per-call `_yf_throttle()` stays inside `to_thread` (no cross-thread coordination) | market_data.py | 22-28 |

## Metadata

**Analog search scope:** `app/main.py`, `app/market_data.py`
**Files scanned:** 2
**Pattern extraction date:** 2026-04-23
**Confidence:** HIGH — all fixes use stdlib primitives with clear analogs in the existing codebase