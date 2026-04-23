# Phase 03: Health Indicators - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-23
**Phase:** 03-health-indicators
**Areas discussed:** Alert format, Threshold config, Target weights, Drawdown detection

---

## Alert Format

| Option | Description | Selected |
|--------|-------------|----------|
| Boolean flags | Simple on/off per alert type. Minimal payload. No position detail. | |
| Structured objects | Objects with type, severity, triggering positions, current value vs threshold. Richer for Hermes and dashboard. | ✓ |
| Claude decides | Pick based on existing API patterns and Hermes context cleanliness. | |

**User's choice:** Claude decides
**Notes:** Structured objects selected — richer for Hermes context and dashboard rendering while keeping a clean list format.

---

## Threshold Configuration

| Option | Description | Selected |
|--------|-------------|----------|
| Environment variables | Per-deployment tuning without code changes. Consistent with HOST, BROKR_AUTH_TOKEN pattern. | ✓ |
| Hardcoded constants | Simpler but requires redeploy to change. | |

**User's choice:** Environment variables
**Notes:** Four env vars: HEALTH_POSITION_THRESHOLD, HEALTH_SECTOR_THRESHOLD, HEALTH_DRAWDOWN_THRESHOLD, HEALTH_REBALANCE_THRESHOLD with sensible defaults.

---

## Target Weights

| Option | Description | Selected |
|--------|-------------|----------|
| Environment variables | TARGET_ETF_PCT=70, TARGET_STOCK_PCT=30. Consistent with other config. | ✓ |
| Hardcoded in code | Keep 70/30 in context_builder.py. | |

**User's choice:** Environment variables
**Notes:** Also removes hardcoded 70/30 from context_builder.py and replaces with env var reads.

---

## Drawdown Detection

| Option | Description | Selected |
|--------|-------------|----------|
| Track peak in memory | Module-level peak value. Resets on session clear. Session-bound only. | |
| YTD as proxy | Weighted average of position perf_ytd values. No snapshot storage needed. | ✓ |
| Defer to Phase 4 | Placeholder until Phase 4 adds historical snapshots. | |

**User's choice:** YTD as proxy
**Notes:** Uses existing perf_ytd per position (from yfinance) weighted by position EUR value. Avoids adding snapshot infrastructure in Phase 3.

---

## Claude's Discretion

- Alert format (D-01 through D-04) — Claude selected structured objects with type/severity/message/current_value/threshold/triggering_positions

## Deferred Ideas

- Historical drawdown tracking: If Phase 4 adds portfolio snapshots, HEALTH-03 could use actual peak tracking instead of YTD proxy. Leave the door open.
