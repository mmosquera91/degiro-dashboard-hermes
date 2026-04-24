# Phase 8: Startup Portfolio Restoration - Research

**Researched:** 2026-04-24
**Domain:** FastAPI application lifecycle, session state restoration from disk snapshots
**Confidence:** HIGH

## Summary

Phase 8 implements startup portfolio restoration: after a container restart, the FastAPI app loads the latest snapshot via `load_latest_snapshot()` and restores it into `_session["portfolio"]`, allowing the dashboard to render immediately without any DeGiro session. The key implementation involves an `@app.on_event("startup")` async handler that acquires `_session_lock`, calls `load_latest_snapshot()`, and populates `_session["portfolio"]` and `_session["portfolio_time"]`. The existing `get_portfolio()` endpoint already serves `_session["portfolio"]` directly (lines 361-364 in main.py) without session validation, which satisfies REST-03 (401 only when both session expired AND no cached portfolio).

**Primary recommendation:** Use the existing `@app.on_event("startup")` hook (already present in main.py) to call `load_latest_snapshot()` and restore portfolio state, applying the thread-safe pattern with `_session_lock`.

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** On app startup, `load_latest_snapshot()` is called and portfolio is restored into `_session["portfolio"]`
- **D-02:** Dashboard serves last-known portfolio immediately after restart (no DeGiro session required)
- **D-03:** NO automatic portfolio refresh is triggered after startup restore
- **D-04:** DeGiro session is always user-triggered: user calls refresh API -> app connects to DeGiro -> fetches portfolio -> disconnects
- **D-05:** After startup restore, the app serves the snapshot portfolio only. No background task, no session check, no auto-fetch
- **D-06:** The snapshot contains the last known portfolio state from when the user last manually triggered a fetch
- **D-07:** `_is_session_valid()` returns False in normal operation (trading_api is None)
- **D-08:** Session TTL check does not block serving restored snapshot portfolio
- **D-09:** On `get_portfolio()` call: if session valid -> fetch fresh; if session invalid but snapshot exists -> serve snapshot; if neither -> return 401
- **D-10:** `load_latest_snapshot()` called in `@app.on_event("startup")` context manager
- **D-11:** Portfolio restored into `_session["portfolio"]` before startup event completes
- **D-12:** If snapshot's `portfolio_data` is None (old-format snapshot), treat as no snapshot (warn, continue, let login page handle)
- **D-13:** If no snapshot exists on first startup, app continues normally
- **D-14:** When session expired but cached portfolio exists: serve cached portfolio (no 401)
- **D-15:** When session expired AND no cached portfolio: 401 with "Session expired" message

### Deferred Ideas (OUT OF SCOPE)
- Benchmark data on startup restore (benchmark data is fetched fresh on `/api/benchmark` call; could store in snapshot in future phase)

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REST-01 | `@app.on_event("startup")` calls `load_latest_snapshot()` and restores portfolio into `_session["portfolio"]` | Startup handler calls load function, populates session dict under lock |
| REST-02 | Dashboard serves last-known portfolio immediately after restart (no DeGiro session required) | `get_portfolio()` lines 361-364 serve `_session["portfolio"]` directly without session check |
| REST-03 | Session TTL check does not block serving fresh cached portfolio (401 only when both session expired AND no cached portfolio) | Existing code path: portfolio served from cache (lines 361-364) bypasses `_is_session_valid()` check entirely |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Snapshot loading on startup | API/Backend (FastAPI) | -- | `load_latest_snapshot()` called in `@app.on_event("startup")` |
| Portfolio session restoration | API/Backend | -- | `_session["portfolio"]` is in-memory dict in FastAPI process |
| Session-TTL-aware serving | API/Backend | -- | `get_portfolio()` endpoint handles cache/session/401 logic |
| Thread-safe session access | API/Backend | -- | All `_session` access via `_session_lock` |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | current | Web framework | Already in project |
| Python threading | stdlib | Thread-safe session access | Already in project |

### No New Dependencies
Phase 8 uses only existing codebase infrastructure:
- `app.snapshots.load_latest_snapshot()` - already implemented
- `_session_lock` threading.Lock - already in main.py
- `@app.on_event("startup")` - already present in main.py

## Architecture Patterns

### System Architecture Diagram

```
[Container Start]
       |
       v
@app.on_event("startup")
       |
       v
load_latest_snapshot()  --> [SNAPSHOT_DIR / latest.json]
       |
       v
portfolio_data = snapshot["portfolio_data"]
       |
       v (portfolio_data is not None)
_session["portfolio"] = portfolio_data
_session["portfolio_time"] = datetime.now()
       |
       v
[Startup complete - app ready]

[HTTP GET /api/portfolio]
       |
       v
Is _session["portfolio"] not None?  --> YES --> return portfolio (no session check)
       |
       NO
       v
Is _is_session_valid()?  --> NO --> raise 401
       |
       YES
       v
Fetch from DeGiro, enrich, score, serve
```

### Recommended Project Structure
No new files needed. Changes confined to:
- `app/main.py` - add startup handler logic

### Pattern 1: Startup State Restoration
**What:** On FastAPI startup, load persisted snapshot into in-memory session
**When to use:** Restoring application state after process restart
**Example:**
```python
@app.on_event("startup")
async def on_startup():
    logger.info("Brokr starting up")
    # ... existing checks ...
    _restore_portfolio_from_snapshot()

def _restore_portfolio_from_snapshot():
    """Restore portfolio from latest snapshot on startup."""
    snapshot = load_latest_snapshot()
    if snapshot is None:
        logger.info("No snapshot found — starting fresh")
        return
    portfolio_data = snapshot.get("portfolio_data")
    if portfolio_data is None:
        logger.warning("Snapshot has no portfolio_data — skipping restore")
        return
    with _session_lock:
        _session["portfolio"] = portfolio_data
        _session["portfolio_time"] = datetime.now()
    logger.info("Portfolio restored from snapshot dated %s", snapshot["date"])
```

### Pattern 2: Session-Aware Portfolio Serving
**What:** `get_portfolio()` serves cached portfolio without session check, only fetches fresh when session valid and cache empty
**When to use:** When you want cached data to be served regardless of auth state
**Existing code (lines 361-364 in main.py) already implements this:**
```python
with _session_lock:
    portfolio = _session["portfolio"]
    if portfolio is not None:
        return portfolio  # No session check here!

# Only here does session check happen
if not _is_session_valid():
    raise HTTPException(status_code=401, ...)
```

### Anti-Patterns to Avoid
- **Don't block startup on snapshot load failure:** If snapshot loading fails, log and continue (D-13). The app should start normally and let the login page handle no-session state.
- **Don't auto-fetch after restore:** No background task, no `asyncio.create_task()` for refresh (D-03, D-05). User manually triggers fetch.
- **Don't use old-format snapshots for restore:** If `portfolio_data` is None (D-12), treat as no snapshot and warn. Old snapshots without enriched data are not useful for dashboard.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Thread-safe session access | Custom locking | `_session_lock` threading.Lock | Already implemented, proven pattern |
| Snapshot loading | Custom disk traversal | `load_latest_snapshot()` | Already implemented with date validation |
| Portfolio serving when unauthenticated | Block with 401 | Serve from `_session["portfolio"]` | Existing code path already does this |

**Key insight:** The existing `get_portfolio()` endpoint (lines 361-364) already serves `_session["portfolio"]` without checking `_is_session_valid()`. The only gap is populating `_session["portfolio"]` on startup.

## Common Pitfalls

### Pitfall 1: Startup Handler Not Awaited Properly
**What goes wrong:** If `load_latest_snapshot()` were async, calling it without `await` in an async handler would return a coroutine, not the result.
**Why it happens:** `load_latest_snapshot()` is synchronous. In an async context, it runs synchronously and blocks the event loop briefly, which is acceptable for a one-time startup task.
**How to avoid:** Call synchronously: `snapshot = load_latest_snapshot()` (no `await` needed since the function is sync). For running sync functions in async context, the codebase uses `asyncio.to_thread()` - not needed here since startup is one-time.
**Warning signs:** `TypeError: coroutine was not awaited` or snapshot data is a coroutine object.

### Pitfall 2: Forgetting `_session_lock` Around Session Writes
**What goes wrong:** Race condition if two threads read/write `_session` simultaneously during startup restoration.
**Why it happens:** FastAPI handles requests concurrently with multiple threads.
**How to avoid:** Always wrap `_session` reads and writes in `with _session_lock:`. The startup handler calls `_restore_portfolio_from_snapshot()` which internally acquires the lock.
**Warning signs:** Intermittent `None` portfolio after restart, race condition symptoms.

### Pitfall 3: Using `datetime.now()` vs Snapshot Date for Freshness
**What goes wrong:** If `portfolio_time` is set from snapshot date (e.g., 2 days old), `_is_portfolio_fresh()` would immediately return False.
**Why it happens:** `_is_portfolio_fresh()` checks `datetime.now() - _session["portfolio_time"] < PORTFOLIO_TTL`. If portfolio_time is old, portfolio is immediately stale.
**How to avoid:** Set `_session["portfolio_time"] = datetime.now()` on restore, not from snapshot. Freshness is relative to "when was this data last known good" - and on restore, we just loaded it, so it's "now."
**Important:** This does not affect serving behavior since `get_portfolio()` serves `_session["portfolio"]` directly without checking freshness (lines 361-364 bypass freshness check).

## Code Examples

### Startup Restoration (to add to main.py)
```python
# Add near existing on_startup handler
@app.on_event("startup")
async def on_startup():
    logger.info("Brokr starting up")
    try:
        import socket
        socket.gethostbyname("google.com")
        logger.info("DNS resolution: OK")
    except Exception as e:
        logger.error("DNS resolution failed: %s", e)
    # ... existing module checks ...

    # REST-01: Restore portfolio from latest snapshot
    _restore_portfolio_from_snapshot()


def _restore_portfolio_from_snapshot():
    """Restore portfolio from latest snapshot on startup (REST-01)."""
    snapshot = load_latest_snapshot()
    if snapshot is None:
        logger.info("No snapshot found on startup — starting fresh")
        return

    portfolio_data = snapshot.get("portfolio_data")
    if portfolio_data is None:
        # D-12: Old-format snapshot without portfolio_data — treat as no snapshot
        logger.warning("Snapshot dated %s has no portfolio_data — skipping restore", snapshot["date"])
        return

    with _session_lock:
        _session["portfolio"] = portfolio_data
        _session["portfolio_time"] = datetime.now()

    logger.info("Portfolio restored from snapshot dated %s", snapshot["date"])
```

### Existing `get_portfolio()` Serves Cached Without Session Check
```python
# Lines 361-364 in main.py — already implements REST-03
with _session_lock:
    portfolio = _session["portfolio"]
    if portfolio is not None:
        return portfolio  # <-- REST-03: served without session check

# Only reaches here if portfolio is None
if not _is_session_valid():
    raise HTTPException(
        status_code=401,
        detail="Session expired or not authenticated. Please reconnect via the UI.",
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No startup restoration | Load latest snapshot into `_session["portfolio"]` on startup | Phase 8 | Dashboard renders immediately after restart |

**Deprecated/outdated:**
- None relevant to Phase 8

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `get_portfolio()` lines 361-364 serve `_session["portfolio"]` without session check (REST-03) | Architecture Patterns | If this code path changed, REST-03 behavior would differ — verified by reading main.py directly |

**If this table is empty:** All claims in this research were verified or cited — no user confirmation needed.

## Open Questions

1. **Should `portfolio_time` be set on startup restore?**
   - What we know: `_is_portfolio_fresh()` uses `portfolio_time` to determine staleness. If not set, `_is_portfolio_fresh()` returns False immediately.
   - What's unclear: Whether any code path depends on `_is_portfolio_fresh()` returning True after startup restore.
   - Recommendation: Set `_session["portfolio_time"] = datetime.now()` on restore. This makes the portfolio "fresh" for PORTFOLIO_TTL (5 minutes), after which it becomes stale. But since `get_portfolio()` serves the cached portfolio directly without calling `_is_portfolio_fresh()`, this only affects the enrichment trigger path, which is acceptable.

2. **Should we update `_session["portfolio_time"]` when serving from cache in `get_portfolio()`?**
   - What we know: Currently, serving from cache (lines 361-364) does not update `portfolio_time`.
   - What's unclear: Whether updating `portfolio_time` on cache hit would cause unexpected behavior in other parts of the code.
   - Recommendation: Do NOT update `portfolio_time` when serving from cache. This preserves the "age" of the cached data and allows `_is_portfolio_fresh()` to indicate staleness correctly for the enrichment path.

## Environment Availability

**Step 2.6: SKIPPED (no external dependencies identified)**

Phase 8 is purely code changes to `app/main.py`. All dependencies (FastAPI, threading, `load_latest_snapshot()`) already exist in the project.

## Security Domain

> Required when `security_enforcement` is enabled (absent = enabled). Omit only if explicitly `false` in config.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V4 Access Control | yes | Bearer token auth on `/api/*` routes via `Depends(verify_brok_token)` — unchanged by Phase 8 |
| V5 Input Validation | no | Phase 8 reads from disk snapshot (already validated JSON), no new user input |

### Known Threat Patterns for Python/FastAPI

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via SNAPSHOT_DIR | Tampering | `load_latest_snapshot()` validates date format in filename before reading |
| Snapshot corruption on crash | Tampering | SNAP-03 atomic rename pattern (write to .tmp, fsync, rename) — already implemented in Phase 7 |

## Sources

### Primary (HIGH confidence)
- `app/main.py` lines 1-550 — Verified `_session` structure, `_session_lock`, `get_portfolio()` logic, existing `@app.on_event("startup")` handler
- `app/snapshots.py` lines 94-130 — Verified `load_latest_snapshot()` signature and backward compatibility handling
- `docker-compose.yml` — Verified `brokr_snapshots` named volume at `/data/snapshots`

### Secondary (MEDIUM confidence)
- `.planning/phases/07-snapshot-format-extension/07-CONTEXT.md` — Verified snapshot format, portfolio_data structure, D-01 through D-15

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — only uses existing project infrastructure
- Architecture: HIGH — verified against existing code in main.py and snapshots.py
- Pitfalls: HIGH — based on verified codebase patterns

**Research date:** 2026-04-24
**Valid until:** 2026-05-24 (30 days — Phase 8 is a small, self-contained change)
