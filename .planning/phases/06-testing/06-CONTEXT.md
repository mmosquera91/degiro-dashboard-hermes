# Phase 06: Testing - Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Add automated test coverage for core logic modules. Delivers TEST-01 through TEST-03:
- Tests for `scoring.py` — `compute_scores`, `compute_momentum_score`, `compute_value_score`
- Tests for `market_data.py` — `enrich_position`, `get_fx_rate`, `compute_rsi`
- Tests for `degiro_client.py` — portfolio parsing, position field extraction

</domain>

<decisions>
## Implementation Decisions

### Test File Location

- **D-01:** Tests go in a `tests/` directory at the project root (not inside `app/`). This keeps `app/` clean and mirrors the standard Python project layout.
- **D-02:** `tests/` is excluded from the Docker image via `.dockerignore` — no test code in production.

### Test Framework

- **D-03:** Use **pytest** as the test framework — it's the standard for Python, widely used, and fits naturally with the existing `requirements.txt` pattern.

### Mock Strategy

- **D-04:** Mock external services: **yfinance** calls, **DeGiro API** (degiro-connector), and **FX rate lookups**.
- **D-05:** Mock via `unittest.mock.patch` — no additional mock library needed.
- **D-06:** Tests must be **deterministic** — no reliance on live data or network calls.

### CI Integration

- **D-07:** Tests run via a simple **shell script** (`scripts/run_tests.sh`) that pytest can execute. CI config can call this script.
- **D-08:** No complex CI pipeline needed for v1 — shell script is sufficient. GitHub Actions or similar can be added later.

### Test Structure

- **D-09:** One test module per application module:
  - `tests/test_scoring.py` — tests for `scoring.py`
  - `tests/test_market_data.py` — tests for `market_data.py`
  - `tests/test_degiro_client.py` — tests for `degiro_client.py`
- **D-10:** Each test module covers the public functions listed in the requirements (TEST-01, TEST-02, TEST-03).

### Scoring Tests (TEST-01)

- **D-11:** Test `compute_momentum_score` — verify weighted average calculation (30d 20%, 90d 30%, YTD 50%), None handling, all-None edge case
- **D-12:** Test `compute_value_score` — verify negation of momentum score, None handling
- **D-13:** Test `compute_scores` — verify it mutates positions in-place, adds momentum_score and value_score, handles empty list

### Market Data Tests (TEST-02)

- **D-14:** Test `get_fx_rate` — verify cache hit/miss, currency conversion math, fallback to 1.0 on failure
- **D-15:** Test `enrich_position` — verify it adds expected fields (price, perf_*, sector, etc.), handles missing data gracefully
- **D-16:** Test `compute_rsi` — verify RSI calculation correctness with known input values

### DeGiro Client Tests (TEST-03)

- **D-17:** Test portfolio parsing — verify position dict structure has expected fields (name, ISIN, quantity, price, value, etc.)
- **D-18:** Test position field extraction — verify normalization of raw API response into enriched position format

### Coverage Target

- **D-19:** Focus on **core logic paths** — happy paths, known edge cases, and error handling. Full branch coverage not required for v1.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Context
- `.planning/phases/01-security-hardening/01-CONTEXT.md` — Auth token pattern, env var conventions
- `.planning/phases/02-performance/02-CONTEXT.md` — Threading patterns, FX cache locking
- `.planning/phases/03-health-indicators/03-CONTEXT.md` — Health alerts pattern
- `.planning/phases/04-benchmark-tracking/04-CONTEXT.md` — Snapshot storage, benchmark patterns
- `.planning/phases/05-dashboard-polish/05-CONTEXT.md` — UI integration patterns
- `.planning/ROADMAP.md` §Phase 6 — Phase goal, success criteria, implementation notes
- `.planning/REQUIREMENTS.md` §Testing (TEST) — TEST-01, TEST-02, TEST-03

### Codebase
- `app/scoring.py` — Functions: `compute_momentum_score`, `compute_value_score`, `compute_scores`, `compute_portfolio_weights`, `get_top_candidates`
- `app/market_data.py` — Functions: `get_fx_rate`, `enrich_position`, `enrich_positions`, `compute_rsi`, `_resolve_yf_symbol`, `_compute_performance`
- `app/degiro_client.py` — Functions: `authenticate`, `from_session_id`, `fetch_portfolio`, `_kv_list_to_dict`, `_extract_error_message`
- `.dockerignore` — Excludes `app/test_*.py`; must also exclude `tests/` to keep test code out of production

### Project Context
- `.planning/PROJECT.md` — Single-user architecture, yfinance for market data, no database
- `.planning/STATE.md` — Current phase position, prior decisions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/scoring.py` — Pure functions with clear inputs/outputs, easy to unit test without mocks
- `app/market_data.py` — `get_fx_rate` uses `_fx_cache` dict (easy to seed in tests), `compute_rsi` takes a pandas Series
- `app/degiro_client.py` — `fetch_portfolio` returns a dict with nested position lists; `_kv_list_to_dict` is a simple transform function

### Established Patterns
- `threading.RLock` for thread-safe cache access — tests may need to handle lock contention
- `os.getenv` with defaults for configuration — tests may need to override via monkeypatch
- `unittest.mock.patch` is sufficient for mocking external calls

### Integration Points
- `tests/` directory needs to be created at project root
- `scripts/run_tests.sh` shell script for CI
- `.dockerignore` should exclude `tests/` directory

</code_context>

<specifics>
## Specific Ideas

- No specific references or "I want it like X" moments from discussion — all decisions followed straightforward testing best practices

</specifics>

<deferred>
## Deferred Ideas

None — all TEST requirements are within scope for this phase.

</deferred>

---

*Phase: 06-testing*
*Context gathered: 2026-04-24*