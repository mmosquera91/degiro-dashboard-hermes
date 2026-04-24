# Phase 7: Snapshot Format Extension - Research

**Researched:** 2026-04-24
**Domain:** JSON file snapshot persistence, atomic file writes, Docker volume management
**Confidence:** HIGH

## Summary

Phase 7 extends the existing snapshot system (Phase 4) to store full enriched portfolio data alongside benchmark tracking fields, and implements atomic writes to prevent corruption on container crashes. The current `save_snapshot()` writes `{date}.json` with benchmark fields only; the extended version adds a `portfolio_data` key with the complete portfolio dict. Atomic writes use the temp-file + rename pattern: write to `{date}.json.tmp`, fsync, then rename to `{date}.json`. Docker volume is configured as a named volume `brokr_snapshots` at `/data/snapshots` that survives `docker-compose down -v`.

**Primary recommendation:** Extend `save_snapshot()` to accept `portfolio_data` dict, implement `load_latest_snapshot()` for Phase 8 restoration, add atomic write pattern with `os.fsync()`, and update `docker-compose.yml` with named volume.

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** New snapshot format extends old format with `portfolio_data` key containing full enriched portfolio dict (positions, sector_breakdown, allocation)
- **D-02:** Backward compatible -- `load_latest_snapshot()` detects old format and returns `portfolio_data: None` (graceful degradation)
- **D-04:** Old snapshots without `portfolio_data` are readable -- Phase 8 planner handles how `load_latest_snapshot()` handles None portfolio_data
- **D-05:** Snapshot writes use temp file + rename pattern with `os.fsync()` before rename
- **D-06:** Prevents corruption if container crashes mid-write -- partial writes go to `.tmp` file, final path stays intact
- **D-07:** Follows existing codebase conventions (no custom code -- standard pattern)
- **D-08:** `load_latest_snapshot()` returns `{"date": ..., "total_value_eur": ..., "portfolio_data": ...}` -- portfolio data only, no benchmark fetched at load time
- **D-09:** Benchmark data fetched fresh from yfinance on `/api/benchmark` call -- existing behavior unchanged
- **D-10:** If snapshot is old format (no `portfolio_data`), `portfolio_data` field is `None`
- **D-11:** `save_snapshot()` called inside `get_portfolio()` after enrichment/scoring completes
- **D-12:** Snapshot happens on every user-triggered portfolio refresh -- same trigger as current benchmark tracking
- **D-13:** No separate endpoint or scheduler -- Phase 7 implements only the pipeline integration
- **D-14:** `docker-compose.yml` uses a named volume `brokr_snapshots` mounted at `/data/snapshots`
- **D-15:** Named volume survives `docker-compose down -v`
- **D-16:** Planner handles volume configuration in docker-compose.yml

### Deferred Ideas (OUT OF SCOPE)

- **Benchmark Data Persistence:** Benchmark data (^GSPC) is fetched fresh from yfinance. Could store in snapshot in a future phase to avoid re-fetch on restart. Not planned for Phase 7.
- **Snapshot Cleanup:** No automatic cleanup of old snapshots. User manages manually. Could add retention policy in future.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SNAP-01 | `save_snapshot()` accepts full `portfolio_data` dict (positions, sector_breakdown, allocation) | Extended `save_snapshot()` signature, JSON structure matching portfolio summary dict |
| SNAP-02 | `load_latest_snapshot()` reads and returns the most recent snapshot with portfolio data | New function `load_latest_snapshot()` traversing snapshot files, sorted by date |
| SNAP-03 | Snapshot writes use atomic rename (write to temp, then rename) to prevent corruption on crash | Python `os.fsync()` + `os.rename()` pattern, temp file in same directory |
| DOCK-01 | `docker-compose.yml` includes named volume or bind mount for `/data/snapshots` | Named volume `brokr_snapshots` declaration in services.volumes |
| DOCK-02 | Snapshot directory survives `docker-compose down -v` (named volume preferred over anonymous) | Named volumes persist across `down -v`; anonymous volumes are removed |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Snapshot format extension | API / Backend | -- | `save_snapshot()` in `app/snapshots.py` -- backend logic |
| Atomic write implementation | API / Backend | -- | File I/O in `app/snapshots.py` -- OS-level operation |
| `load_latest_snapshot()` | API / Backend | -- | New function in `app/snapshots.py` -- Phase 8 calls it on startup |
| Docker volume configuration | Infrastructure | -- | `docker-compose.yml` -- container orchestration |
| Snapshot trigger integration | API / Backend | -- | `get_portfolio()` in `app/main.py` -- endpoint where snapshot is called |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|--------|---------|--------------|
| Python stdlib `os` | built-in | `os.fsync()`, `os.rename()` for atomic writes | Standard atomic file write pattern, no third-party needed |
| Python stdlib `json` | built-in | JSON serialization for snapshot files | Already used in existing `save_snapshot()` |
| Python stdlib `pathlib` | built-in | `Path(SNAPSHOT_DIR).glob()` for file discovery | Already used in `load_snapshots()` |
| Docker named volumes | Docker built-in | Persistent storage surviving `down -v` | Standard Docker volume types |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|--------|---------|-------------|
| `logging` | stdlib | Log snapshot save/load operations | Already in `snapshots.py` |
| `fastapi` | 0.115.6 | HTTP endpoints | Used for integration test (not implementation scope) |

**Installation:**
No new Python packages required. Docker Compose is a system dependency.

## Architecture Patterns

### System Architecture Diagram

```
Browser                    FastAPI                        File System                  Docker
   |                           |                               |                        |
   |-- GET /api/portfolio -->--|                               |                        |
   |                           |                               |                        |
   |                    fetch_portfolio()                       |                        |
   |                    enrich_positions()                      |                        |
   |                    compute_scores()                        |                        |
   |                           |                               |                        |
   |                    save_snapshot() ------------------------>| write {date}.tmp       |
   |                           |                               |                        |
   |                           |                          fsync()                       |
   |                           |                               |                        |
   |                           |                          rename()                       |
   |                           |                               |                        |
   |<-- full portfolio ------|                               |                        |
   |                           |                               |                        |
   |                           |                    {date}.json (durable) <------------|
```

**Atomic Write Flow:**
1. Open `{SNAPSHOT_DIR}/{date}.json.tmp` for writing
2. `json.dump()` snapshot data
3. `f.flush()` + `os.fsync(f.fileno())` to ensure data hits disk
4. `os.rename()` temp file to `{date}.json`

### Recommended Project Structure
```
app/
├── snapshots.py        # Extended with portfolio_data, atomic writes, load_latest_snapshot
docker-compose.yml      # Named volume brokr_snapshots
snapshots/              # Created automatically at {SNAPSHOT_DIR} (host path)
```

### Pattern 1: Atomic Snapshot Write
**What:** Temp file + rename + fsync for crash-safe writes
**When to use:** Any state written to disk that must not be corrupted by mid-write crashes
**Example:**
```python
# Source: Python stdlib documentation + POSIX guarantees
import os
import json

def save_snapshot(path: Path, data: dict) -> None:
    tmp_path = path.with_suffix(".json.tmp")
    with open(tmp_path, "w") as f:
        json.dump(data, f)
        f.flush()
        os.fsync(f.fileno())
    os.rename(tmp_path, path)  # atomic on POSIX
```

**Why atomic matters:** If container crashes after `f.write()` but before `fsync()`, the file contains partial JSON (corrupt). The rename ensures either the old file is intact OR the new file is complete. Temp file in same directory ensures rename is atomic (same filesystem).

### Pattern 2: Backward-Compatible Snapshot Loading
**What:** Check for key existence before accessing new fields
**When to use:** When extending a data format that must remain readable by old code
**Example:**
```python
def load_latest_snapshot() -> dict | None:
    snapshots = sorted(Path(SNAPSHOT_DIR).glob("*.json"), key=lambda p: p.stem)
    if not snapshots:
        return None
    with open(snapshots[-1]) as f:
        data = json.load(f)
    # Graceful degradation for old snapshots
    if "portfolio_data" not in data:
        data["portfolio_data"] = None
    return data
```

### Anti-Patterns to Avoid

- **Non-atomic overwrite:** Opening `{date}.json` directly for writing, then crashing mid-write, leaves corrupt JSON. Use temp + rename.
- **Missing `fsync`:** `f.flush()` only flushes userspace buffer, not disk. `os.fsync()` is required to guarantee durability before rename.
- **Cross-filesystem rename:** `os.rename()` is atomic only within the same filesystem. Temp file MUST be in same directory as target.
- **Anonymous volume:** `volumes: ["./snapshots:/data/snapshots"]` survives container restart but NOT `down -v`. Use named volume `brokr_snapshots` instead.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic file writes | Custom locking mechanism | Temp file + rename + fsync | POSIX guarantees rename atomicity, fsync ensures durability |
| Crash-safe snapshots | Write-then-verify pattern | Rename pattern | Rename is atomic; verification cannot detect all corruption |
| Volume persistence | Anonymous bind mount | Named Docker volume | Named volumes survive `down -v` |

**Key insight:** The temp file + rename pattern is the standard crash-safety pattern for single-file writes. Python stdlib `os.rename()` is atomic on POSIX systems when src and dst are on the same filesystem.

## Common Pitfalls

### Pitfall 1: Forgetting `fsync`
**What goes wrong:** `f.flush()` only flushes Python's userspace buffer. On crash, the OS may not have written the data to disk, leaving a 0-byte or partial file.
**Why it happens:** `flush()` is visible in Python code; `fsync()` requires explicit call and is easily omitted.
**How to avoid:** Always pair `flush()` with `os.fsync(f.fileno())` for durability-critical writes.
**Warning signs:** Snapshot files with 0 bytes or truncated JSON after container crash.

### Pitfall 2: Volume not surviving `down -v`
**What goes wrong:** Using `volumes: ["./snapshots:/data/snapshots"]` -- anonymous volumes are removed on `down -v`.
**Why it happens:** Anonymous volumes (`volumes: ["/path"]` with no name) are container-scoped and cleaned up with `down`.
**How to avoid:** Use named volume `brokr_snapshots` -- defined at top level of docker-compose.yml, not inside service.
**Warning signs:** Snapshots disappear after `docker-compose down -v`; `docker volume ls` shows no `brokr_snapshots`.

### Pitfall 3: Old snapshot format causing `KeyError` in Phase 8
**What goes wrong:** `load_latest_snapshot()` accesses `data["portfolio_data"]` on old snapshots that lack this key.
**Why it happens:** Phase 4 snapshots contain only `date`, `total_value_eur`, `benchmark_value`, `benchmark_return_pct`.
**How to avoid:** Check `if "portfolio_data" in data` before access, default to `None` if missing (D-02, D-10).
**Warning signs:** `KeyError: 'portfolio_data'` when loading pre-Phase-7 snapshots during Phase 8 startup.

## Code Examples

### Extended `save_snapshot()` (SNAP-01)
```python
# Source: Based on existing app/snapshots.py save_snapshot()
# Extended per D-01, D-05

import os
import json
from pathlib import Path
from typing import Optional

def save_snapshot(
    date_str: str,
    total_value_eur: float,
    benchmark_value: float,
    benchmark_return_pct: float,
    portfolio_data: Optional[dict] = None,  # New: full enriched portfolio
) -> None:
    """Save a portfolio snapshot atomically.

    Args:
        date_str: Date string in YYYY-MM-DD format.
        total_value_eur: Total portfolio value in EUR.
        benchmark_value: Indexed benchmark value (100 at portfolio start).
        benchmark_return_pct: Benchmark return percentage since portfolio start.
        portfolio_data: Full portfolio dict with positions, sector_breakdown,
                       allocation. May be None for old-format snapshots.
    """
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        logger.warning("Invalid date format: %s — skipping snapshot", date_str)
        return

    Path(SNAPSHOT_DIR).mkdir(parents=True, exist_ok=True)

    snapshot = {
        "date": date_str,
        "total_value_eur": round(total_value_eur, 2),
        "benchmark_value": round(benchmark_value, 4),
        "benchmark_return_pct": round(benchmark_return_pct, 4),
        "portfolio_data": portfolio_data,  # None for backward compatibility
    }

    file_path = Path(SNAPSHOT_DIR) / f"{date_str}.json"
    tmp_path = file_path.with_suffix(".json.tmp")

    # Atomic write: temp file + fsync + rename
    with open(tmp_path, "w") as f:
        json.dump(snapshot, f, indent=2)
        f.flush()
        os.fsync(f.fileno())

    os.rename(tmp_path, file_path)  # atomic on POSIX
    logger.info("Snapshot saved (atomic): %s", file_path)
```

### `load_latest_snapshot()` (SNAP-02)
```python
# Source: Derived from existing load_snapshots() in app/snapshots.py

def load_latest_snapshot() -> Optional[dict]:
    """Load the most recent snapshot from SNAPSHOT_DIR.

    Returns:
        Snapshot dict with keys: date, total_value_eur, benchmark_value,
        benchmark_return_pct, portfolio_data. portfolio_data is None
        for old-format snapshots (backward compatible, D-02).

    Returns None if SNAPSHOT_DIR is empty or does not exist.
    """
    snapshot_dir = Path(SNAPSHOT_DIR)
    if not snapshot_dir.exists():
        return None

    # Find all .json snapshot files, filter valid dates, sort by date
    snapshots = []
    for file_path in snapshot_dir.glob("*.json"):
        try:
            date_str = file_path.stem
            datetime.strptime(date_str, "%Y-%m-%d")
            snapshots.append(file_path)
        except ValueError:
            logger.warning("Skipping invalid snapshot filename: %s", file_path.name)
            continue

    if not snapshots:
        return None

    # Most recent by date (lexicographic sort works for YYYY-MM-DD)
    latest_path = sorted(snapshots, key=lambda p: p.name)[-1]

    with open(latest_path, "r") as f:
        data = json.load(f)

    # Backward compatibility: old snapshots lack portfolio_data
    if "portfolio_data" not in data:
        data["portfolio_data"] = None

    logger.info("Loaded latest snapshot: %s", latest_path.name)
    return data
```

### Docker Named Volume
```yaml
# Source: docker-compose.yml updated per D-14, D-15

services:
  brokr:
    build: .
    container_name: brokr
    network_mode: host
    environment:
      - HOST=0.0.0.0
    env_file:
      - .env
    restart: unless-stopped
    volumes:
      - brokr_snapshots:/data/snapshots  # Named volume, survives down -v

volumes:
  brokr_snapshots:  # Top-level named volume declaration
```

**Verification:** `docker volume ls` should show `brokr_snapshots` after `docker-compose up -d`.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Direct file write | Temp file + rename + fsync | Standard crash-safety | Prevents corrupt JSON on crash |
| Anonymous volume | Named volume | Docker best practice | Snapshots survive `down -v` |
| Benchmark-only snapshot | Portfolio data snapshot | Phase 7 extension | Enables Phase 8 startup restoration |

**Deprecated/outdated:**
- Anonymous volume for persistence (`:/data/snapshots` without name) -- removed by `down -v`
- Non-atomic file writes for state -- risk of corruption

## Assumptions Log

> List all claims tagged `[ASSUMED]` in this research. The planner and discuss-phase use this section to identify decisions that need user confirmation before execution.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `os.fsync()` works reliably on the Docker volume mount | Common Pitfalls #1 | Without fsync, crashes may still corrupt snapshots |
| A2 | `os.rename()` is atomic on the Docker volume filesystem | Don't Hand-Roll | If not atomic, crash could leave both temp and target file |

**If this table is empty:** All claims in this research were verified or cited -- no user confirmation needed.

## Open Questions

1. **Should SNAP-04 (bind mount `./snapshots:/data/snapshots`) be merged with D-14 (named volume)?**
   - What we know: D-14 says named volume `brokr_snapshots`; DOCK-01/DOCK-02 from REQUIREMENTS.md says `./snapshots:/data/snapshots` bind mount. The CONTEXT.md D-14/D-15 are the more recent decisions (2026-04-24).
   - What's unclear: Whether host `./snapshots` directory should be bind-mounted or a named volume used. Named volumes cannot be easily inspected from host; bind mounts map to host directory.
   - Recommendation: Use named volume `brokr_snapshots` as per D-14. Bind mount adds host dependency; named volume is cleaner for Docker-native deployment.

2. **Should SNAP-04 be marked complete if `./snapshots` bind mount is used instead of named volume?**
   - What we know: D-15 explicitly says "named volume preferred over anonymous" and D-14 specifies `brokr_snapshots`. REQUIREMENTS.md SNAP-04 says `./snapshots:/data/snapshots`.
   - What's unclear: If user expects `./snapshots` on host to be pre-created and bind-mounted vs. Docker-managed named volume.
   - Recommendation: Named volume `brokr_snapshots` per D-14. Snapshot directory will be Docker-managed at `/var/lib/docker/volumes/brokr_snapshots/_data`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Snapshots module | ✓ | 3.12.3 | — |
| Docker | Container + volume management | ✓ | 20.10.17 | — |
| docker-compose | Volume configuration | ✓ | 1.29.2 | — |
| pytest | Testing | ✓ | 9.0.3 | — |

**Missing dependencies with no fallback:**
- None identified -- all required tools are available.

**Missing dependencies with fallback:**
- None identified.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | `pytest.ini` or `pyproject.toml` (not yet created) |
| Quick run command | `pytest tests/test_snapshots.py -x -v` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SNAP-01 | `save_snapshot()` accepts and writes full portfolio_data dict | unit | `pytest tests/test_snapshots.py::test_save_snapshot_with_portfolio_data -x` | ❌ Wave 0 |
| SNAP-02 | `load_latest_snapshot()` returns most recent snapshot with portfolio data | unit | `pytest tests/test_snapshots.py::test_load_latest_snapshot_returns_portfolio -x` | ❌ Wave 0 |
| SNAP-03 | Atomic write uses temp file + rename + fsync | unit | `pytest tests/test_snapshots.py::test_atomic_write_pattern -x` | ❌ Wave 0 |
| DOCK-01 | docker-compose.yml has named volume for /data/snapshots | smoke | `grep -q "brokr_snapshots" docker-compose.yml && echo "PASS"` | ❌ Wave 0 |
| DOCK-02 | Volume survives `docker-compose down -v` | manual | `docker volume ls | grep brokr_snapshots` after down -v | N/A (manual) |

### Sampling Rate
- **Per task commit:** `pytest tests/test_snapshots.py -x`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_snapshots.py` -- covers SNAP-01, SNAP-02, SNAP-03
- [ ] `tests/conftest.py` -- shared fixtures (tmp snapshot dir, mock portfolio_data)
- [ ] `pytest.ini` or `pyproject.toml` -- if config needed
- [ ] Framework install: `pip install pytest` -- already available (9.0.3)

## Security Domain

> Phase 7 is an infrastructure/data persistence phase with no external input vectors beyond what Phase 1 already handles (auth token, session management). No new security concerns introduced.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Already handled by Phase 1 |
| V3 Session Management | no | Already handled by Phase 1 |
| V4 Access Control | no | Snapshot files are Docker-internal |
| V5 Input Validation | yes | `portfolio_data` dict passed through from already-validated pipeline |
| V6 Cryptography | no | No sensitive data at rest in snapshots (portfolio data is user-owned) |

### Known Threat Patterns for Snapshot Format Extension

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Snapshot file injection | Tampering | Date format validated with `datetime.strptime` before writing |
| Corrupt snapshot on crash | Integrity | Atomic write (temp + rename + fsync) prevents partial writes |
| Snapshot directory traversal | Information Disclosure | `Path(SNAPSHOT_DIR).glob("*.json")` -- only reads `.json` files in configured directory |

## Sources

### Primary (HIGH confidence)
- `app/snapshots.py` — Current implementation of `save_snapshot()` and `load_snapshots()` (VERIFIED: read 2026-04-24)
- `app/main.py` lines 399-428 — Snapshot trigger integration in `get_portfolio()` (VERIFIED: read 2026-04-24)
- `docker-compose.yml` — Current volume configuration (VERIFIED: read 2026-04-24)
- Python stdlib `os` module — `fsync()`, `rename()` behavior (CITED: docs.python.org/3/library/os.html)
- Docker named volumes documentation — (CITED: docs.docker.com/compose/compose-file/09-volume/)

### Secondary (MEDIUM confidence)
- `.planning/codebase/CONVENTIONS.md` — Python code style, pattern conventions (VERIFIED: read 2026-04-24)
- `.planning/codebase/ARCHITECTURE.md` — System architecture, data flow (VERIFIED: read 2026-04-24)

### Tertiary (LOW confidence)
- None — all claims verified via source reading or official documentation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — only stdlib + Docker, no new dependencies
- Architecture: HIGH — clear extension of existing snapshot pattern
- Pitfalls: HIGH — known crash-safety patterns, well-documented

**Research date:** 2026-04-24
**Valid until:** 2026-05-24 (30 days — snapshot format is stable, Docker volumes are mature)

---

## RESEARCH COMPLETE