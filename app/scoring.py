"""Scoring logic — momentum score and buy priority score."""

import logging
from datetime import date as date_type, datetime as dt_type
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

COOLDOWN_DAYS = 10


def _zscore_normalize(values: list[float]) -> list[float]:
    """Z-score normalize a list of values to [0, 1] via standard scoring.

    Maps to [0, 1] using max(0, min(1, 0.5 + (v - mean) / (3 * std))).
    If N < 4, returns [0.5] * N (insufficient data for z-score).
    None values are treated as the median of non-None values.
    """
    clean = [v for v in values if v is not None]
    if not clean:
        return [0.5] * len(values)

    median_val = float(np.median(clean))
    filled = [v if v is not None else median_val for v in values]

    n = len(filled)
    if n < 4:
        return [0.5] * n

    mean_val = float(np.mean(filled))
    std_val = float(np.std(filled, ddof=1))

    if std_val > 0 and std_val < 0.01:
        std_val = 0.01

    if std_val == 0:
        return [0.5] * n

    return [max(0.0, min(1.0, 0.5 + (v - mean_val) / (3 * std_val))) for v in filled]


def _normalize_lower_better(values: list[Optional[float]]) -> list[Optional[float]]:
    """Z-score normalize a factor where LOWER raw values are better (e.g. P/E, P/B).

    Negates before z-scoring so cheaper → higher normalized score. None inputs map
    to None outputs (the caller decides the fallback) so a missing metric does not
    pollute the pool or get silently treated as cheap/expensive.
    """
    clean = [v for v in values if v is not None]
    if not clean:
        return [None] * len(values)

    normed = _zscore_normalize([-v for v in clean])
    out: list[Optional[float]] = []
    ci = 0
    for v in values:
        if v is None:
            out.append(None)
        else:
            out.append(normed[ci])
            ci += 1
    return out


def compute_momentum_score(position: dict) -> Optional[float]:
    """Compute momentum score for a single position.

    Momentum score = weighted average of 30d (20%), 90d (30%), 1Y (50%) performance.
    """
    perf_30d = position.get("perf_30d")
    perf_90d = position.get("perf_90d")
    perf_1y = position.get("perf_1y")

    # Need at least 1Y performance
    if perf_1y is None and perf_90d is None and perf_30d is None:
        return None

    # Fill missing with 0
    p30 = perf_30d if perf_30d is not None else 0.0
    p90 = perf_90d if perf_90d is not None else 0.0
    p1y = perf_1y if perf_1y is not None else 0.0

    return round((0.20 * p30) + (0.30 * p90) + (0.50 * p1y), 2)


def compute_value_score(position: dict) -> Optional[float]:
    """Compute value score — lower P/E and P/B are better.

    Averages trailing_pe and price_to_book (both from yfinance).
    If neither is available → None (gets 0.5 in normalize).
    """
    pe = position.get("pe_ratio")
    pb = position.get("price_to_book")

    has_pe = pe is not None and pe > 0
    has_pb = pb is not None and pb > 0

    if not has_pe and not has_pb:
        return None

    if has_pe and has_pb:
        return round((pe + pb) / 2, 2)
    if has_pe:
        return round(pe, 2)
    return round(pb, 2)


def is_buyable(position: dict) -> tuple[bool, str | None]:
    """Absolute quality gates before buy eligibility.

    ETFs are ALWAYS buyable — they are exempt from all three entry gates.
    Rationale: this is a 70% ETF / 30% STOCK buy-and-hold DCA portfolio. The ETF
    core is bought on a schedule regardless of market conditions; market-timing the
    index (RSI, distance from 52w high) is counterproductive and causes the dashboard
    to disagree with the rebalancer when markets are near highs.

    For STOCKs only — three entry gates apply:
      RSI < 70 (not overbought), distance_from_52w_high_pct < -3% (sufficiently below
      the 52w high), momentum_score > -25 (not in freefall).

    Returns (bool, reason) where reason is None if buyable, or a string describing
    the blocking gate.
    """
    # ETFs skip all entry gates — timing the index core fights buy-and-hold DCA.
    if position.get("asset_type") == "ETF":
        return True, None

    rsi = position.get("rsi")
    if rsi is not None and rsi >= 70:
        return False, f"RSI {rsi:.0f}>=70"

    dist = position.get("distance_from_52w_high_pct")
    if dist is not None and dist >= -3:
        # Not far enough below 52w high — requires strictly < -3
        dist_abs = abs(dist)
        return False, f"a {dist_abs:.0f}% del max 52s"

    momentum = position.get("momentum_score")
    if momentum is not None and momentum <= -25:
        return False, f"momentum {momentum:.0f}<=-25"

    return True, None


def compute_scores(positions: list[dict]) -> list[dict]:
    """Compute momentum, value, and buy priority scores for all positions.

    Buy priority is computed within separate ETF and STOCK pools.
    Only positions passing is_buyable() are scored; others get buy_priority_score = None.
    """
    # Step 1: Compute momentum score for each position
    for pos in positions:
        pos["momentum_score"] = compute_momentum_score(pos)

    # Step 2: Compute value score for each position
    for pos in positions:
        pos["value_score"] = compute_value_score(pos)

    # Step 3: Compute buy priority score — separately for ETFs and Stocks
    etfs = [p for p in positions if p.get("asset_type") == "ETF"]
    stocks = [p for p in positions if p.get("asset_type") == "STOCK"]

    for pool in [etfs, stocks]:
        if not pool:
            continue

        n = len(pool)

        # Pool-size guard: fewer than 4 positions cannot be z-score ranked meaningfully.
        # A fabricated 0.5 is not a real ranking — mark every position in the pool as
        # unrankable instead. momentum_score and value_score are still computed above
        # (per-position, not pool-relative), so those remain useful.
        if n < 4:
            for pos in pool:
                buyable, blocked_reason = is_buyable(pos)
                pos["buy_priority_score"] = None
                if not buyable:
                    pos["buy_priority_blocked_reason"] = blocked_reason
                else:
                    pos["buy_priority_note"] = (
                        "insufficient pool to rank (need 4+ holdings in pool)"
                    )
            continue

        # Pre-compute mask: which positions pass is_buyable
        buyable_results = [is_buyable(p) for p in pool]
        buyable_mask = [r[0] for r in buyable_results]

        # Momentum scores (used as independent signal, not inverted)
        momentum_scores = [p.get("momentum_score") for p in pool]
        mom_none_mask = [v is None for v in momentum_scores]
        mom_clean = [v for v in momentum_scores if v is not None]
        norm_momentum = _zscore_normalize(mom_clean) if mom_clean else [0.5]
        norm_momentum_full = []
        ni = 0
        for has_none in mom_none_mask:
            norm_momentum_full.append(0.5 if has_none else norm_momentum[ni])
            if not has_none:
                ni += 1

        # value — normalize P/E and P/B SEPARATELY (they live on different scales),
        # then average the available normalized metrics. Lower is better for both,
        # so _normalize_lower_better negates before z-scoring. Averaging the *raw*
        # ratios would let whichever number is larger (usually P/E) dominate.
        def _clean_ratio(v):
            return v if (v is not None and v > 0) else None

        pe_norm = _normalize_lower_better([_clean_ratio(p.get("pe_ratio")) for p in pool])
        pb_norm = _normalize_lower_better([_clean_ratio(p.get("price_to_book")) for p in pool])
        norm_value_full = []
        for pe_n, pb_n in zip(pe_norm, pb_norm):
            present = [x for x in (pe_n, pb_n) if x is not None]
            norm_value_full.append(sum(present) / len(present) if present else 0.5)

        # distance_from_52w_high_pct
        distances = [p.get("distance_from_52w_high_pct") for p in pool]
        dist_none_mask = [d is None for d in distances]
        dist_clean = [d for d in distances if d is not None]
        norm_distance = _zscore_normalize([-d for d in dist_clean]) if dist_clean else [0.5]
        norm_distance_full = []
        ni = 0
        for has_none in dist_none_mask:
            norm_distance_full.append(0.5 if has_none else norm_distance[ni])
            if not has_none:
                ni += 1

        # rsi
        rsi_values = [p.get("rsi") for p in pool]
        rsi_none_mask = [r is None for r in rsi_values]
        rsi_clean = [r for r in rsi_values if r is not None]
        norm_rsi_inv = _zscore_normalize([100 - r for r in rsi_clean]) if rsi_clean else [0.5]
        norm_rsi_full = []
        ni = 0
        for has_none in rsi_none_mask:
            norm_rsi_full.append(0.5 if has_none else norm_rsi_inv[ni])
            if not has_none:
                ni += 1

        # weight — reward being underweight. Watchlist (owned == False) entries have no
        # portfolio weight; give them the neutral 0.5 directly and EXCLUDE them from the
        # z-score so a weight of 0 (maximally underweight) neither auto-boosts the candidate
        # nor distorts owned positions' normalization. owned defaults True for back-compat.
        owned_flags = [p.get("owned", True) for p in pool]
        owned_weights = [(p.get("weight", 0) or 0) for p, o in zip(pool, owned_flags) if o]
        norm_owned_weight = _zscore_normalize([-w for w in owned_weights]) if owned_weights else [0.5]
        norm_weight_full = []
        oi = 0
        for o in owned_flags:
            if o:
                norm_weight_full.append(norm_owned_weight[oi])
                oi += 1
            else:
                norm_weight_full.append(0.5)

        # recency — days since last buy (cooldown penalty)
        today = date_type.today()
        recency_factors = []
        for pos in pool:
            last_buy = pos.get("last_buy_date")
            if last_buy:
                try:
                    if isinstance(last_buy, str):
                        parsed = dt_type.fromisoformat(last_buy.replace("Z", "+00:00"))
                        buy_date = parsed.date() if hasattr(parsed, "date") else parsed
                    elif isinstance(last_buy, (dt_type, date_type)):
                        buy_date = last_buy.date() if hasattr(last_buy, "date") else last_buy
                    else:
                        buy_date = None
                    if buy_date:
                        days_since = (today - buy_date).days
                        recency_factors.append(max(0.0, min(1.0, days_since / COOLDOWN_DAYS)))
                    else:
                        recency_factors.append(1.0)
                except Exception:
                    recency_factors.append(1.0)
            else:
                recency_factors.append(1.0)

        recency_none_mask = [r == 1.0 and pos.get("last_buy_date") is None
                             for pos, r in zip(pool, recency_factors)]
        recency_clean = [r for r, is_none in zip(recency_factors, recency_none_mask) if not is_none]
        norm_recency = _zscore_normalize(recency_clean) if recency_clean else [0.5]
        norm_recency_full = []
        ni = 0
        for is_none in recency_none_mask:
            norm_recency_full.append(0.5 if is_none else norm_recency[ni])
            if not is_none:
                ni += 1

        for i, pos in enumerate(pool):
            if not buyable_mask[i]:
                pos["buy_priority_score"] = None
                pos["buy_priority_blocked_reason"] = buyable_results[i][1]
                continue

            buy_score = (
                0.20 * norm_value_full[i]
                + 0.15 * norm_momentum_full[i]
                + 0.20 * norm_distance_full[i]
                + 0.15 * norm_rsi_full[i]
                + 0.20 * norm_weight_full[i]
                + 0.10 * norm_recency_full[i]
            )
            pos["buy_priority_score"] = round(buy_score, 2)

    # Set buy_priority_score to None for positions not in either pool
    for pos in positions:
        if "buy_priority_score" not in pos:
            pos["buy_priority_score"] = None

    return positions


def compute_portfolio_weights(positions: list[dict]) -> list[dict]:
    """Compute portfolio weight for each position based on EUR value."""
    total_value = sum(p.get("current_value_eur", 0) or 0 for p in positions)

    if total_value == 0:
        for pos in positions:
            pos["weight"] = 0.0
        return positions

    for pos in positions:
        val = pos.get("current_value_eur", 0) or 0
        pos["weight"] = round((val / total_value) * 100, 2)

    return positions


def get_top_candidates(positions: list[dict], n: int = 3) -> dict:
    """Get top N ETF and Stock candidates by buy priority score."""
    etfs = sorted(
        [p for p in positions if p.get("asset_type") == "ETF" and p.get("buy_priority_score") is not None],
        key=lambda x: x["buy_priority_score"],
        reverse=True,
    )
    stocks = sorted(
        [p for p in positions if p.get("asset_type") == "STOCK" and p.get("buy_priority_score") is not None],
        key=lambda x: x["buy_priority_score"],
        reverse=True,
    )

    def build_reason(pos: dict) -> str:
        """Build a human-readable reason string for why this position is a candidate."""
        parts = []
        rsi = pos.get("rsi")
        if rsi is not None:
            parts.append(f"RSI: {rsi:.0f}")
        dist = pos.get("distance_from_52w_high_pct")
        if dist is not None:
            parts.append(f"{abs(dist):.1f}% below 52w high" if dist < 0 else f"{dist:.1f}% from 52w high")
        momentum = pos.get("momentum_score")
        if momentum is not None:
            if momentum < 0:
                parts.append("low recent momentum")
            else:
                parts.append(f"momentum: {momentum:+.1f}%")
        return " — ".join(parts) if parts else "Score-based ranking"

    top_etfs = []
    for p in etfs[:n]:
        top_etfs.append({
            "name": p.get("name", ""),
            "symbol": p.get("symbol", ""),
            "isin": p.get("isin", ""),
            "buy_priority_score": p.get("buy_priority_score"),
            "reason": build_reason(p),
            "current_price": p.get("current_price"),
            "rsi": p.get("rsi"),
            "distance_from_52w_high_pct": p.get("distance_from_52w_high_pct"),
            "momentum_score": p.get("momentum_score"),
            "weight": p.get("weight"),
            "owned": p.get("owned", True),
        })

    top_stocks = []
    for p in stocks[:n]:
        top_stocks.append({
            "name": p.get("name", ""),
            "symbol": p.get("symbol", ""),
            "isin": p.get("isin", ""),
            "buy_priority_score": p.get("buy_priority_score"),
            "reason": build_reason(p),
            "current_price": p.get("current_price"),
            "rsi": p.get("rsi"),
            "distance_from_52w_high_pct": p.get("distance_from_52w_high_pct"),
            "momentum_score": p.get("momentum_score"),
            "weight": p.get("weight"),
            "owned": p.get("owned", True),
        })

    return {"etfs": top_etfs, "stocks": top_stocks}
