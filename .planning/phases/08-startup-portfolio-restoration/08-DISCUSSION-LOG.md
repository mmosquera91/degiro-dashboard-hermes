# Phase 08: Startup Portfolio Restoration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-24
**Phase:** 08-startup-portfolio-restoration
**Areas discussed:** No Auto-Fetch Model, Session TTL Behavior

---

## No Auto-Fetch Model

| Option | Description | Selected |
|--------|-------------|----------|
| No auto-fetch | App restores from snapshot on startup. No automatic fetch — user triggers fetch manually via API call. | ✓ |
| Session check only | Check if session is valid, but only alert the user or set a flag — no automatic fetch. | |
| Auto-fetch in background | Re-fetch portfolio automatically in background after startup restore if session valid. User gets fresh data without asking. | |

**User's choice:** No auto-fetch
**Notes:** DeGiro session is always user-triggered: user calls refresh API → app connects to DeGiro → fetches portfolio → disconnects. After that, a copy of the portfolio remains in the local app and in the snapshot. No persistent session ever exists.

---

## Session TTL Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| No TTL gating, serve snapshot | `_is_session_valid()` always returns False on startup. App serves cached portfolio immediately with no TTL gating. | ✓ |
| Session check only on manual refresh | The distinction matters — on app startup, no session check is done, but on explicit user-triggered refresh, we check session before fetching. | |

**User's choice:** No TTL gating, serve snapshot
**Notes:** User noted they don't know if `_is_session_valid()` is even useful for their setup. Deferred to Claude's judgment — Claude decided to simplify by having it always return False since no persistent session exists.

---

## Deferred Ideas

No scope creep occurred during discussion.
