"""Benchmark tracking — snapshot save/load, benchmark fetch, attribution computation."""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yfinance as yf

from .market_data import _yf_throttle

logger = logging.getLogger(__name__)

def _resolve_snapshot_dir() -> str:
    """Resolve SNAPSHOT_DIR with fallback to workspace-relative path.

    Priority:
    1. SNAPSHOT_DIR env var if set and path exists
    2. /data/snapshots if it exists (Docker volume mount)
    3. ./snapshots relative to working directory (workspace fallback)
    """
    env_val = os.getenv("SNAPSHOT_DIR")
    if env_val:
        return env_val
    if Path("/data/snapshots").exists():
        return "/data/snapshots"
    return "./snapshots"


SNAPSHOT_DIR = _resolve_snapshot_dir()
BENCHMARK_TICKER = os.getenv("BENCHMARK_TICKER", "^GSPC")
SNAPSHOT_RETENTION_DAYS = int(os.getenv("SNAPSHOT_RETENTION_DAYS", "365"))


def save_snapshot(
    date_str: str,
    total_value_eur: float,
    benchmark_value: float,
    benchmark_return_pct: float,
    portfolio_data: Optional[dict] = None,
) -> None:
    """Save a portfolio snapshot to {SNAPSHOT_DIR}/{date_str}.json.

    SNAPSHOT_DIR is resolved dynamically: SNAPSHOT_DIR env var if set,
    then /data/snapshots if it exists, else ./snapshots (workspace-relative).

    Args:
        date_str: Date string in YYYY-MM-DD format.
        total_value_eur: Total portfolio value in EUR.
        benchmark_value: Indexed benchmark value (100 at portfolio start).
        benchmark_return_pct: Benchmark return percentage since portfolio start.
        portfolio_data: Optional full portfolio data dict for restoration.
    """
    # Validate date format before constructing file path (T-04-01)
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        logger.warning("Invalid date format: %s — skipping snapshot", date_str)
        return

    # Create directory if missing
    Path(SNAPSHOT_DIR).mkdir(parents=True, exist_ok=True)

    snapshot = {
        "date": date_str,
        "total_value_eur": round(total_value_eur, 2),
        "benchmark_value": round(benchmark_value, 4),
        "benchmark_return_pct": round(benchmark_return_pct, 4),
        "portfolio_data": portfolio_data,
    }

    file_path = Path(SNAPSHOT_DIR) / f"{date_str}.json"
    tmp_path = file_path.with_suffix(".json.tmp")
    with open(tmp_path, "w") as f:
        json.dump(snapshot, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.rename(tmp_path, file_path)
    logger.info("Snapshot saved (atomic): %s", file_path)
    _prune_old_snapshots()


def _prune_old_snapshots() -> None:
    """Delete snapshots older than SNAPSHOT_RETENTION_DAYS. Keeps the
    most recent snapshot regardless of age (safety net for startup restore)."""
    if SNAPSHOT_RETENTION_DAYS <= 0:
        return  # 0 = disabled
    snapshot_dir = Path(SNAPSHOT_DIR)
    cutoff = datetime.now().date()
    from datetime import timedelta
    cutoff -= timedelta(days=SNAPSHOT_RETENTION_DAYS)

    all_files = sorted(snapshot_dir.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].json"))
    if len(all_files) <= 1:
        return  # always keep at least one

    for file_path in all_files[:-1]:  # never delete the newest
        try:
            date_str = file_path.stem
            file_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if file_date < cutoff:
                file_path.unlink()
                logger.info("Pruned old snapshot: %s", file_path.name)
        except Exception as e:
            logger.warning("Could not prune snapshot %s: %s", file_path.name, e)


def load_snapshots() -> list[dict]:
    """Load all snapshots from SNAPSHOT_DIR, sorted by date ascending.

    Returns:
        List of snapshot dicts, each with keys: date, total_value_eur,
        benchmark_value, benchmark_return_pct.

    Returns an empty list if SNAPSHOT_DIR does not exist.
    """
    snapshot_dir = Path(SNAPSHOT_DIR)
    if not snapshot_dir.exists():
        return []

    snapshots = []
    for file_path in snapshot_dir.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].json"):
        try:
            # Validate date in filename before parsing (T-04-01)
            date_str = file_path.stem
            datetime.strptime(date_str, "%Y-%m-%d")

            with open(file_path, "r") as f:
                snapshot = json.load(f)
            snapshots.append(snapshot)
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning("Skipping invalid snapshot file %s: %s", file_path, e)
            continue

    return sorted(snapshots, key=lambda s: s["date"])


def load_latest_snapshot() -> Optional[dict]:
    """Load the most recent snapshot from SNAPSHOT_DIR.

    Returns:
        Snapshot dict with keys: date, total_value_eur, benchmark_value,
        benchmark_return_pct, portfolio_data. portfolio_data is None
        for old-format snapshots (backward compatible).

    Returns None if SNAPSHOT_DIR is empty or does not exist.
    """
    snapshot_dir = Path(SNAPSHOT_DIR)
    # Ensure directory exists on first startup (gap: ./snapshots not created automatically)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    snapshots = []
    for file_path in snapshot_dir.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].json"):
        try:
            date_str = file_path.stem
            datetime.strptime(date_str, "%Y-%m-%d")
            snapshots.append(file_path)
        except ValueError:
            logger.warning("Skipping invalid snapshot filename: %s", file_path.name)
            continue

    if not snapshots:
        return None

    latest_path = sorted(snapshots, key=lambda p: p.name)[-1]
    with open(latest_path, "r") as f:
        data = json.load(f)

    # Backward compatibility: old snapshots lack portfolio_data
    if "portfolio_data" not in data:
        data["portfolio_data"] = None

    logger.info("Loaded latest snapshot: %s", latest_path.name)
    return data


def fetch_benchmark_series(start_date: str, end_date: str) -> list[dict]:
    """Fetch benchmark price series from yfinance, indexed to 100 at start_date.

    Args:
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.

    Returns:
        List of {"date": "YYYY-MM-DD", "value": float} where value is indexed
        to 100 at start_date.

    Benchmark data is NOT stored — fetched fresh each call (D-07).
    """
    ticker = BENCHMARK_TICKER

    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        logger.warning("Invalid date format: %s or %s", start_date, end_date)
        return []

    if start_dt >= end_dt:
        logger.warning("start_date %s must be before end_date %s", start_date, end_date)
        return []

    # Ensure end_date is exclusive-inclusive: add 1 day so today's data is included
    end_dt_padded = end_dt + timedelta(days=1)

    # If range is less than 7 days, pad start back to ensure trading days are covered
    if (end_dt - start_dt).days < 7:
        start_dt_padded = end_dt - timedelta(days=7)
        logger.info(
            "Benchmark range too narrow (%s to %s) — padding start to %s",
            start_date, end_date, start_dt_padded.strftime("%Y-%m-%d")
        )
    else:
        start_dt_padded = start_dt

    fetch_start = start_dt_padded.strftime("%Y-%m-%d")
    fetch_end = end_dt_padded.strftime("%Y-%m-%d")

    _yf_throttle()
    try:
        data = yf.download(ticker, start=fetch_start, end=fetch_end, progress=False, timeout=10)
    except Exception as e:
        e_str = str(e).lower()
        if "timezone" in e_str or "delisted" in e_str or \
           "429" in e_str or "too many" in e_str or \
           "expecting value" in e_str:
            logger.warning(
                "Benchmark fetch skipped (rate-limited or tz error): %s", e
            )
            return []
        raise

    if data.empty:
        logger.warning("No benchmark data returned for %s to %s", start_date, end_date)
        return []

    # Get first price for indexing
    first_price = float(data["Close"].iloc[0].iloc[0]) if hasattr(data["Close"].iloc[0], 'iloc') else float(data["Close"].iloc[0])

    result = []
    for idx, row in data.iterrows():
        date_str = idx.strftime("%Y-%m-%d")
        if date_str < fetch_start:
            continue  # exclude only days before the padded fetch window
        price = float(row["Close"].iloc[0]) if hasattr(row["Close"], 'iloc') else float(row["Close"])
        indexed_value = (price / first_price) * 100.0
        result.append({"date": date_str, "value": round(indexed_value, 4)})

    return result


def compute_attribution(positions: list[dict], benchmark_return: float) -> list[dict]:
    """Compute attribution for each position relative to benchmark.

    Attribution formula (D-11):
        relative_contribution = (position_return - benchmark_return) * weight
        absolute_contribution = position_return * weight
        weight = position weight as decimal (e.g., 0.20 for 20%)

    Args:
        positions: List of position dicts with weight and perf_ytd fields.
        benchmark_return: Benchmark return percentage for the period.

    Returns:
        List of dicts sorted by absolute_contribution descending.
        Each dict: name, symbol, relative_contribution, absolute_contribution.
    """
    if not positions:
        return []

    attribution = []
    for pos in positions:
        position_return = pos.get("perf_ytd") if pos.get("perf_ytd") is not None else 0.0
        weight = (pos.get("weight") or 0.0) / 100.0
        relative_contribution = round(
            (position_return - benchmark_return) * weight,
            4,
        )
        absolute_contribution = round(position_return * weight, 4)

        attribution.append({
            "name": pos.get("name", ""),
            "symbol": pos.get("symbol", ""),
            "relative_contribution": relative_contribution,
            "absolute_contribution": absolute_contribution,
        })

    return sorted(attribution, key=lambda x: x["absolute_contribution"], reverse=True)