"""Watchlist scoring: weight factor is neutral 0.5 for owned == False entries."""
import sys
sys.path.insert(0, 'app')
from scoring import compute_scores, get_top_candidates


def _etf(isin, weight, owned=True):
    """An ETF with all non-weight factors absent (→ 0.5) so buy_priority isolates weight."""
    return {
        "isin": isin, "symbol": isin, "name": isin, "asset_type": "ETF",
        "weight": weight, "owned": owned,
        "perf_30d": None, "perf_90d": None, "perf_1y": None,
        "pe_ratio": None, "price_to_book": None,
        "rsi": None, "distance_from_52w_high_pct": None,
        "last_buy_date": None,
    }


def test_unowned_item_gets_neutral_weight_factor():
    # 4 owned ETFs (weights 1..4) + 1 watchlist ETF (weight 0, owned=False).
    # ETFs skip is_buyable gates, pool size 5 ≥ 4 so all are ranked.
    pool = [_etf(f"OWN{i}", float(i)) for i in range(1, 5)]
    watch = _etf("WATCH", 0.0, owned=False)
    compute_scores(pool + [watch])
    # All non-weight factors are 0.5; recency neutral; so the watchlist item's
    # buy_priority_score must be exactly 0.5 (weight factor neutralized, not maxed).
    assert watch["buy_priority_score"] == 0.5


def test_unowned_weight_excluded_from_owned_normalization():
    owned_only = [_etf(f"OWN{i}", float(i)) for i in range(1, 5)]
    compute_scores(owned_only)
    baseline = {p["isin"]: p["buy_priority_score"] for p in owned_only}

    owned_with_watch = [_etf(f"OWN{i}", float(i)) for i in range(1, 5)]
    compute_scores(owned_with_watch + [_etf("WATCH", 0.0, owned=False)])
    after = {p["isin"]: p["buy_priority_score"] for p in owned_with_watch}
    assert after == baseline


def test_candidates_tagged_with_owned_flag():
    pool = [_etf(f"OWN{i}", float(i)) for i in range(1, 5)]
    watch = _etf("WATCH", 0.0, owned=False)
    scored = compute_scores(pool + [watch])
    cands = get_top_candidates(scored, n=10)
    by_isin = {c["isin"]: c for c in cands["etfs"]}
    assert by_isin["WATCH"]["owned"] is False
    assert by_isin["OWN1"]["owned"] is True


import app.universe as universe


def test_score_universe_returns_only_watchlist_scored(monkeypatch):
    owned = [
        {"isin": f"OWN{i}", "symbol": f"OWN{i}", "name": f"O{i}", "asset_type": "ETF",
         "weight": float(i), "owned": True,
         "perf_1y": None, "pe_ratio": None, "rsi": None,
         "distance_from_52w_high_pct": None, "last_buy_date": None}
        for i in range(1, 5)
    ]
    watch_entries = [{"isin": "WATCH", "symbol": "WATCH", "name": "W", "asset_type": "ETF"}]

    def fake_enrich_watchlist(entries):
        return [
            {"isin": "WATCH", "symbol": "WATCH", "name": "W", "asset_type": "ETF",
             "quantity": 0, "weight": 0, "owned": False, "source": "watchlist",
             "perf_1y": None, "pe_ratio": None, "rsi": None,
             "distance_from_52w_high_pct": None, "last_buy_date": None}
        ]

    monkeypatch.setattr(universe, "enrich_watchlist", fake_enrich_watchlist)
    result = universe.score_universe(owned, watch_entries)
    assert len(result) == 1
    assert result[0]["isin"] == "WATCH"
    assert result[0]["owned"] is False
    assert result[0]["buy_priority_score"] == 0.5  # neutral weight factor (from Task B1)
    # score_universe must NOT mutate the caller's owned position dicts
    assert "buy_priority_score" not in owned[0]
    assert "momentum_score" not in owned[0]


def test_score_universe_empty_watchlist_returns_empty():
    assert universe.score_universe([{"isin": "X", "asset_type": "ETF", "owned": True}], []) == []
