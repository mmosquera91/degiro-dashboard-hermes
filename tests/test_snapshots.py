"""Tests for snapshot save/load functions (SNAP-01, SNAP-02, SNAP-03)."""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

# Patch SNAPSHOT_DIR before importing snapshots module
from app import snapshots


@pytest.fixture
def temp_snapshot_dir(tmp_path):
    """Provide a temporary directory for snapshot files."""
    with patch.object(snapshots, "SNAPSHOT_DIR", str(tmp_path)):
        yield tmp_path


@pytest.fixture
def sample_portfolio():
    """Provide a sample portfolio dict matching the structure from _build_portfolio_summary."""
    return {
        "date": "2026-04-24T10:00:00",
        "total_value": 12345.67,
        "total_invested": 10000.0,
        "total_pl": 2345.67,
        "total_pl_pct": 23.46,
        "etf_allocation_pct": 40.0,
        "stock_allocation_pct": 60.0,
        "num_positions": 5,
        "top_5_winners": [{"name": "Apple", "symbol": "AAPL", "pl_pct": 13.33}],
        "top_5_losers": [{"name": "Tesla", "symbol": "TSLA", "pl_pct": -5.2}],
        "sector_breakdown": {"Technology": 60.0, "Healthcare": 40.0},
        "cash_available": 500.0,
        "daily_change_pct": 1.2,
        "positions": [
            {
                "name": "Apple Inc",
                "symbol": "AAPL",
                "current_value_eur": 5000.0,
                "weight": 40.0,
                "momentum_score": 0.75,
                "buy_priority_score": 0.8,
            }
        ],
        "top_candidates": {"etfs": [], "stocks": []},
    }


class TestSaveSnapshot:
    def test_save_snapshot_with_portfolio_data(self, temp_snapshot_dir, sample_portfolio):
        """SNAP-01: save_snapshot() writes portfolio_data to JSON file."""
        date_str = "2026-04-24"

        snapshots.save_snapshot(
            date_str,
            12345.67,
            105.5,
            5.5,
            sample_portfolio,
        )

        file_path = temp_snapshot_dir / f"{date_str}.json"
        assert file_path.exists(), "Snapshot file was not created"

        with open(file_path) as f:
            data = json.load(f)

        assert data["date"] == date_str
        assert data["total_value_eur"] == 12345.67
        assert data["benchmark_value"] == 105.5
        assert data["benchmark_return_pct"] == 5.5
        assert data["portfolio_data"] == sample_portfolio

    def test_save_snapshot_without_portfolio_data(self, temp_snapshot_dir):
        """SNAP-01: save_snapshot() backward compatible when portfolio_data is None."""
        date_str = "2026-04-24"

        snapshots.save_snapshot(
            date_str,
            12345.67,
            105.5,
            5.5,
        )

        file_path = temp_snapshot_dir / f"{date_str}.json"
        with open(file_path) as f:
            data = json.load(f)

        assert data["portfolio_data"] is None

    def test_atomic_write_pattern(self, temp_snapshot_dir, sample_portfolio):
        """SNAP-03: Snapshot write uses temp file + rename pattern, no .tmp left behind."""
        date_str = "2026-04-24"

        snapshots.save_snapshot(
            date_str,
            12345.67,
            105.5,
            5.5,
            sample_portfolio,
        )

        # No .tmp files should remain
        tmp_files = list(temp_snapshot_dir.glob("*.json.tmp"))
        assert len(tmp_files) == 0, f"Temp files still exist: {tmp_files}"

        # Target file should exist
        target_file = temp_snapshot_dir / f"{date_str}.json"
        assert target_file.exists(), "Target snapshot file does not exist"

        # File content should be valid JSON
        with open(target_file) as f:
            json.load(f)


class TestLoadLatestSnapshot:
    def test_load_latest_snapshot_returns_portfolio(self, temp_snapshot_dir, sample_portfolio):
        """SNAP-02: load_latest_snapshot() returns most recent snapshot with portfolio_data."""
        # Create two snapshot files
        snapshots.save_snapshot("2026-04-22", 10000.0, 100.0, 0.0, {"total_value": 10000})
        snapshots.save_snapshot("2026-04-23", 11000.0, 102.0, 2.0, {"total_value": 11000})
        snapshots.save_snapshot("2026-04-24", 12345.67, 105.5, 5.5, sample_portfolio)

        result = snapshots.load_latest_snapshot()

        assert result is not None
        assert result["date"] == "2026-04-24"
        assert result["portfolio_data"] == sample_portfolio

    def test_load_latest_snapshot_handles_old_format(self, temp_snapshot_dir):
        """SNAP-02: load_latest_snapshot() backward compatible with old snapshots (no portfolio_data key)."""
        # Write an old-format snapshot manually (simulating pre-Phase-7 snapshot)
        old_snapshot = {
            "date": "2026-04-20",
            "total_value_eur": 10000.0,
            "benchmark_value": 100.0,
            "benchmark_return_pct": 0.0,
            # No "portfolio_data" key
        }
        file_path = temp_snapshot_dir / "2026-04-20.json"
        with open(file_path, "w") as f:
            json.dump(old_snapshot, f)

        result = snapshots.load_latest_snapshot()

        assert result is not None
        assert result["date"] == "2026-04-20"
        assert result["portfolio_data"] is None  # Graceful degradation

    def test_load_latest_snapshot_returns_none_when_empty(self, temp_snapshot_dir):
        """SNAP-02: load_latest_snapshot() returns None when no snapshots exist."""
        result = snapshots.load_latest_snapshot()
        assert result is None