---
phase: 08-startup-portfolio-restoration
reviewed: 2026-04-24T00:00:00Z
depth: standard
files_reviewed: 1
files_reviewed_list:
  - app/main.py
findings:
  critical: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
---

# Phase 08: Code Review Report

**Reviewed:** 2026-04-24T00:00:00Z
**Depth:** standard
**Files Reviewed:** 1
**Status:** issues_found

## Summary

Reviewed `app/main.py` (579 lines). The file is generally well-structured with good security practices (timing-safe token comparison, CSRF middleware, Content-Security-Policy headers). The portfolio snapshot restore logic on startup is sound. Two warnings and two info-level findings were identified.

## Warnings

### WR-01: Blocking DNS call inside async startup handler

**File:** `app/main.py:261-265`
**Issue:** `socket.gethostbyname("google.com")` is a synchronous blocking call. It is invoked directly inside an `async def on_startup()` function without wrapping in `asyncio.to_thread()` or `run_in_executor()`. On slow DNS or network issues, this blocks the entire asyncio event loop during startup.

**Fix:**
```python
await asyncio.to_thread(socket.gethostbyname, "google.com")
```
Or use `loop.run_in_executor(None, lambda: socket.gethostbyname("google.com"))`.

---

### WR-02: Misleading error message on portfolio fetch with valid but empty session

**File:** `app/main.py:396-400`
**Issue:** When `_is_session_valid()` returns `True` but `_session["portfolio"]` is `None`, the code raises HTTPException with `"Session expired or not authenticated"`. This is inaccurate — the DeGiro session is valid; only the portfolio cache is empty. A caller will be misled about the actual problem.

**Fix:**
```python
if not _is_session_valid():
    raise HTTPException(
        status_code=401,
        detail="Session expired or not authenticated. Please reconnect via the UI.",
    )
# Remove the above block and keep only the portfolio-not-cached case, or
# split the error messages:
if _session["trading_api"] is None:
    raise HTTPException(
        status_code=401,
        detail="Session expired or not authenticated. Please reconnect via the UI.",
    )
# else: session valid but no cached portfolio — proceed to fetch
```

---

## Info

### IN-01: Deprecated `@app.on_event("startup")` alongside modern lifespan context manager

**File:** `app/main.py:257-283`
**Issue:** FastAPI 0.100+ deprecated `@app.on_event("startup")` in favor of the `lifespan` asynccontextmanager (already defined at line 242). Both mechanisms fire on startup, but mixing them reduces clarity. The lifespan at line 242-251 does not call `_restore_portfolio_from_snapshot()`, so the `on_startup` handler is needed — but this could be made explicit with a comment or consolidated into the lifespan.

**Fix:** Either migrate the DNS check, module checks, and snapshot restore fully into the lifespan context manager, or document why both mechanisms are needed.

---

### IN-02: Unused import

**File:** `app/main.py:3`
**Issue:** `import asyncio` is present but never used directly in the module. The only async usage is via `asyncio.to_thread` at line 408, but `asyncio` is implicitly available as a standard library module. In strict terms this is not an error, but it signals the import may have been left behind from a refactor.

**Fix:** Remove `import asyncio` if no direct `asyncio.X` calls are needed in the module itself (the `asyncio.to_thread` call in `get_portfolio` does not require the import at module level).

---

_Reviewed: 2026-04-24T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_