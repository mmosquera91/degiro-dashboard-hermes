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
