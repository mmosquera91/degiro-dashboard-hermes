"""Unit tests for health_checks.py — focus on HEALTH-05 trim-candidate visibility.

Trim candidates are informational ("consider trimming"), never an action. A position
is flagged when it is the inverse of buyable-for-being-too-hot: overbought (RSI high)
AND extended (at/near its 52-week high). The strategy stays buy-and-hold; this is
visibility only.
"""

import sys
sys.path.insert(0, 'app')
from health_checks import compute_health_alerts, _check_trim_candidates


def _pos(symbol, **overrides):
    base = {
        "asset_type": "STOCK",
        "name": f"Test {symbol}",
        "symbol": symbol,
        "rsi": 50.0,
        "distance_from_52w_high_pct": -15.0,
        "weight": 5.0,
        "current_value_eur": 1000.0,
        "perf_ytd": 5.0,
        "sector": "Technology",
    }
    base.update(overrides)
    return base


def _trim_alerts(positions):
    return [a for a in _check_trim_candidates(positions) if a is not None]


class TestTrimCandidates:
    def test_overbought_and_extended_is_flagged(self):
        """A position that is overbought AND at its 52w high is a trim candidate."""
        positions = [_pos("HOT", rsi=78.0, distance_from_52w_high_pct=-1.0)]
        alerts = _trim_alerts(positions)
        assert len(alerts) == 1
        assert alerts[0]["type"] == "trim_candidate"
        assert alerts[0]["severity"] == "info"
        assert "HOT" in alerts[0]["message"] or "Test HOT" in alerts[0]["message"]

    def test_overbought_but_not_extended_is_not_flagged(self):
        """High RSI alone (still well below 52w high) is NOT a trim candidate —
        it may just be a mid-trend position we keep holding."""
        positions = [_pos("DIP", rsi=78.0, distance_from_52w_high_pct=-25.0)]
        assert _trim_alerts(positions) == []

    def test_extended_but_not_overbought_is_not_flagged(self):
        """At the 52w high but with calm RSI is NOT a trim candidate."""
        positions = [_pos("CALM", rsi=55.0, distance_from_52w_high_pct=-0.5)]
        assert _trim_alerts(positions) == []

    def test_concentration_is_noted_in_message_when_also_overweight(self):
        """When an extended position is ALSO over the concentration cap, the message
        says so — the two signals combine into one trim rationale."""
        positions = [_pos("BIG", rsi=80.0, distance_from_52w_high_pct=0.0, weight=24.0)]
        alerts = _trim_alerts(positions)
        assert len(alerts) == 1
        assert "24" in alerts[0]["message"]  # weight surfaced

    def test_trim_alerts_appear_in_compute_health_alerts(self):
        """Trim candidates flow through the top-level aggregator."""
        portfolio = {
            "positions": [_pos("HOT", rsi=78.0, distance_from_52w_high_pct=-1.0)],
            "sector_breakdown": {},
            "etf_allocation_pct": 70,
            "stock_allocation_pct": 30,
        }
        alerts = compute_health_alerts(portfolio)
        assert any(a["type"] == "trim_candidate" for a in alerts)

    def test_missing_rsi_or_distance_is_not_flagged(self):
        """Positions lacking the data needed to judge 'extended' are never flagged."""
        assert _trim_alerts([_pos("NA1", rsi=None, distance_from_52w_high_pct=-1.0)]) == []
        assert _trim_alerts([_pos("NA2", rsi=80.0, distance_from_52w_high_pct=None)]) == []
