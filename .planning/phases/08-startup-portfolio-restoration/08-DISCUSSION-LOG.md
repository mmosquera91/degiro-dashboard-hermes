# Phase 08: Startup Portfolio Restoration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-24
**Phase:** 08-startup-portfolio-restoration
**Areas discussed:** Startup data freshness, Portfolio TTL behavior, First-startup handling

---

## Startup Data Freshness

| Option | Description | Selected |
|--------|-------------|----------|
| Serve as-is (recommended) | Serve snapshot data immediately. Fast, no DeGiro needed. Metrics may be stale since last snapshot. | |
| Re-enrich on startup | Run yfinance enrichment on startup. Fresh metrics but slower startup and requires DeGiro session. | |
| Hybrid (background refresh) | Do both — serve snapshot immediately, then re-enrich in background if session is valid. | ✓ |

**User's choice:** Hybrid (background refresh)
**Notes:** User wants fresh metrics eventually but not at the cost of blocking startup. Background refresh is the right approach.

---

## Portfolio TTL Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Skip TTL (recommended) | Bypass PORTFOLIO_TTL check. Dashboard always shows restored data until you explicitly refresh. | ✓ |
| Respect 5-min TTL | After 5 minutes, background refresh kicks in (if session is valid) to get fresh data. | |

**User's choice:** Skip TTL (recommended)
**Notes:** Restored portfolio is treated as fresh — no auto-refresh based on time elapsed since restore.

---

## First-Startup Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Warn and continue (recommended) | App starts normally. Dashboard shows empty state. Logs a warning. | |
| Error but continue | App starts but logs an error. Dashboard shows empty state. | |
| Fail fast | App refuses to start without a snapshot or valid session. | |

**User's choice:** there is already a login page when there's no snapshot present
**Notes:** User clarified that the existing login page handles the no-session state when no snapshot is present — no special handling needed, no fail-fast behavior.

---

## Claude's Discretion

- No areas deferred to Claude — all decisions made by user

## Deferred Ideas

- Benchmark data on startup restore: benchmark ^GSPC series not stored in snapshot (fetched fresh on /api/benchmark). Could store in future phase.