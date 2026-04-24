# Phase 07: Snapshot Format Extension - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-24
**Phase:** 07-snapshot-format-extension
**Areas discussed:** Snapshot format, Load behavior, Snapshot trigger

---

## Snapshot Format

| Option | Description | Selected |
|--------|-------------|----------|
| Extend + backward-compat | Add portfolio_data to snapshot dict, keep old-format readable. load_latest_snapshot() detects old format gracefully. | ✓ |
| New format only | New format only, no backward compat. Errors on old snapshots. | |
| Nested under portfolio_data key | portfolio_data at top level alongside existing fields. | |

**User's choice:** Extend + backward-compat (Recommended)
**Notes:** User wants existing snapshots to remain readable after upgrade. Portfolio data at top level alongside existing fields is the right structure.

---

## Load Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Portfolio data only | load_latest_snapshot() returns portfolio_data, benchmark fetched fresh. Simpler. | ✓ |
| Include benchmark data | Load returns both portfolio and benchmark data. No re-fetch needed. | |
| Separate benchmark load | Portfolio and benchmark loaded via separate functions. | |

**User's choice:** Portfolio data only (Recommended)
**Notes:** User prefers simplicity — benchmark is fetched fresh on `/api/benchmark` calls. Phase 8 planner handles how load_latest_snapshot() handles old-format snapshots (portfolio_data = None).

---

## Snapshot Trigger

| Option | Description | Selected |
|--------|-------------|----------|
| After portfolio fetch | save_snapshot() called inside get_portfolio() after enrichment/scoring. Snapshot on every manual refresh. | ✓ |
| Manual snapshot endpoint | Separate /api/snapshot endpoint. More flexible but adds complexity. | |
| Automatic periodic | Background task saves snapshots periodically. Overkill for single-user. | |

**User's choice:** After portfolio fetch (Recommended)
**Notes:** Consistent with Phase 4 behavior — snapshots happen on user-triggered refresh. No separate endpoint or scheduler for Phase 7.

---

## Claude's Discretion

- Docker volume configuration (named volume vs bind mount) — planner decides based on DOCK-01, DOCK-02 requirements
- Exact implementation of atomic write (fsync timing, error handling) — planner follows standard pattern
- Backward compat detection logic in load_latest_snapshot() — planner implements graceful None return

## Deferred Ideas

- Benchmark data persistence in snapshot (future phase — not needed for Phase 7)
- Snapshot retention/cleanup policy (future phase — not planned)