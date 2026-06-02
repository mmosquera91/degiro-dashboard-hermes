"""Unit tests for scoring.py — compute_momentum_score, compute_value_score, compute_scores."""

import pytest
from unittest.mock import patch, MagicMock


# Import from app.scoring since PYTHONPATH=app
import sys
sys.path.insert(0, 'app')
from scoring import compute_momentum_score, compute_value_score, compute_scores, is_buyable


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
        """ETF and STOCK pools are scored separately; BONDs and others always get None.

        Changed (Issue #3): pools need 4+ positions for a rankable buy_priority_score.
        Test now uses 4 ETFs + 4 STOCKs to keep testing the "separate pools" invariant
        while satisfying the minimum-pool-size requirement.
        """
        def _etf(w, rsi, dist):
            return {"asset_type": "ETF", "perf_30d": 5.0, "perf_90d": 10.0, "perf_1y": 15.0,
                    "distance_from_52w_high_pct": dist, "rsi": rsi, "weight": w}

        def _stock(w, rsi, dist):
            return {"asset_type": "STOCK", "perf_30d": 3.0, "perf_90d": 6.0, "perf_1y": 9.0,
                    "distance_from_52w_high_pct": dist, "rsi": rsi, "weight": w}

        positions = [
            _etf(10.0, 40.0, -10.0), _etf(12.0, 42.0, -12.0),
            _etf(14.0, 44.0, -14.0), _etf(16.0, 46.0, -16.0),
            _stock(20.0, 55.0, -5.0), _stock(22.0, 57.0, -7.0),
            _stock(24.0, 59.0, -9.0), _stock(26.0, 61.0, -11.0),
            {"asset_type": "BOND", "perf_30d": 1.0, "perf_90d": 2.0, "perf_1y": 3.0,
             "distance_from_52w_high_pct": -2.0, "rsi": 50.0, "weight": 5.0},
        ]
        result = compute_scores(positions)
        etf_results = [p for p in result if p.get("asset_type") == "ETF"]
        stock_results = [p for p in result if p.get("asset_type") == "STOCK"]
        bond_results = [p for p in result if p.get("asset_type") == "BOND"]
        # 4-ETF pool and 4-STOCK pool: each position gets a non-None buy_priority_score
        assert all(p["buy_priority_score"] is not None for p in etf_results), "ETFs should be ranked"
        assert all(p["buy_priority_score"] is not None for p in stock_results), "STOCKs should be ranked"
        # BOND does not belong to either pool — always None
        assert bond_results[0]["buy_priority_score"] is None

    def test_compute_scores_zero_values(self):
        """All-None performance fields handled; single-ETF pool is unrankable.

        Changed (Issue #2 + #3): ETFs no longer fail the dist gate (ETF exemption),
        but a pool of n=1 is unrankable under Issue #3 — so buy_priority_score is
        still None, now for the pool-size reason rather than a gate reason.
        """
        positions = [
            {"asset_type": "ETF", "perf_30d": None, "perf_90d": None, "perf_1y": None,
             "value_score": None, "distance_from_52w_high_pct": 0, "rsi": None, "weight": 0},
        ]
        result = compute_scores(positions)
        assert result[0]["momentum_score"] is None
        assert result[0]["value_score"] is None
        # buy_priority_score is None because pool size is 1 < 4 (unrankable), not due to a gate
        assert result[0]["buy_priority_score"] is None


class TestValueFactorDirection:
    """The value factor must reward CHEAP positions (lower P/E and P/B = higher buy priority).

    Regression against the inverted-direction bug where value was z-scored without
    negation, making expensive positions score higher. Also pins that P/E and P/B
    are normalized on independent scales, then averaged.
    """

    def _stock(self, symbol, **overrides):
        """A buyable STOCK with all non-value factors held constant across the pool.

        Identical rsi/distance/weight/perf means those factors collapse to the
        neutral 0.5 (std=0), so buy_priority_score differences come ONLY from value.
        """
        base = {
            "asset_type": "STOCK",
            "symbol": symbol,
            "rsi": 45.0,
            "distance_from_52w_high_pct": -12.0,
            "weight": 5.0,
            "perf_30d": 3.0,
            "perf_90d": 8.0,
            "perf_1y": 15.0,
        }
        base.update(overrides)
        return base

    def test_lower_pe_scores_higher(self):
        """All else equal, the cheapest P/E gets the highest buy_priority_score."""
        positions = [
            self._stock("CHEAP", pe_ratio=8.0),
            self._stock("MID1", pe_ratio=18.0),
            self._stock("MID2", pe_ratio=28.0),
            self._stock("RICH", pe_ratio=40.0),
        ]
        result = compute_scores(positions)
        by_sym = {p["symbol"]: p["buy_priority_score"] for p in result}
        assert by_sym["CHEAP"] > by_sym["MID1"] > by_sym["MID2"] > by_sym["RICH"]

    def test_lower_pb_scores_higher(self):
        """All else equal, the cheapest P/B gets the highest buy_priority_score."""
        positions = [
            self._stock("CHEAP", price_to_book=0.8),
            self._stock("MID1", price_to_book=2.0),
            self._stock("MID2", price_to_book=4.0),
            self._stock("RICH", price_to_book=9.0),
        ]
        result = compute_scores(positions)
        by_sym = {p["symbol"]: p["buy_priority_score"] for p in result}
        assert by_sym["CHEAP"] > by_sym["MID1"] > by_sym["MID2"] > by_sym["RICH"]

    def test_missing_metric_falls_back_to_present_one(self):
        """A position with only P/E (no P/B) is scored on its P/E alone — a missing
        metric is excluded from the average, NOT treated as a neutral 0.5.

        This pins the independent-metric combine logic: P/E and P/B are normalized
        separately, and the value factor averages whichever metrics are present.
        """
        positions = [
            self._stock("CHEAP_PE", pe_ratio=8.0),    # no P/B → scored on P/E alone
            self._stock("RICH_PE", pe_ratio=40.0),    # no P/B → scored on P/E alone
            self._stock("MID1", pe_ratio=20.0, price_to_book=2.0),
            self._stock("MID2", pe_ratio=22.0, price_to_book=2.0),
        ]
        result = compute_scores(positions)
        by_sym = {p["symbol"]: p["buy_priority_score"] for p in result}
        # Cheap-on-P/E beats rich-on-P/E even though both lack P/B — the absent
        # metric did not flatten them toward each other at 0.5.
        assert by_sym["CHEAP_PE"] > by_sym["RICH_PE"]


class TestComputeScoresNoneExclusion:
    """BUG-01: Positions with None values are excluded from normalization pool."""

    def test_compute_scores_none_value_score_excluded_from_pool(self):
        """A position with None pe_ratio/price_to_book does not pollute the value factor.

        Changed (Issue #3): the original test used n=3, which is below the minimum
        pool size for ranking. To meaningfully test the None-exclusion invariant, we
        need n>=4 (so z-score normalization runs). The invariant being guarded:
        positions whose value metrics are None get a neutral 0.5 for the value factor
        (treated as the median of the non-None positions), not a corrupted score.

        With n=4 ETFs where one has no pe_ratio/price_to_book (None value factor):
        - all get non-None buy_priority_score (pool is large enough to rank)
        - the None-value position gets a score, not an error
        """
        # Four ETF positions, one with no value metrics (None pe_ratio/price_to_book).
        # All non-value factors are varied to produce differentiated scores.
        positions = [
            {
                "asset_type": "ETF",
                "pe_ratio": 10.0, "price_to_book": 1.0,  # cheap
                "distance_from_52w_high_pct": -20.0,
                "rsi": 35.0,
                "weight": 5.0,
                "perf_30d": 5.0, "perf_90d": 10.0, "perf_1y": 18.0,
            },
            {
                "asset_type": "ETF",
                "pe_ratio": None, "price_to_book": None,  # no value metrics — was polluting pool
                "distance_from_52w_high_pct": -5.0,
                "rsi": 60.0,
                "weight": 20.0,
                "perf_30d": 3.0, "perf_90d": 6.0, "perf_1y": 9.0,
            },
            {
                "asset_type": "ETF",
                "pe_ratio": 20.0, "price_to_book": 2.0,
                "distance_from_52w_high_pct": -8.0,
                "rsi": 50.0,
                "weight": 15.0,
                "perf_30d": 4.0, "perf_90d": 8.0, "perf_1y": 12.0,
            },
            {
                "asset_type": "ETF",
                "pe_ratio": 30.0, "price_to_book": 4.0,  # expensive
                "distance_from_52w_high_pct": -4.0,
                "rsi": 65.0,
                "weight": 25.0,
                "perf_30d": 2.0, "perf_90d": 4.0, "perf_1y": 7.0,
            },
        ]

        result = compute_scores(positions)

        # All 4 positions get a buy_priority_score (pool >= 4, all ETFs are buyable)
        # Changed: original test asserted score=0.5 for n=3 pool; now n=4 yields real scores
        assert all(p.get("buy_priority_score") is not None for p in result), (
            "4-ETF pool: all positions should be ranked with non-None buy_priority_score"
        )

        # Verify the None-value position gets a momentum score (per-position calculation unaffected)
        none_pos = result[1]
        assert none_pos["momentum_score"] is not None  # momentum computed from perf fields

        # The None-exclusion invariant: a position without value metrics still gets ranked
        # (it falls back to 0.5 for the value factor internally), and crucially the
        # cheap-value position outscores the expensive-value position — confirming None
        # did not corrupt the value factor direction for the pool.
        score_cheap = result[0]["buy_priority_score"]
        score_expensive = result[3]["buy_priority_score"]
        assert score_cheap > score_expensive, (
            "Cheap-value ETF should outscore expensive-value ETF even with a None-value peer"
        )

    def test_compute_scores_all_nones_get_neutral_scores(self):
        """All-None single-ETF pool is unrankable (pool < 4) — score is None with note.

        Changed (Issue #3): the original intent was "an all-None pool doesn't crash
        and produces a non-None score". Under the pool-size rule, a pool of n=1 is
        unrankable — the score is None with a note, not a fabricated 0.5.
        The non-crash invariant is still tested (no exception is raised).
        """
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
        # Changed: n=1 pool is unrankable, so buy_priority_score is None with a note
        # (previously this returned a non-None 0.5 from the n<4 fallback)
        assert result[0]["buy_priority_score"] is None
        note = result[0].get("buy_priority_note", "")
        assert "insufficient pool" in (note or "").lower(), (
            f"Expected 'insufficient pool' in note, got: {note!r}"
        )

    def test_compute_scores_mixed_none_per_dimension(self):
        """Different dimensions can have None independently in a rankable pool (n>=4).

        Changed (Issue #3): original test used n=1 (unrankable). Bumped to n=4 to
        test the actual invariant — that a None in one dimension (distance) does not
        prevent ranking or crash the scoring logic. Positions with None in one factor
        get the pool median (0.5 fallback) for that factor only; other factors score normally.
        """
        def _etf(dist, rsi, weight, perf_1y):
            return {
                "asset_type": "ETF",
                "distance_from_52w_high_pct": dist,
                "rsi": rsi,
                "weight": weight,
                "perf_30d": 2.0, "perf_90d": 5.0, "perf_1y": perf_1y,
            }

        positions = [
            {**_etf(-10.0, 40.0, 10.0, 15.0), "distance_from_52w_high_pct": None},  # None dist
            _etf(-5.0, 50.0, 15.0, 12.0),
            _etf(-8.0, 45.0, 12.0, 10.0),
            _etf(-12.0, 55.0, 8.0, 18.0),
        ]
        result = compute_scores(positions)
        # All 4 positions should be ranked — a None in one dimension doesn't block ranking
        assert all(p["buy_priority_score"] is not None for p in result), (
            "4-ETF pool: positions with None in one dimension should still be ranked"
        )


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


# ===========================================================================
# Issue #2 — ETFs must not be gated out by market-timing rules
# ===========================================================================

class TestIsBuyableETFExemption:
    """ETFs are always buyable; the three entry gates apply only to STOCKs.

    Context: this is a 70% ETF / 30% STOCK buy-and-hold DCA portfolio.
    Market-timing the index core (RSI, distance from 52w high) is
    counterproductive — you keep buying the core regardless of highs.
    """

    def test_etf_at_52w_high_and_overbought_rsi_is_still_buyable(self):
        """An ETF with RSI=85 and distance=0.0 (at 52w high) must be buyable.

        Both values would fail the stock entry gates, but ETFs are exempt.
        Contract: is_buyable returns (True, None) for any ETF.
        """
        etf = {
            "asset_type": "ETF",
            "rsi": 85.0,                    # fails RSI < 70 gate
            "distance_from_52w_high_pct": 0.0,  # fails dist < -3 gate
            "momentum_score": 10.0,         # passes momentum gate
        }
        buyable, reason = is_buyable(etf)
        assert buyable is True, f"ETF should always be buyable, got buyable={buyable}, reason={reason}"
        assert reason is None, f"ETF buyable reason should be None, got: {reason}"

    def test_stock_with_same_values_is_not_buyable(self):
        """A STOCK with RSI=85 (>=70) is gated — confirms ETF exemption is ETF-only."""
        stock = {
            "asset_type": "STOCK",
            "rsi": 85.0,
            "distance_from_52w_high_pct": 0.0,
            "momentum_score": 10.0,
        }
        buyable, reason = is_buyable(stock)
        assert buyable is False, "STOCK with RSI=85 must fail the RSI gate"
        assert reason is not None, "STOCK gate failure must include a reason string"

    def test_etf_near_high_gets_non_none_buy_priority_in_large_pool(self):
        """ETFs near 52w highs still get non-None buy_priority_score in a 4-ETF pool.

        Guards the end-to-end path: ETF passes is_buyable (#2 fix), pool is large
        enough (#3 rule), so buy_priority_score is computed and non-None — meaning
        it appears in get_top_candidates as the rebalancer expects.
        """
        from scoring import get_top_candidates

        def _etf_near_high(symbol, weight):
            return {
                "asset_type": "ETF",
                "symbol": symbol,
                "name": f"ETF {symbol}",
                "rsi": 78.0,                    # would fail stock RSI gate
                "distance_from_52w_high_pct": -1.0,  # would fail stock dist gate
                "perf_30d": 2.0,
                "perf_90d": 5.0,
                "perf_1y": 12.0,
                "weight": weight,
            }

        positions = [
            _etf_near_high("IWDA", 30.0),
            _etf_near_high("EIMI", 20.0),
            _etf_near_high("IUSN", 15.0),
            _etf_near_high("VWCE", 10.0),
        ]
        result = compute_scores(positions)
        for pos in result:
            assert pos["buy_priority_score"] is not None, (
                f"{pos['symbol']}: ETF near 52w high should have non-None buy_priority_score "
                f"after #2 exemption fix"
            )

        # Also verify they surface in get_top_candidates
        candidates = get_top_candidates(result, n=3)
        assert len(candidates["etfs"]) == 3, (
            f"Expected 3 ETF candidates, got {len(candidates['etfs'])}"
        )


# ===========================================================================
# Issue #3 — small pools must be labeled unrankable, not given a fake 0.5
# ===========================================================================

class TestSmallPoolUnrankable:
    """Pools with fewer than 4 positions cannot be z-score ranked meaningfully.

    The old behavior returned 0.5 (fabricated neutral). The new contract:
    buy_priority_score = None and buy_priority_note contains "insufficient pool".
    momentum_score and value_score are still computed (per-position, not pool-relative).
    """

    def _etf(self, symbol, weight=10.0, rsi=40.0, dist=-10.0):
        """Buyable ETF helper — all pass the (now ETF-exempt) gates."""
        return {
            "asset_type": "ETF",
            "symbol": symbol,
            "rsi": rsi,
            "distance_from_52w_high_pct": dist,
            "perf_30d": 3.0,
            "perf_90d": 7.0,
            "perf_1y": 12.0,
            "weight": weight,
        }

    def test_three_etf_pool_is_unrankable(self):
        """A pool of exactly 3 buyable ETFs must get buy_priority_score=None with note.

        Old behavior: score=0.5 (fake neutral). New contract: score=None + note,
        since z-score ranking on 3 positions is not meaningful.
        """
        positions = [
            self._etf("IWDA", weight=30.0),
            self._etf("EIMI", weight=20.0),
            self._etf("IUSN", weight=15.0),
        ]
        result = compute_scores(positions)
        for pos in result:
            assert pos["buy_priority_score"] is None, (
                f"{pos['symbol']}: 3-ETF pool should have buy_priority_score=None "
                f"(got {pos['buy_priority_score']}), not the old fake 0.5"
            )
            note = pos.get("buy_priority_note", "")
            assert "insufficient pool" in (note or "").lower(), (
                f"{pos['symbol']}: expected 'insufficient pool' in buy_priority_note, "
                f"got: {note!r}"
            )

    def test_four_etf_pool_is_rankable_with_differentiated_scores(self):
        """A pool of 4 ETFs produces differentiated non-None scores.

        Guards against over-applying the unrankable rule to pools that are large enough.
        """
        positions = [
            self._etf("IWDA", weight=30.0, rsi=35.0, dist=-20.0),
            self._etf("EIMI", weight=20.0, rsi=45.0, dist=-10.0),
            self._etf("IUSN", weight=15.0, rsi=55.0, dist=-5.0),
            self._etf("VWCE", weight=10.0, rsi=65.0, dist=-4.0),
        ]
        result = compute_scores(positions)
        scores = [pos["buy_priority_score"] for pos in result]
        assert all(s is not None for s in scores), (
            f"4-ETF pool: all scores should be non-None, got {scores}"
        )
        # Scores must differ — not all collapsed to the same value
        assert len(set(scores)) > 1, (
            f"4-ETF pool: scores must be differentiated, got {scores}"
        )

    def test_momentum_and_value_still_computed_for_small_pool(self):
        """Per-position scores (momentum, value) are computed even for small pools.

        The unrankable rule affects buy_priority_score only — not independent
        per-position calculations.
        """
        positions = [
            {
                "asset_type": "ETF",
                "symbol": "IWDA",
                "rsi": 40.0,
                "distance_from_52w_high_pct": -10.0,
                "perf_30d": 3.0,
                "perf_90d": 7.0,
                "perf_1y": 12.0,
                "weight": 30.0,
            },
            {
                "asset_type": "ETF",
                "symbol": "EIMI",
                "rsi": 50.0,
                "distance_from_52w_high_pct": -5.0,
                "perf_30d": 2.0,
                "perf_90d": 5.0,
                "perf_1y": 10.0,
                "weight": 20.0,
            },
        ]
        result = compute_scores(positions)
        for pos in result:
            assert pos.get("momentum_score") is not None, (
                f"{pos['symbol']}: momentum_score must be computed even in a small pool"
            )
            # buy_priority_score is None for small pool
            assert pos["buy_priority_score"] is None

    def test_interaction_three_etfs_buyable_but_unrankable(self):
        """3-ETF portfolio: ETFs are buyable (#2) but unrankable (#3). Coherent outcome.

        is_buyable returns True (ETF exemption), but the pool-size rule sets
        buy_priority_score=None. Both rules coexist correctly — the note explains
        the unrankable state, not a gate rejection.
        """
        positions = [
            {"asset_type": "ETF", "symbol": "IWDA", "rsi": 85.0,
             "distance_from_52w_high_pct": 0.0, "perf_30d": 2.0,
             "perf_90d": 5.0, "perf_1y": 10.0, "weight": 30.0},
            {"asset_type": "ETF", "symbol": "EIMI", "rsi": 80.0,
             "distance_from_52w_high_pct": -1.0, "perf_30d": 1.5,
             "perf_90d": 4.0, "perf_1y": 8.0, "weight": 20.0},
            {"asset_type": "ETF", "symbol": "IUSN", "rsi": 75.0,
             "distance_from_52w_high_pct": -2.0, "perf_30d": 1.0,
             "perf_90d": 3.0, "perf_1y": 6.0, "weight": 15.0},
        ]
        result = compute_scores(positions)
        for pos in result:
            # ETF exemption: not gated out
            buyable, gate_reason = is_buyable(pos)
            assert buyable is True, f"{pos['symbol']}: ETF should be buyable even near highs"
            # Pool too small: unrankable
            assert pos["buy_priority_score"] is None, (
                f"{pos['symbol']}: 3-ETF pool should be unrankable (score=None)"
            )
            note = pos.get("buy_priority_note", "")
            assert "insufficient pool" in (note or "").lower(), (
                f"{pos['symbol']}: expected note about insufficient pool, got {note!r}"
            )
