# Phase 02: Performance - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-23
**Phase:** 02-performance
**Areas discussed:** Threading approach, Rate limiting design, Lock architecture

---

## Threading Approach

| Option | Description | Selected |
|--------|-------------|----------|
| asyncio.to_thread() | Simple — one call wrapping synchronous inner work. Clean, minimal. Works for single-user app. | ✓ |
| ThreadPoolExecutor bounded | Explicit ThreadPoolExecutor with max_workers=4 or configurable. More control but more code. | |
| Background queue | Full task queue with separate workers. Overkill for single-user, adds complexity. | |

**User's choice:** asyncio.to_thread() (Recommended)
**Notes:** Per-call throttle inside each thread — no cross-thread coordination needed

---

## Rate Limiting Design

| Option | Description | Selected |
|--------|-------------|----------|
| Per-call throttle (inside each thread) | Keep the 0.25s delay inside each thread, so there's no cross-thread coordination needed. Simpler, works correctly under concurrent threads. | ✓ |
| Global throttler with lock | Shared throttle state that coordinates across all threads. Needs thread-safe locking around time.time() access. More complex. | |
| Remove throttle entirely | Let yfinance's built-in rate limiting handle it. No throttle code at all. Less predictable. | |

**User's choice:** Per-call throttle (inside each thread) (Recommended)
**Notes:** Keep _yf_throttle as-is, per-call, inside each thread

---

## Lock Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Add lock to FX cache only | Add RLock around the session cache operations (reads + writes). Simple fix for the known race condition. | ✓ |
| Separate locks for session and FX | Both session and FX cache get their own locks. Different concerns, separate isolation. | |
| Unified locking strategy | One lock coordinates both caches. Simpler but may add contention under concurrent requests. | |

**User's choice:** Add lock to FX cache only (Recommended)
**Notes:** FX cache in market_data.py gets a threading.RLock. Session cache already has _session_lock.

---

## Claude's Discretion

Verification approach was not discussed — planner decides profiling and load testing specifics.

## Deferred Ideas

- Verification approach: profile before/after + load test for thread safety under concurrent requests
- Session cache read issue noted but not addressed — return-by-reference pattern acceptable as-is