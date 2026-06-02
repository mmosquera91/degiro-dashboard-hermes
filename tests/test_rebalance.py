"""
Tests for the Cash-Flow Rebalancing Planner.

Pure-function tests with fabricated portfolio dicts.
Mirrors the pattern from test_scoring.py / test_health_checks.py.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from rebalance import plan_contribution, _split_budget_by_drift, _price_per_share_eur


# ─── Fixtures ──────────────────────────────────────────────────────────────────


def _make_position(
    name: str = "Test Stock",
    symbol: str = "TST",
    isin: str = "US0000000000",
    asset_type: str = "STOCK",
    quantity: float = 10,
    current_value_eur: float = 1000,
    current_price: float = 100,
    currency: str = "EUR",
    weight: float = 10.0,
    sector: str = "Technology",
    buy_priority_score: float = 0.5,
    perf_30d: float = 0.02,
    rsi: float = 45,
) -> dict:
    return {
        "name": name,
        "symbol": symbol,
        "isin": isin,
        "asset_type": asset_type,
        "quantity": quantity,
        "current_value_eur": current_value_eur,
        "current_price": current_price,
        "currency": currency,
        "weight": weight,
        "sector": sector,
        "buy_priority_score": buy_priority_score,
        "perf_30d": perf_30d,
        "rsi": rsi,
        "distance_from_52w_high_pct": -8,
        "momentum_score": 0.1,
        "country": "United States",
    }


def _make_portfolio(
    positions: list[dict] | None = None,
    total_value_eur: float = 10000,
    etf_pct: float = 70,
    stock_pct: float = 30,
) -> dict:
    if positions is None:
        positions = [
            _make_position("ETF-1", "ETF1", asset_type="ETF", current_value_eur=3500, weight=35, sector="Diversified", buy_priority_score=0.6),
            _make_position("ETF-2", "ETF2", asset_type="ETF", current_value_eur=3500, weight=35, sector="Diversified", buy_priority_score=0.55),
            _make_position("Stock-1", "STK1", asset_type="STOCK", current_value_eur=1500, weight=15, sector="Technology", buy_priority_score=0.7),
            _make_position("Stock-2", "STK2", asset_type="STOCK", current_value_eur=1500, weight=15, sector="Healthcare", buy_priority_score=0.4),
        ]
    return {
        "positions": positions,
        "total_value_eur": total_value_eur,
        "etf_allocation_pct": etf_pct,
        "stock_allocation_pct": stock_pct,
        "sector_breakdown": {},
    }


# ─── Basic validation ──────────────────────────────────────────────────────────


class TestBasicValidation:
    def test_zero_amount(self):
        result = plan_contribution(_make_portfolio(), 0)
        assert result["buys"] == []
        assert result["warnings"]

    def test_negative_amount(self):
        result = plan_contribution(_make_portfolio(), -100)
        assert result["buys"] == []
        assert result["warnings"]

    def test_empty_portfolio(self):
        result = plan_contribution({"positions": [], "total_value_eur": 0}, 1000)
        assert result["buys"] == []
        assert result["hold_reserve_eur"] == 1000

    def test_zero_value_portfolio(self):
        result = plan_contribution({"positions": [_make_position()], "total_value_eur": 0}, 1000)
        assert result["buys"] == []
        assert result["hold_reserve_eur"] == 1000

    def test_no_positions_key(self):
        result = plan_contribution({"total_value_eur": 1000}, 500)
        assert result["buys"] == []


# ─── Reconciliation ────────────────────────────────────────────────────────────


class TestReconciliation:
    """Sum of spends + hold_reserve must equal amount requested."""

    def test_reconciliation_basic(self):
        pf = _make_portfolio()
        amount = 1000
        result = plan_contribution(pf, amount)
        total_spent = sum(b["spend_eur"] for b in result["buys"])
        hold = result["hold_reserve_eur"]
        assert abs((total_spent + hold) - amount) < 0.02, f"Spend {total_spent} + hold {hold} != {amount}"

    def test_reconciliation_large_amount(self):
        pf = _make_portfolio()
        amount = 5000
        result = plan_contribution(pf, amount)
        total_spent = sum(b["spend_eur"] for b in result["buys"])
        hold = result["hold_reserve_eur"]
        assert abs((total_spent + hold) - amount) < 0.02

    def test_reconciliation_tiny_amount(self):
        pf = _make_portfolio()
        amount = 5  # too small to buy anything
        result = plan_contribution(pf, amount)
        # Either nothing bought or very little
        total_spent = sum(b["spend_eur"] for b in result["buys"])
        hold = result["hold_reserve_eur"]
        assert abs((total_spent + hold) - amount) < 0.02

    def test_reconciliation_single_etf(self):
        pos = [_make_position("Only ETF", "OETF", asset_type="ETF", current_value_eur=10000, weight=100, sector="Diversified")]
        pf = _make_portfolio(positions=pos, total_value_eur=10000, etf_pct=100, stock_pct=0)
        result = plan_contribution(pf, 500)
        total_spent = sum(b["spend_eur"] for b in result["buys"])
        hold = result["hold_reserve_eur"]
        assert abs((total_spent + hold) - 500) < 0.02


# ─── Drift correction ──────────────────────────────────────────────────────────


class TestDriftCorrection:
    def test_underweight_etfs_get_more_budget(self):
        """When ETFs are underweight, most cash should flow to ETFs."""
        positions = [
            _make_position("ETF-1", "E1", asset_type="ETF", current_value_eur=3000, weight=30, quantity=30, current_price=100, sector="Diversified"),
            _make_position("Stock-1", "S1", asset_type="STOCK", current_value_eur=7000, weight=70, quantity=70, current_price=100, sector="Technology"),
        ]
        pf = _make_portfolio(positions=positions, total_value_eur=10000, etf_pct=30, stock_pct=70)
        result = plan_contribution(pf, 1000)

        # Most budget should go to ETF side since 30% vs target 70%
        etf_spent = sum(b["spend_eur"] for b in result["buys"] if b["asset_type"] == "ETF")
        stock_spent = sum(b["spend_eur"] for b in result["buys"] if b["asset_type"] == "STOCK")
        assert etf_spent >= stock_spent, f"ETF spend {etf_spent} should be >= stock {stock_spent}"

    def test_at_target_preserves_allocation(self):
        """When already at target, budget splits by target weights."""
        positions = [
            _make_position("ETF-1", "E1", asset_type="ETF", current_value_eur=7000, weight=70, quantity=70, current_price=100, sector="Diversified"),
            _make_position("Stock-1", "S1", asset_type="STOCK", current_value_eur=3000, weight=30, quantity=30, current_price=100, sector="Technology"),
        ]
        pf = _make_portfolio(positions=positions, total_value_eur=10000, etf_pct=70, stock_pct=30)
        result = plan_contribution(pf, 1000)

        # Should roughly split 70/30
        etf_spent = sum(b["spend_eur"] for b in result["buys"] if b["asset_type"] == "ETF")
        stock_spent = sum(b["spend_eur"] for b in result["buys"] if b["asset_type"] == "STOCK")
        total_spent = etf_spent + stock_spent
        if total_spent > 0:
            etf_ratio = etf_spent / total_spent
            assert 0.5 < etf_ratio < 0.9, f"ETF ratio {etf_ratio:.2f} should be near 0.7"

    def test_projected_drift_shrinks(self):
        """After the plan, drift should be smaller than before."""
        positions = [
            _make_position("ETF-1", "E1", asset_type="ETF", current_value_eur=3000, weight=30, quantity=30, current_price=100, sector="Diversified"),
            _make_position("Stock-1", "S1", asset_type="STOCK", current_value_eur=7000, weight=70, quantity=70, current_price=100, sector="Technology"),
        ]
        pf = _make_portfolio(positions=positions, total_value_eur=10000, etf_pct=30, stock_pct=70)
        result = plan_contribution(pf, 2000)
        proj = result["projected"]

        # Drift after should be smaller (less negative) than before for ETFs
        assert abs(proj["etf_drift_after"]) <= abs(proj["etf_drift_before"])


# ─── Concentration cap ─────────────────────────────────────────────────────────


class TestConcentrationCap:
    def test_over_cap_position_gets_zero(self):
        """A position already at 20%+ weight should not get more."""
        positions = [
            _make_position("Big ETF", "BIG", asset_type="ETF", current_value_eur=8000, weight=80, quantity=80, current_price=100, sector="Diversified", buy_priority_score=0.9),
            _make_position("Small ETF", "SML", asset_type="ETF", current_value_eur=2000, weight=20, quantity=20, current_price=100, sector="Diversified", buy_priority_score=0.3),
        ]
        pf = _make_portfolio(positions=positions, total_value_eur=10000, etf_pct=100, stock_pct=0)
        result = plan_contribution(pf, 500)

        # The big position should either not appear in buys or get very little
        big_buys = [b for b in result["buys"] if b["symbol"] == "BIG"]
        if big_buys:
            assert big_buys[0]["new_weight_pct"] <= 21, "Should not push above cap"


# ─── Whole share snapping ──────────────────────────────────────────────────────


class TestWholeShares:
    def test_shares_are_integers(self):
        result = plan_contribution(_make_portfolio(), 1000)
        for buy in result["buys"]:
            assert isinstance(buy["shares"], int), f"{buy['name']} has non-integer shares: {buy['shares']}"

    def test_spend_matches_shares_times_price(self):
        result = plan_contribution(_make_portfolio(), 1000)
        for buy in result["buys"]:
            expected = round(buy["shares"] * buy["price_eur"], 2)
            assert abs(buy["spend_eur"] - expected) < 0.02, f"{buy['name']}: {buy['spend_eur']} != {buy['shares']}×{buy['price_eur']}"


# ─── Budget split ──────────────────────────────────────────────────────────────


class TestBudgetSplit:
    def test_split_sums_to_amount(self):
        etf_budget, stock_budget = _split_budget_by_drift(
            1000, 10000,
            [_make_position(asset_type="ETF")],
            [_make_position(asset_type="STOCK")],
            70, 30,
        )
        assert abs(etf_budget + stock_budget - 1000) < 0.02

    def test_gap_driven_split(self):
        """Huge ETF gap → most budget to ETFs."""
        etf_budget, stock_budget = _split_budget_by_drift(
            1000, 10000,
            [_make_position(asset_type="ETF", current_value_eur=2000)],
            [_make_position(asset_type="STOCK", current_value_eur=3000)],
            20, 30,  # etf is only 20% vs target 70%
        )
        assert etf_budget > stock_budget


# ─── Price helper ──────────────────────────────────────────────────────────────


class TestPriceHelper:
    def test_eur_position_from_value_qty(self):
        pos = {"quantity": 10, "current_value_eur": 1000, "currency": "EUR"}
        assert _price_per_share_eur(pos) == 100.0

    def test_non_eur_position_no_fallback(self):
        pos = {"quantity": 10, "current_value_eur": 0, "currency": "USD", "current_price": 100}
        assert _price_per_share_eur(pos) is None

    def test_zero_quantity(self):
        pos = {"quantity": 0, "current_value_eur": 1000, "currency": "EUR", "current_price": 100}
        # zero qty → division by zero → fallback to current_price
        assert _price_per_share_eur(pos) is None or _price_per_share_eur(pos) == 100


# ─── Excluded positions ────────────────────────────────────────────────────────


class TestExclusions:
    def test_fx_missing_excluded(self):
        """Position with non-EUR currency and no value should be excluded."""
        positions = [
            _make_position("GBP Stock", "GBS", currency="GBp", current_value_eur=0, quantity=0),
            _make_position("ETF-1", "E1", asset_type="ETF", current_value_eur=10000, weight=100, quantity=100, current_price=100, sector="Diversified"),
        ]
        pf = _make_portfolio(positions=positions, total_value_eur=10000, etf_pct=100, stock_pct=0)
        result = plan_contribution(pf, 500)
        excluded_symbols = [e["symbol"] for e in result["excluded"]]
        assert "GBS" in excluded_symbols

    def test_zero_quantity_excluded(self):
        positions = [
            _make_position("Sold", "SOLD", quantity=0),
            _make_position("ETF-1", "E1", asset_type="ETF", current_value_eur=10000, weight=100, quantity=100, current_price=100, sector="Diversified"),
        ]
        pf = _make_portfolio(positions=positions, total_value_eur=10000, etf_pct=100, stock_pct=0)
        result = plan_contribution(pf, 500)
        excluded_symbols = [e["symbol"] for e in result["excluded"]]
        assert "SOLD" in excluded_symbols


# ─── Quality gates ─────────────────────────────────────────────────────────────


class TestQualityGates:
    def test_gated_positions_still_eligible(self):
        """Positions with buy_priority_score=None can still be bought (deprioritized)."""
        positions = [
            _make_position("Gated", "GTD", buy_priority_score=None, asset_type="ETF", current_value_eur=600, weight=3, quantity=6, current_price=100, sector="Diversified"),
            _make_position("OK ETF", "OK", buy_priority_score=0.8, asset_type="ETF", current_value_eur=600, weight=3, quantity=6, current_price=100, sector="Diversified"),
            _make_position("Big Stock", "BS", asset_type="STOCK", current_value_eur=18800, weight=94, quantity=188, current_price=100, sector="Technology"),
        ]
        pf = _make_portfolio(positions=positions, total_value_eur=20000, etf_pct=6, stock_pct=94)
        result = plan_contribution(pf, 500)
        # Should still produce buys
        assert len(result["buys"]) > 0

    def test_high_score_preferred(self):
        """Position with higher buy_priority_score should get more allocation."""
        positions = [
            _make_position("Low Score", "LOW", buy_priority_score=0.1, asset_type="ETF", current_value_eur=5000, weight=50, quantity=50, current_price=100, sector="Diversified"),
            _make_position("High Score", "HIGH", buy_priority_score=0.9, asset_type="ETF", current_value_eur=5000, weight=50, quantity=50, current_price=100, sector="Diversified"),
        ]
        pf = _make_portfolio(positions=positions, total_value_eur=10000, etf_pct=100, stock_pct=0)
        result = plan_contribution(pf, 500)
        # High score should appear earlier or get more budget
        symbols_order = [b["symbol"] for b in result["buys"]]
        if "HIGH" in symbols_order and "LOW" in symbols_order:
            assert symbols_order.index("HIGH") <= symbols_order.index("LOW"), "High score should be ranked first"


# ─── Output shape ──────────────────────────────────────────────────────────────


class TestOutputShape:
    def test_has_required_keys(self):
        result = plan_contribution(_make_portfolio(), 1000)
        assert "amount_requested" in result
        assert "currency" in result
        assert "buys" in result
        assert "hold_reserve_eur" in result
        assert "hold_reasons" in result
        assert "projected" in result
        assert "excluded" in result
        assert "warnings" in result

    def test_projected_has_drift_fields(self):
        result = plan_contribution(_make_portfolio(), 1000)
        proj = result["projected"]
        assert "etf_allocation_pct" in proj
        assert "stock_allocation_pct" in proj
        assert "etf_drift_before" in proj
        assert "etf_drift_after" in proj
        assert "stock_drift_before" in proj
        assert "stock_drift_after" in proj

    def test_buy_items_have_required_fields(self):
        result = plan_contribution(_make_portfolio(), 1000)
        for buy in result["buys"]:
            assert "name" in buy
            assert "symbol" in buy
            assert "shares" in buy
            assert "price_eur" in buy
            assert "spend_eur" in buy
            assert "reason" in buy
            assert "new_weight_pct" in buy
            assert "asset_type" in buy


# ─── Regression: core ETFs above 5% weight must still be buyable ──────────────


class TestCoreETFBuyable:
    def test_concentrated_core_etfs_receive_budget(self):
        """
        Regression test for the >5% hard-skip bug.

        A realistic index-investor portfolio: 4 core ETFs each at ~15% weight
        (total ETF ~60%), 1 stock at ~40% weight.  The 70% ETF target means
        the portfolio is significantly underweight ETFs.

        Crucially, all 4 ETFs sit in the 5-20% weight band — above the old
        >5% hard-skip threshold that excluded them from `weights`, but below
        the legitimate 20% concentration cap that correctly skips over-weight
        positions.  With a €2 000 contribution:

        Before the fix: ALL ETFs excluded by `if weight > 5.0: continue` →
        `weights` is empty after Phase 1 → `_allocate_budget` returns ([], 0)
        for the ETF side → full budget falls through to hold_reserve.

        After the fix: quadratic headroom + concentration-cap logic handles
        these positions correctly; buys are made and cash is deployed.
        """
        # 4 ETFs × €1 500 = €6 000 ETF total out of €10 000 → 60% vs 70% target
        # 1 stock  × €4 000 = €4 000 stock total → 40%
        # Each ETF weight = 15%  (>5% triggers old bug, <20% bypasses cap guard)
        total = 10_000.0
        etf_value_each = 1_500.0   # 15% weight each
        stock_value = 4_000.0      # 40% weight

        positions = [
            _make_position(
                "World ETF", "VWCE", isin="IE00B3RBWM25",
                asset_type="ETF",
                quantity=15, current_value_eur=etf_value_each,
                current_price=etf_value_each / 15,
                currency="EUR",
                weight=15.0,
                sector="Diversified",
                buy_priority_score=0.8,
            ),
            _make_position(
                "Europe ETF", "MEUD", isin="LU0908500753",
                asset_type="ETF",
                quantity=20, current_value_eur=etf_value_each,
                current_price=etf_value_each / 20,
                currency="EUR",
                weight=15.0,
                sector="Diversified",
                buy_priority_score=0.7,
            ),
            _make_position(
                "EM ETF", "VFEM", isin="IE00B3CNHF17",
                asset_type="ETF",
                quantity=30, current_value_eur=etf_value_each,
                current_price=etf_value_each / 30,
                currency="EUR",
                weight=15.0,
                sector="Diversified",
                buy_priority_score=0.6,
            ),
            _make_position(
                "Small Cap ETF", "WSML", isin="IE00BF4RFH31",
                asset_type="ETF",
                quantity=25, current_value_eur=etf_value_each,
                current_price=etf_value_each / 25,
                currency="EUR",
                weight=15.0,
                sector="Diversified",
                buy_priority_score=0.65,
            ),
            _make_position(
                "Tech Stock", "ASML", isin="NL0010273215",
                asset_type="STOCK",
                quantity=4, current_value_eur=stock_value,
                current_price=stock_value / 4,
                currency="EUR",
                weight=40.0,
                sector="Technology",
                buy_priority_score=0.5,
            ),
        ]

        pf = {
            "positions": positions,
            "total_value_eur": total,
            "etf_allocation_pct": 60.0,   # 60% actual vs 70% target → clear ETF gap
            "stock_allocation_pct": 40.0,
            "sector_breakdown": {},
        }

        result = plan_contribution(pf, 2000)

        total_spent = sum(b["spend_eur"] for b in result["buys"])
        etf_spent = sum(b["spend_eur"] for b in result["buys"] if b["asset_type"] == "ETF")

        # Core ETFs must receive meaningful cash — at least half the contribution.
        # Before the fix this is 0 (all ETFs excluded by the >5% skip).
        assert total_spent > 1000, (
            f"Expected >€1000 deployed but total_spent={total_spent}, "
            f"hold_reserve={result['hold_reserve_eur']}, buys={result['buys']}"
        )
        assert etf_spent > 500, (
            f"Expected >€500 to ETFs but etf_spent={etf_spent}, buys={result['buys']}"
        )
