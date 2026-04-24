# Phase 06: Testing - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-24
**Phase:** 06-testing
**Areas discussed:** Test file location, Mock strategy, CI integration, Coverage target

---

## Gray Area Selection

User deferred all decisions to Claude ("not sure, you decide").

## Decisions Made

### Test File Location

Claude chose: **`tests/` directory at project root**

Rationale: Keeps `app/` clean (matches Docker `.dockerignore` exclude pattern), mirrors standard Python project layout, excluded from Docker image via `.dockerignore`.

### Mock Strategy

Claude chose: **`unittest.mock.patch` for yfinance, DeGiro API, FX lookups**

Rationale: Standard library, no additional dependencies, sufficient for mocking external calls. Tests must be deterministic with no live network calls.

### CI Integration

Claude chose: **Simple shell script (`scripts/run_tests.sh`)**

Rationale: No complex CI pipeline for v1. Shell script is portable and can be called by GitHub Actions or similar later.

### Coverage Target

Claude chose: **Core logic paths only**

Rationale: Focus on happy paths, known edge cases, error handling. Full branch coverage not required for v1.

---

## Summary

Phase 6 context captured with all testing decisions deferred to standard best practices. User confirmed ready to proceed.