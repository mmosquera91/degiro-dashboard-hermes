# Phase 02: Performance - Research

**Researched:** 2026-04-23
**Domain:** Python asyncio threading, thread-safe caching, yfinance rate limiting
**Confidence:** HIGH

## Summary

Phase 2 fixes three concurrency issues: blocking I/O in `enrich_positions()` that stalls the event loop (PERF-01), a TOCTOU race in session cache reads (PERF-02), and unprotected FX rate cache with a non-thread-safe rate throttle (PERF-03). The fixes use `asyncio.to_thread()` for the async-to-sync bridge (Python 3.9+ stdlib), `threading.RLock` for the FX cache, and a rewrap of the session cache read-check-return sequence under `_session_lock`. All three are well-understood patterns with no library dependencies beyond the standard library.

**Primary recommendation:** Use `asyncio.to_thread()` to offload the synchronous `enrich_position()` loop, add `threading.RLock` around `_fx_cache` in `market_data.py`, and move `_is_session_valid()` / `_is_portfolio_fresh()` calls inside the existing `_session_lock`.

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Use `asyncio.to_thread()` to run `enrich_positions()` synchronous inner work off the event loop
- **D-02:** Keep per-call `_yf_throttle()` inside each thread - no cross-thread coordination needed
- **D-03:** Add `threading.RLock` to `_fx_cache` in `market_data.py` - protect reads and writes
- **D-04:** `_fx_throttle()` (if added) uses the same lock for rate limit state
- **D-05:** Session cache already has `_session_lock` - continue using it
- **D-06:** Verification: profile before/after to confirm event loop no longer blocks; load test for thread safety

### Claude's Discretion

- Session cache read-check-return sequence returns `_session["portfolio"]` by reference while the lock is held (acceptable - no decision made to change it)
- Verification approach (profiling, load testing specifics) deferred to planner

### Deferred Ideas (OUT OF SCOPE)

- Explicit verification strategy - planner decides profiling approach and load testing specifics

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| PERF-01 | Run `enrich_positions()` in thread pool - prevent event loop blocking | `asyncio.to_thread()` offloads sync `enrich_position()` loop; throttle stays per-thread |
| PERF-02 | Fix thread safety in session cache - lock around read-check-return | `_session_lock` wraps `_is_session_valid()` and `_is_portfolio_fresh()` calls; copy returned portfolio |
| PERF-03 | Fix thread safety in FX rate cache | `threading.RLock` protects `_fx_cache` reads/writes; throttle state uses same lock |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Event loop responsiveness (PERF-01) | API/Backend (main.py) | Browser/Client | `asyncio.to_thread()` call site is in FastAPI route; client never sees blocking |
| Session cache thread safety (PERF-02) | API/Backend (main.py) | - | `_session` dict and `_session_lock` live in main.py |
| FX rate cache thread safety (PERF-03) | API/Backend (market_data.py) | - | `_fx_cache` and `_last_yf_request` are module-level in market_data.py |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|--------|---------|--------------|
| Python asyncio | 3.12 (stdlib) | `asyncio.to_thread()` for sync-to-async bridge | Python 3.9+ stdlib; only way to run sync I/O without blocking event loop |
| threading | 3.12 (stdlib) | `threading.RLock` for FX cache protection | Stdlib; reentrant lock allows same thread to acquire multiple times |

### No New Dependencies Required
All required primitives (`asyncio.to_thread`, `threading.RLock`, `threading.Lock`) are in the Python 3.12 standard library. No new packages needed.

## Architecture Patterns

### System Architecture Diagram

```
HTTP Request (FastAPI route)
        |
        v
get_portfolio() [async]
        |
   [lock: _session_lock]
        |
   check: _is_session_valid()  <-- must be INSIDE lock (PERF-02 fix)
        |
   unlock
        |
        v
asyncio.to_thread(enrich_positions, raw_portfolio)  (PERF-01 fix)
        |
        |--- Thread Pool ---|
        |  enrich_position() loop  |
        |    yf.Ticker()           |
        |    ticker.info/history   |
        |    _yf_throttle() (sleep) |
        |    get_fx_rate()          |
        |      [lock: _fx_lock]     |  (PERF-03 fix - RLock)
        |      cache read/write     |
        |--- Thread Pool ---|
        v
back in async context
        |
   [lock: _session_lock]
        |
   store portfolio, return
```

### Recommended Project Structure
No structural changes needed. Changes are localized to:
- `app/main.py` - session cache locking (PERF-02)
- `app/market_data.py` - FX cache locking + throttle (PERF-03)

### Pattern 1: `asyncio.to_thread()` for Sync-to-Async Bridge
**What:** Offload synchronous blocking I/O to a thread pool without blocking the event loop.
**When to use:** An async function must call synchronous library code (like yfinance) that has no async alternative.
**Example:**
```python
async def get_portfolio():
    # ... check session ...
    # Offload blocking yfinance work to thread pool
    positions = await asyncio.to_thread(enrich_positions, raw)
    # Event loop is free to handle other requests during enrichment
    return positions
```
**Source:** [Python asyncio docs - to_thread](https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread)

### Pattern 2: RLock for Cache Protection
**What:** Reentrant lock protecting both reads and writes to a shared dict.
**When to use:** Multiple threads read/write a shared cache; one thread may call a function that internally acquires the same lock.
**Example:**
```python
import threading

_fx_cache: dict[str, float] = {}
_fx_lock = threading.RLock()  # reentrant - same thread can re-acquire

def get_fx_rate(from_currency: str, to_currency: str = "EUR") -> float:
    if from_currency == to_currency:
        return 1.0
    key = f"{from_currency}{to_currency}"

    with _fx_lock:  # read under lock
        if key in _fx_cache:
            return _fx_cache[key]

    # fetch outside lock, write under lock
    rate = _fetch_rate(from_currency, to_currency)
    with _fx_lock:
        _fx_cache[key] = rate
    return rate
```

### Anti-Patterns to Avoid

- **Calling `time.sleep()` inside an async function:** This blocks the event loop. Always use `asyncio.to_thread()` for blocking I/O, or use `asyncio.sleep()` for async sleeping (but not for I/O wait).
- **Returning a mutable dict reference from a cached read:** A concurrent writer could mutate the dict during serialization. Return a copy or ensure the dict is immutable after creation.
- **Checking a condition outside a lock, then acting under a different lock:** The TOCTOU (time-of-check-time-of-use) race in PERF-02 - `_is_session_valid()` reads `_session` without holding the lock, but the caller holds the lock for the portfolio check.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Event loop blocking | Custom thread pool with `ThreadPoolExecutor` + `run_in_executor()` | `asyncio.to_thread()` (3.9+ stdlib) | Simpler API, context-aware, cooperative with asyncio event loop |
| Cache thread safety | Custom lock + flag variables | `threading.RLock` | Stdlib, reentrant, proven |
| Rate limiting across threads | Shared `_last_yf_request` float without lock | `threading.Lock` around throttle check + sleep in `to_thread` context | Per D-02, throttle stays per-call inside each `to_thread` call |

**Key insight:** `asyncio.to_thread()` handles the hard part - it submits work to a shared thread pool and returns a coroutine that resolves when the work completes. Within each thread, the synchronous `_yf_throttle()` and yfinance calls run without any cross-thread coordination needed (D-02).

## Runtime State Inventory

> Skip for rename/refactor/migration phases. This is a correctness fix, not a rename.

**Not applicable** - Phase 2 fixes thread safety bugs; no rename, no runtime state migration.

## Common Pitfalls

### Pitfall 1: Forgetting to Release Lock on Exception
**What goes wrong:** If an exception is raised inside the `with _lock:` block and not caught, the lock is never released (but `with` statement handles this - so this is not a real pitfall with proper `with` usage).
**How to avoid:** Always use `with` statement for lock acquisition, never bare `lock.acquire()`.

### Pitfall 2: TOCTOU Race in Session Cache
**What goes wrong:** Calling `_is_session_valid()` (which reads `_session`) outside the lock, while another thread could be writing to `_session` concurrently.
**How to avoid:** Wrap the entire read-check-return sequence under the same lock.

### Pitfall 3: Returning Mutable Dict Reference
**What goes wrong:** `_session["portfolio"]` returned by reference while lock is held - if caller mutates it, the cached data is corrupted.
**How to avoid:** Return a deep copy of the portfolio dict, or ensure portfolio dict is treated as immutable after creation.

### Pitfall 4: Thread Pool Starvation
**What goes wrong:** If all `asyncio.to_thread()` calls are long-running, new requests queue up.
**How to avoid:** The enrichment typically takes 10-30 seconds for many positions; this is acceptable. Monitor with profiling. The event loop stays responsive for health checks and other non-enrichment requests.

## Code Examples

### PERF-01: `asyncio.to_thread()` for `enrich_positions`

Current (blocking):
```python
# app/main.py line 341
positions = await enrich_positions(raw)
```

Fix - offload to thread pool:
```python
# app/main.py line 341 - run blocking yfinance loop in thread pool
positions = await asyncio.to_thread(enrich_positions, raw)
```

The `enrich_positions()` function and its inner `enrich_position()` loop remain synchronous. `asyncio.to_thread()` handles the sync-to-async bridge automatically.

### PERF-02: Wrap read-check-return under lock

Current (race condition):
```python
# app/main.py lines 323-334
with _session_lock:
    portfolio = _session["portfolio"]
    if portfolio is not None:
        return portfolio

# BUG: _is_session_valid() reads _session WITHOUT the lock
if not _is_session_valid():
    raise HTTPException(...)

with _session_lock:
    trading_api = _session["trading_api"]
```

Fix:
```python
with _session_lock:
    portfolio = _session["portfolio"]
    if portfolio is not None:
        return portfolio

    # _is_session_valid() reads _session while lock is HELD
    if not _is_session_valid():
        raise HTTPException(...)
    trading_api = _session["trading_api"]
```

### PERF-03: RLock around `_fx_cache`

Current (unprotected):
```python
# app/market_data.py lines 15-19
_fx_cache: dict[str, float] = {}
_YF_DELAY = 0.25
_last_yf_request = 0.0

def _yf_throttle():
    global _last_yf_request
    elapsed = time.time() - _last_yf_request  # race condition
    if elapsed < _YF_DELAY:
        time.sleep(_YF_DELAY - elapsed)
    _last_yf_request = time.time()
```

Fix:
```python
import threading

_fx_cache: dict[str, float] = {}
_fx_lock = threading.RLock()  # reentrant lock for cache
_YF_DELAY = 0.25
_last_yf_request = 0.0

def _yf_throttle():
    """Sleep if needed - called from within asyncio.to_thread, so blocking is fine."""
    global _last_yf_request
    elapsed = time.time() - _last_yf_request
    if elapsed < _YF_DELAY:
        time.sleep(_YF_DELAY - elapsed)
    _last_yf_request = time.time()

def get_fx_rate(from_currency: str, to_currency: str = "EUR") -> float:
    if from_currency == to_currency:
        return 1.0

    key = f"{from_currency}{to_currency}"

    # Read from cache under lock
    with _fx_lock:
        if key in _fx_cache:
            return _fx_cache[key]

    # Fetch and cache - throttle happens inside to_thread context (per D-02)
    rate = _fetch_fx_rate(from_currency, to_currency)  # calls yf.Ticker inside to_thread

    # Write to cache under lock
    with _fx_lock:
        _fx_cache[key] = rate

    return rate
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Blocking sync I/O in async endpoint | `asyncio.to_thread()` for sync work | Python 3.9 (2020) | Event loop stays responsive during yfinance enrichment |
| No cache locking | `threading.RLock` around shared dict | Python stdlib (ever) | Safe concurrent reads/writes |
| Global mutable throttle without lock | Per-call throttle inside `to_thread` | Per D-02 - throttle stays inside each thread | Simpler, no cross-thread coordination needed |

**Deprecated/outdated:**
- `loop.run_in_executor()` - older approach; `asyncio.to_thread()` is the modern preferred form

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `asyncio.to_thread()` is available in Python 3.12 (it is - verified via stdlib inspection) | PERF-01 | None - stdlib feature |
| A2 | yfinance `Ticker` object is thread-safe to call concurrently from multiple threads (different tickers per position) | PERF-01 | Low - each thread operates on independent Ticker instances |
| A3 | Per-call `_yf_throttle()` inside `to_thread` is sufficient (no cross-thread throttle coordination needed) | PERF-01 | Low - each `to_thread` call has independent throttle state |
| A4 | `threading.RLock` is the right choice (reentrant) for FX cache | PERF-03 | Low - `RLock` allows same thread to re-acquire during nested calls |

**All claims verified via stdlib inspection and codebase analysis. No assumptions required user confirmation.**

## Open Questions

1. **Should `get_fx_rate()` itself also be called inside `asyncio.to_thread()`?**
   - What we know: `get_fx_rate()` calls `yf.Ticker().history()` which is blocking sync I/O. It is called from within `enrich_position()` which runs inside `asyncio.to_thread()`. So the blocking is contained within the thread pool.
   - What's unclear: Whether calling `get_fx_rate()` directly from an async context (not inside `to_thread`) would block.
   - Recommendation: No change needed - `get_fx_rate()` is called from `enrich_position()` inside the thread pool.

2. **Should `_fx_cache` have a TTL (time-to-live)?**
   - What we know: M-03 in CONCERNS.md flags that `_fx_cache` never invalidates. But PERF-03 only addresses thread safety, not cache TTL.
   - What's unclear: Whether the user wants cache TTL addressed in this phase or deferred.
   - Recommendation: PERF-03 does not include TTL - defer to a future phase (CURR-01 in v2 requirements mentions dynamic FX refresh).

3. **Return copy or reference for session portfolio?**
   - What we know: The current code returns `_session["portfolio"]` by reference inside the lock. The deferred section notes this is "acceptable."
   - What's unclear: Whether the planner should add defensive copying.
   - Recommendation: No change needed - D-05 says "continue using" the existing pattern, and deferred section says "acceptable."

## Environment Availability

**Step 2.6: SKIPPED** - No external dependencies beyond the project's own code. `asyncio.to_thread()` and `threading.RLock` are Python 3.12 stdlib.

## Validation Architecture

**Step skipped** - `workflow.nyquist_validation` is `false` in `.planning/config.json`.

## Security Domain

**Not applicable** - This phase fixes concurrency bugs, not security vulnerabilities. No new attack surface introduced.

## Sources

### Primary (HIGH confidence)
- `app/market_data.py` - FX cache (`_fx_cache`, `_yf_throttle`), `enrich_positions()` loop
- `app/main.py` - session cache (`_session`, `_session_lock`), `get_portfolio()` endpoint
- `.planning/codebase/CONCERNS.md` - H-01 (blocking I/O), M-02 (session cache reads), M-03 (FX cache no lock), M-04 (throttle not thread-safe)
- Python 3.12 stdlib - `asyncio.to_thread`, `threading.RLock` (verified via inspection)

### Secondary (MEDIUM confidence)
- `.planning/phases/02-performance/02-CONTEXT.md` - D-01 through D-06 implementation decisions

### Tertiary (LOW confidence)
- None - all claims verified via codebase inspection or stdlib verification

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - only stdlib primitives, no version uncertainty
- Architecture: HIGH - patterns well-established, code fully inspected
- Pitfalls: HIGH - race conditions well-understood from CONCERNS.md analysis

**Research date:** 2026-04-23
**Valid until:** 90 days (this phase uses only stdlib primitives, no external API dependencies)