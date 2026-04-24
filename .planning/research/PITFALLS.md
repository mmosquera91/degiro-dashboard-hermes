# Pitfalls Research

**Domain:** Portfolio Dashboard — FastAPI + yfinance + vanilla JS + Chart.js
**Researched:** 2026-04-24
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Silent yfinance Failures Cascading to Blank Dashboard Metrics

**What goes wrong:**
Per-stock metrics (RSI, Weight, Momentum, Buy Priority) show "-" in the dashboard when yfinance enrichment fails silently. The scoring pipeline produces `None` values at every step, cascading through: `momentum_score` = None → `value_score` = None → `buy_priority_score` = None → dashboard shows "-".

**Why it happens:**
In `enrich_position()` (`market_data.py`), all yfinance-dependent fields are initialized to `None` at the top. The `ticker.history()` call is wrapped in a bare `try/except Exception` that only logs at WARNING level. If yfinance returns an empty DataFrame or raises an exception, no error is raised to callers — the position just has all-None enrichment fields.

The scoring chain in `scoring.py`:
- `compute_momentum_score()` returns `None` when all perf fields are `None`
- `compute_value_score()` returns `None` when `momentum_score` is `None`
- In `compute_scores()`, positions with `None` value_score silently get 0 in the normalization pool (via `p.get("value_score", 0) or 0`)
- `get_top_candidates()` filters positions where `buy_priority_score is not None` — so if all scoring fails, top_candidates returns empty lists

The result is an API response where `buy_priority_score` is `null` for every position, and the frontend renders "-" for each one.

**Warning signs:**
- Dashboard per-stock section shows all "-" for RSI, Momentum, Buy Priority
- `/api/portfolio` response has positions with `"momentum_score": null` entries
- yfinance enrichment loop logs WARNING "yfinance enrichment failed for SYMBOL" but no error reaches the user
- Benchmark/sector charts missing not because the charts are broken, but because `sector` field is `null` (grouped as "Unknown") and benchmark series returns empty

**How to avoid:**
1. **Explicit error propagation** in `enrich_position`: instead of catching all exceptions silently, return a partial result with an `_enrichment_error` field, and let the caller decide whether to use stale data or fail.
2. **Scoring error boundaries**: In `compute_scores()`, log a WARNING when a position has no valid data to score, and assign a score of `None` explicitly rather than allowing silent None propagation.
3. **Dashboard fallback display**: When `momentum_score` is `None`, display "No data" instead of "-" to signal the user that enrichment failed.
4. **Enrichment status tracking**: Add a `_yfinance_available` boolean per position so the frontend can show "stale" badges.

**Phase to address:**
This is a **data enrichment phase** problem. The fix must be in `enrich_position` and the scoring chain, not in the visualization phase.

---

### Pitfall 2: Snapshot Persistence Without Portfolio Recovery

**What goes wrong:**
`save_snapshot()` in `snapshots.py` only saves `{"date", "total_value_eur", "benchmark_value", "benchmark_return_pct"}` — no positions, no sector data, no benchmark series. After a container restart, `load_snapshots()` returns historical values but the in-memory `_session["portfolio"]` is empty. Calls to `/api/portfolio` return 401 "Session expired" because there is no session and no cached portfolio to serve.

**Why it happens:**
The snapshot was designed purely for benchmark tracking (D-04), not for portfolio state survival. The snapshot-on-fetch flow in `main.py` saves a snapshot every time `/api/portfolio` is called, but the in-memory session cache (`_session`) is lost on restart.

The `/api/portfolio` handler checks `_is_session_valid()` before attempting to fetch from DeGiro. If the session is invalid AND there's no cached portfolio, it raises 401. There's no fallback to load a previous snapshot and serve it as "stale but valid" data.

**Consequences:**
- Container restart clears session — user sees "Session expired" even though their portfolio data from moments ago could still be relevant
- Snapshots accumulate but cannot reconstruct portfolio state
- Benchmark attribution can be computed from snapshots alone, but positions list is always empty in the benchmark response
- The dashboard shows blank rather than showing the last-known portfolio with a "stale" indicator

**How to avoid:**
1. **Store minimal position summary in snapshots**: Include at least `positions_count`, `total_invested`, `etf_allocation_pct`, `stock_allocation_pct` in each snapshot.
2. **Serve stale snapshots on session expiry**: If `_is_portfolio_fresh()` returns True (portfolio data is recent), serve it even if session is expired. Only require session for a true refresh.
3. **Restart recovery logic**: On startup, load the most recent snapshot and pre-populate `_session["portfolio"]` with it so the dashboard shows data immediately.
4. **Snapshot versioning**: Add `_version` field to snapshot schema to allow future schema migration without breaking old snapshots.

**Warning signs:**
- `load_snapshots()` returns populated list but `/api/portfolio` still returns 401
- Logs show "Session expired" but no attempt to load from snapshot
- Container restart immediately shows "Please reconnect" in dashboard

**Phase to address:**
This is a **persistence phase** problem. The fix requires changes to snapshot schema, session recovery logic, and startup behavior.

---

### Pitfall 3: Partial Snapshot Write on Crash

**What goes wrong:**
`save_snapshot()` writes the JSON file directly with no atomicity guarantee. If the process crashes mid-write, the file is truncated or partially written. On restart, `load_snapshots()` may read a corrupted JSON file, log a warning, and skip it — losing that day's data point.

**Why it happens:**
The write pattern is:
```python
with open(file_path, "w") as f:
    json.dump(snapshot, f, indent=2)
```
No rename-after-write pattern. On POSIX systems, `rename()` is atomic; writing directly to the target file is not.

**How to avoid:**
1. **Write-to-temp-then-rename**:
```python
temp_path = Path(SNAPSHOT_DIR) / f".{date_str}.tmp"
with open(temp_path, "w") as f:
    json.dump(snapshot, f)
temp_path.rename(file_path)  # atomic on POSIX
```
2. **Write verification**: After rename, read the file back and verify it loads correctly.
3. **Corruption detection**: The existing `json.JSONDecodeError` catch in `load_snapshots()` handles this but silently skips corrupt files — add a metric counter for monitoring.

**Warning signs:**
- Snapshot files with unusual sizes (e.g., 0 bytes or much smaller than others)
- JSON decode errors in logs for snapshot files
- Missing date entries in the benchmark series chart

**Phase to address:**
This is a **persistence phase** problem. Fix the write pattern in `save_snapshot()`.

---

### Pitfall 4: In-Memory Portfolio Lost While Snapshot Exists

**What goes wrong:**
The session TTL (30 min) and portfolio TTL (5 min) are separate. When the portfolio expires (5 min), `/api/portfolio` will re-fetch and re-save a new snapshot automatically. But the session TTL (30 min) means the DeGiro session could expire before the portfolio — causing a 401 on the next fetch even though fresh snapshot data exists.

**Why it happens:**
`_is_portfolio_fresh()` checks portfolio age. `_is_session_valid()` checks session age. These are independent. After 5 minutes, portfolio is stale. After 30 minutes, session is stale. The code path in `/api/portfolio` tries to fetch if portfolio is stale, but fails with 401 if session is also stale.

If the session expires but the most recent snapshot is only 10 minutes old (still valid), the user sees 401 "Session expired" instead of getting the recent snapshot data.

**How to avoid:**
- Add a condition: if `portfolio` is fresh (less than portfolio TTL), serve it even if session is expired
- Only require active session when refreshing portfolio
- The session TTL protects against DeGiro session expiry, not from serving stale cached data

**Warning signs:**
- User sees 401 after ~30 min but could have served a 10-min-old snapshot
- Logs show "Session expired" followed by "Serving cached portfolio" (if such a log existed — it currently doesn't)

**Phase to address:**
This is a **persistence + session management** problem. The session TTL should not block serving fresh cached portfolio.

---

### Pitfall 5: Scoring Normalization Pool Pollution from None Values

**What goes wrong:**
In `compute_scores()` (`scoring.py`), when normalizing buy_priority_score components for a pool (ETF or STOCK), `value_scores` uses `p.get("value_score", 0) or 0`. If a position has `value_score = None`, it becomes `0` in the list. This means a position with completely missing yfinance data gets the same value_score (0) as a position that genuinely scored 0 on value — the normalization treats them identically.

**Why it happens:**
The `_min_max_normalize()` function replaces None values with the median of non-None values. But the input list comes from `p.get("value_score", 0) or 0`, which explicitly replaces None with 0 before passing to the normalizer. So None values are invisible to the normalizer's median-replacement logic — they appear as 0.

**Consequences:**
- A position with failed yfinance enrichment has `value_score = None` → treated as 0
- It gets the same normalized score as a position that genuinely has 0 value_score
- The buy_priority_score for "data missing" positions is indistinguishable from "genuinely bad value" positions
- A portfolio where most positions have failed yfinance will show all positions with similar low buy_priority_scores rather than clearly signaling "no data"

**How to avoid:**
1. Track positions with missing data separately — exclude them from the normalization pool entirely, or assign them a fixed fallback score.
2. Or: Use a sentinel value (e.g., `-999`) to mark "no data" positions in the normalization input, then replace sentinel with median after normalization.

**Warning signs:**
- All positions in a pool get similar buy_priority_scores even when some have rich data and others have no enrichment
- Top candidates appear evenly distributed rather than having clear leaders

**Phase to address:**
This is a **data enrichment + scoring** problem. The normalization logic needs to handle missing data explicitly.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| yfinance bare `except Exception` swallowing all errors | Code doesn't crash, enrichment continues | Silent failures show as "-" in dashboard, no user feedback | Never — at minimum log ERROR |
| No atomic writes for snapshots | Simple code | Corrupt snapshots on crash, data loss | Never — use rename-after-write |
| No position summary in snapshots | Snapshot stays small | Cannot recover portfolio state on restart | Only if restart recovery is deferred |
| Session TTL independent of portfolio TTL | Simple logic | Stale portfolio still served but session expired blocks it | Never — session expiry should not block serving fresh cache |
| None treated as 0 in scoring normalization | Avoids null check everywhere | Unknown data indistinguishable from genuine zero | Never — use explicit missing-data handling |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| yfinance → scoring chain | Scoring chain has no error boundary — None cascades silently | Add `_enrichment_error` field to position dict, propagate explicitly |
| yfinance → dashboard | Missing yfinance data shows "-" with no indication of staleness | Add `_yfinance_available` flag per position, show "stale" badge in UI |
| DeGiro session → portfolio | Session expiry blocks portfolio fetch even when cache is fresh | Serve fresh cached portfolio regardless of session age |
| Snapshot → restart recovery | Snapshots don't store positions — cannot reconstruct state | Include minimal position summary in snapshots |
| yfinance `ticker.info` | `info` returns empty dict `{}` on failure, not exception — silently skipped | Check `if not info:` and log WARNING |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| yfinance enrichment thread pool blocking | Slow portfolio load when many positions have failed enrichment | Use asyncio.to_thread properly, don't block event loop | All enrichments fail (network issue) |
| Snapshot write on every portfolio fetch | Disk I/O on every /api/portfolio call | Only save snapshot if data has changed meaningfully (e.g., >1% value change) | High-frequency polling |
| Loading all snapshots on every benchmark request | O(n) file I/O where n = number of snapshot days | Cache snapshots in memory with TTL | Long time series (years of daily snapshots) |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| yfinance errors not logged at ERROR level | Silent failures hide systemic data issues | Log ERROR for any yfinance exception in `enrich_position` |
| DeGiro session ID logged in warning messages | Credentials leak via logs | Scrub session IDs from all log messages |
| Snapshot directory not validated | Path traversal if SNAPSHOT_DIR is user-controlled | Validate SNAPSHOT_DIR is a safe absolute path |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| "-" shown for any missing metric | User cannot tell if data is missing, zero, or loading | Show "No data" or "Stale" for missing, "-" only for intentionally zero values |
| Blank sector/benchmark charts with no explanation | User thinks charts are broken | Add inline message: "No sector data available — yfinance enrichment may have failed" |
| Session expiry shows "Please reconnect" with no stale data shown | User loses all visibility | Show last-known portfolio with "Data from X minutes ago — reconnect to refresh" |
| All positions showing identical low buy_priority_scores | User cannot distinguish real candidates | Clearly flag which positions have full data vs. partial data |

---

## "Looks Done But Isn't" Checklist

- [ ] **Snapshot persistence:** Snapshot files exist on disk but contain no positions — restart still shows "Session expired"
- [ ] **Enrichment:** yfinance calls succeed but `ticker.info` returns `{}` silently — sector field stays `None` → sector chart shows single "Unknown" bar
- [ ] **Scoring:** All positions get `None` for `momentum_score` but `buy_priority_score` is still computed (from zero defaults) — top candidates list is meaningless
- [ ] **Benchmark chart:** Snapshot loads but benchmark series fetch fails silently → chart shows empty with no error message
- [ ] **Sector chart:** All positions have `sector = None` (yfinance failed) → chart renders single category "Unknown" with 100%

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Silent yfinance failure | LOW | Add logging, re-enrich positions via explicit API call |
| Snapshot write corruption | MEDIUM | Delete corrupt .json, next fetch will write new valid snapshot |
| Session expiry with fresh snapshot | LOW | Serve snapshot with `stale: true` flag, don't block on session |
| None cascade through scoring | MEDIUM | Fix `enrich_position` error propagation, re-score positions |
| Missing sector data | LOW | Re-enrich positions, sector data is non-critical for core metrics |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Silent yfinance failures showing as "-" | Data enrichment phase — add error propagation and status tracking | Dashboard shows "No data" not "-" for failed positions |
| Snapshot persistence without recovery | Persistence phase — add position summary to snapshots, implement restart recovery | Container restart → dashboard shows last-known portfolio immediately |
| Partial snapshot write corruption | Persistence phase — rename-after-write pattern | Kill process mid-write → on restart, snapshot either saved or not (no corruption) |
| Session expiry blocking fresh portfolio | Session/cache management — serve portfolio regardless of session age | Wait 30 min → dashboard still shows portfolio with "last refreshed X min ago" |
| Scoring normalization polluted by None values | Scoring phase — explicit missing-data handling in normalization | Positions with failed yfinance are clearly distinguishable from those with rich data |
| Sector/benchmark charts blank with no error | Visualization phase — error boundary in chart render | Charts show "No data available" inline message, not empty space |

---

## Sources

- Observed: `market_data.py` — `enrich_position` has bare `except Exception` swallowing all yfinance errors
- Observed: `scoring.py` — `_min_max_normalize` median-replacement logic bypassed by `or 0` default in input
- Observed: `main.py` — `_is_session_valid()` blocks portfolio fetch even when `_is_portfolio_fresh()` returns True
- Observed: `snapshots.py` — `save_snapshot` writes directly without atomic rename
- Observed: `snapshots.py` — snapshot schema has no positions list, only total_value_eur
- Observed: `main.py` — snapshot saved on every portfolio fetch (no delta check)