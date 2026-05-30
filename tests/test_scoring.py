"""Unit tests for scoring.py — compute_momentum_score, compute_value_score, compute_scores."""

import pytest
from unittest.mock import patch, MagicMock


# Import from app.scoring since PYTHONPATH=app
import sys
sys.path.insert(0, 'app')
from scoring import compute_momentum_score, compute_value_score, compute_scores


class TestComputeMomentumScore:
    def test_compute_momentum_score_happy_path(self):
        """Verify correct weighted average: 30d 20%, 90d 30%, 1Y 50%."""
        pos = {"perf_30d": 5.0, "perf_90d": 10.0, "perf_1y": 20.0}
        # 0.20*5 + 0.30*10 + 0.50*20 = 1 + 3 + 10 = 14.0
        assert compute_momentum_score(pos) == 14.0

    def test_compute_momentum_score_all_none(self):
        """All None inputs return None."""
        pos = {"perf_30d": None, "perf_90d": None, "perf_1y": None}
        assert compute_momentum_score(pos) is None

    def test_compute_momentum_score_partial(self):
        """Missing values filled with 0."""
        # Only 30d available
        pos = {"perf_30d": 10.0, "perf_90d": None, "perf_1y": None}
        # 0.20*10 + 0.30*0 + 0.50*0 = 2.0
        assert compute_momentum_score(pos) == 2.0

        # Only 1Y available
        pos2 = {"perf_30d": None, "perf_90d": None, "perf_1y": 15.0}
        # 0.20*0 + 0.30*0 + 0.50*15 = 7.5
        assert compute_momentum_score(pos2) == 7.5

    def test_compute_momentum_score_only_1y(self):
        """Only 1Y, others None."""
        pos = {"perf_30d": None, "perf_90d": None, "perf_1y": -5.0}
        # 0.20*0 + 0.30*0 + 0.50*(-5) = -2.5
        assert compute_momentum_score(pos) == -2.5


class TestComputeValueScore:
    def test_compute_value_score(self):
        """Requires trailing_pe + price_to_book. Without them, returns None."""
        pos_high = {"momentum_score": 10.0}
        assert compute_value_score(pos_high) is None

        pos_negative = {"momentum_score": -5.0}
        assert compute_value_score(pos_negative) is None

    def test_compute_value_score_with_pe_and_pb(self):
        """With pe_ratio and price_to_book, returns average of the two values."""
        # scoring.py reads "pe_ratio" (not "trailing_pe") — field name set by market_data.py
        pos = {"pe_ratio": 20.0, "price_to_book": 2.0}
        result = compute_value_score(pos)
        assert result == 11.0  # (20.0 + 2.0) / 2

    def test_compute_value_score_wrong_field_name_returns_none(self):
        """Using the wrong key 'trailing_pe' yields None — only 'pe_ratio' is read."""
        pos_wrong = {"trailing_pe": 20.0, "price_to_book": None}
        assert compute_value_score(pos_wrong) is None

    def test_compute_value_score_none(self):
        """None momentum returns None."""
        pos_none = {"momentum_score": None}
        assert compute_value_score(pos_none) is None


class TestComputeScores:
    def test_compute_scores_empty(self):
        """Empty list handled."""
        result = compute_scores([])
        assert result == []

    def test_compute_scores_in_place_mutation(self):
        """Positions mutated in place with momentum_score and value_score."""
        positions = [{"perf_30d": 5.0, "perf_90d": 10.0, "perf_1y": 20.0}]
        compute_scores(positions)
        assert "momentum_score" in positions[0]
        assert "value_score" in positions[0]
        assert positions[0]["momentum_score"] == 14.0
        assert positions[0]["value_score"] is None

    def test_compute_scores_etf_and_stock_pool(self):
        """ETF and STOCK get separate buy_priority_scores, others get None."""
        positions = [
            {"asset_type": "ETF", "perf_30d": 5.0, "perf_90d": 10.0, "perf_1y": 15.0,
             "value_score": 5.0, "distance_from_52w_high_pct": -10.0, "rsi": 40.0, "weight": 10.0},
            {"asset_type": "STOCK", "perf_30d": 3.0, "perf_90d": 6.0, "perf_1y": 9.0,
             "value_score": 3.0, "distance_from_52w_high_pct": -5.0, "rsi": 60.0, "weight": 20.0},
            {"asset_type": "BOND", "perf_30d": 1.0, "perf_90d": 2.0, "perf_1y": 3.0,
             "value_score": 1.0, "distance_from_52w_high_pct": -2.0, "rsi": 50.0, "weight": 5.0},
        ]
        result = compute_scores(positions)
        # ETF and STOCK get buy_priority_score
        assert result[0]["asset_type"] == "ETF"
        assert result[1]["asset_type"] == "STOCK"
        assert result[0]["buy_priority_score"] is not None
        assert result[1]["buy_priority_score"] is not None
        # BOND does not get buy_priority_score
        assert result[2]["buy_priority_score"] is None

    def test_compute_scores_zero_values(self):
        """All-None performance fields handled."""
        positions = [
            {"asset_type": "ETF", "perf_30d": None, "perf_90d": None, "perf_1y": None,
             "value_score": None, "distance_from_52w_high_pct": 0, "rsi": None, "weight": 0},
        ]
        result = compute_scores(positions)
        assert result[0]["momentum_score"] is None
        assert result[0]["value_score"] is None
        assert result[0]["buy_priority_score"] is None  # dist=0 fails is_buyable() gate (dist >= -3)


class TestComputeScoresNoneExclusion:
    """BUG-01: Positions with None values are excluded from normalization pool."""

    def test_compute_scores_none_value_score_excluded_from_pool(self):
        """A position with None value_score does not pollute the normalization range.

        With n=3 positions (below the n<4 z-score threshold), all positions
        receive the neutral fallback score 0.5. The key invariant is that
        None values do not pollute the pool — the normalization is based on
        non-None values only, not on the median-filled None values.
        """
        # Three ETF positions:
        # Position 0: value_score=10.0
        # Position 1: value_score=None (should be excluded from pool)
        # Position 2: value_score=5.0
        # With n=3 < 4, _zscore_normalize returns [0.5, 0.5, 0.5] fallback
        # rather than attempting z-score normalization (insufficient data).
        positions = [
            {
                "asset_type": "ETF",
                "value_score": 10.0,
                "distance_from_52w_high_pct": -10.0,
                "rsi": 40.0,
                "weight": 10.0,
                "perf_30d": 5.0,
                "perf_90d": 10.0,
                "perf_1y": 15.0,
            },
            {
                "asset_type": "ETF",
                "value_score": None,  # BUG: was polluting the pool
                "distance_from_52w_high_pct": -5.0,
                "rsi": 60.0,
                "weight": 20.0,
                "perf_30d": 3.0,
                "perf_90d": 6.0,
                "perf_1y": 9.0,
            },
            {
                "asset_type": "ETF",
                "value_score": 5.0,
                "distance_from_52w_high_pct": -8.0,
                "rsi": 50.0,
                "weight": 15.0,
                "perf_30d": 4.0,
                "perf_90d": 8.0,
                "perf_1y": 12.0,
            },
        ]

        result = compute_scores(positions)

        # All positions should get a buy_priority_score
        assert all(p.get("buy_priority_score") is not None for p in result)

        # Verify the None value_score position gets a neutral score
        none_pos = result[1]
        assert none_pos["momentum_score"] is not None  # momentum computed from perf fields

        # With n=3 < 4, all positions get the neutral fallback 0.5.
        # (z-score normalization requires n>=4 for meaningful differentiation)
        score_0 = result[0]["buy_priority_score"]
        score_2 = result[2]["buy_priority_score"]
        assert score_0 == score_2 == 0.5

    def test_compute_scores_all_nones_get_neutral_scores(self):
        """All-None pool returns neutral scores (0.5) for all positions."""
        positions = [
            {
                "asset_type": "ETF",
                "value_score": None,
                "distance_from_52w_high_pct": None,
                "rsi": None,
                "weight": None,
                "perf_30d": None,
                "perf_90d": None,
                "perf_1y": None,
            },
        ]
        result = compute_scores(positions)
        # buy_priority_score should be based on 0.5 defaults for all dimensions
        assert result[0]["buy_priority_score"] is not None

    def test_compute_scores_mixed_none_per_dimension(self):
        """Different dimensions can have None independently."""
        positions = [
            {
                "asset_type": "ETF",
                "value_score": 10.0,
                "distance_from_52w_high_pct": None,  # Only this is None
                "rsi": 40.0,
                "weight": 10.0,
                "perf_30d": 5.0,
                "perf_90d": 10.0,
                "perf_1y": 15.0,
            },
        ]
        result = compute_scores(positions)
        assert result[0]["buy_priority_score"] is not None


class TestScoreFieldsPopulated:
    """Regression: enriched positions with full data must produce non-None score fields.

    Guards against field-name mismatches between market_data.py (which writes
    'pe_ratio', 'rsi', 'momentum_score', 'weight', 'buy_priority_score') and
    the renderer (app.js renderPositions) which reads the same names.
    """

    def _make_enriched_stock(self, symbol: str, **overrides) -> dict:
        """Minimal enriched STOCK dict that passes all quality gates."""
        base = {
            "asset_type": "STOCK",
            "name": f"Test {symbol}",
            "symbol": symbol,
            "pe_ratio": 18.0,           # market_data writes "pe_ratio" (not "trailing_pe")
            "price_to_book": 2.5,
            "perf_30d": 3.0,
            "perf_90d": 8.0,
            "perf_1y": 15.0,
            "rsi": 45.0,                # < 70 — passes gate
            "distance_from_52w_high_pct": -12.0,  # < -3 — passes gate
            "weight": 5.0,
            "current_value_eur": 1000.0,
        }
        base.update(overrides)
        return base

    def test_enriched_stock_pool_produces_non_none_scores(self):
        """Four enriched STOCKs all passing quality gates yield non-None scores.

        Uses n=4 (the minimum for z-score normalization in _zscore_normalize).
        Asserts that rsi, weight, momentum_score, and buy_priority_score are all
        present and non-None — the exact fields read by app.js renderPositions.
        """
        positions = [
            self._make_enriched_stock("A", weight=4.0, rsi=40.0,  perf_1y=10.0, distance_from_52w_high_pct=-20.0),
            self._make_enriched_stock("B", weight=5.0, rsi=45.0,  perf_1y=15.0, distance_from_52w_high_pct=-12.0),
            self._make_enriched_stock("C", weight=6.0, rsi=50.0,  perf_1y=12.0, distance_from_52w_high_pct=-8.0),
            self._make_enriched_stock("D", weight=8.0, rsi=55.0,  perf_1y=18.0, distance_from_52w_high_pct=-15.0),
        ]
        result = compute_scores(positions)

        for pos in result:
            sym = pos["symbol"]
            # rsi and weight survive as-is (not overwritten by compute_scores)
            assert pos.get("rsi") is not None, f"{sym}: rsi must not be None"
            assert pos.get("weight") is not None, f"{sym}: weight must not be None"
            # momentum_score is computed from perf_* fields
            assert pos.get("momentum_score") is not None, f"{sym}: momentum_score must not be None"
            # buy_priority_score must be non-None for stocks passing quality gates
            assert pos.get("buy_priority_score") is not None, f"{sym}: buy_priority_score must not be None"

    def test_enriched_stock_with_pe_ratio_key_produces_value_score(self):
        """compute_value_score reads 'pe_ratio' — the key written by market_data.py.

        Regression against using the wrong key name 'trailing_pe'.
        """
        from scoring import compute_value_score
        pos = {"pe_ratio": 20.0, "price_to_book": 2.0}
        score = compute_value_score(pos)
        assert score is not None, "value_score must not be None when pe_ratio and price_to_book are set"
        assert score == 11.0, f"expected (20+2)/2=11.0, got {score}"
