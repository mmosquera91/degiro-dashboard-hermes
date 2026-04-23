"""Benchmark tracking — snapshot save/load, benchmark fetch, attribution computation."""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import yfinance as yf

from .market_data import _yf_throttle

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = os.getenv("SNAPSHOT_DIR", "/data/snapshots")
BENCHMARK_TICKER = os.getenv("BENCHMARK_TICKER", "^GSPC")


def save_snapshot(
    date_str: str,
    total_value_eur: float,
    benchmark_value: float,
    benchmark_return_pct: float,
) -> None:
    """Save a portfolio snapshot to {SNAPSHOT_DIR}/{date_str}.json.

    Args:
        date_str: Date string in YYYY-MM-DD format.
        total_value_eur: Total portfolio value in EUR.
        benchmark_value: Indexed benchmark value (100 at portfolio start).
        benchmark_return_pct: Benchmark return percentage since portfolio start.
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
    }

    file_path = Path(SNAPSHOT_DIR) / f"{date_str}.json"
    with open(file_path, "w") as f:
        json.dump(snapshot, f, indent=2)

    logger.info("Snapshot saved: %s", file_path)


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
    for file_path in snapshot_dir.glob("*.json"):
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

    _yf_throttle()
    try:
        data = yf.download(ticker, start=start_date, end=end_date, progress=False)
    except Exception as e:
        logger.warning("yfinance benchmark fetch failed: %s", e)
        return []

    if data.empty:
        logger.warning("No benchmark data returned for %s to %s", start_date, end_date)
        return []

    # Get first price for indexing
    first_price = float(data["Close"].iloc[0])

    result = []
    for idx, row in data.iterrows():
        date_str = idx.strftime("%Y-%m-%d")
        price = float(row["Close"])
        indexed_value = (price / first_price) * 100.0
        result.append({"date": date_str, "value": round(indexed_value, 4)})

    return result


def compute_attribution(positions: list[dict], benchmark_return: float) -> list[dict]:
    """Compute attribution for each position relative to benchmark.

    Attribution formula (D-11):
        relative_contribution = (position_return - benchmark_return) * weight * direction
        absolute_contribution = position_return * weight
        direction = 1 if position_return >= 0 else -1
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
        direction = 1 if position_return >= 0 else -1

        relative_contribution = round(
            (position_return - benchmark_return) * weight * direction,
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