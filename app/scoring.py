"""Scoring logic — momentum score and buy priority score."""

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


def _min_max_normalize(values: list[float]) -> list[float]:
    """Min-max normalize a list of values to [0, 1].

    If all values are the same, returns 0.5 for all.
    None values are treated as the median of non-None values.
    """
    # Replace None with median
    clean = [v for v in values if v is not None]
    if not clean:
        return [0.5] * len(values)

    median_val = float(np.median(clean))
    filled = [v if v is not None else median_val for v in values]

    min_val = min(filled)
    max_val = max(filled)

    if min_val == max_val:
        return [0.5] * len(values)

    return [(v - min_val) / (max_val - min_val) for v in filled]


def compute_momentum_score(position: dict) -> Optional[float]:
    """Compute momentum score for a single position.

    Momentum score = weighted average of 30d (20%), 90d (30%), YTD (50%) performance.
    """
    perf_30d = position.get("perf_30d")
    perf_90d = position.get("perf_90d")
    perf_ytd = position.get("perf_ytd")

    # Need at least YTD performance
    if perf_ytd is None and perf_90d is None and perf_30d is None:
        return None

    # Fill missing with 0
    p30 = perf_30d if perf_30d is not None else 0.0
    p90 = perf_90d if perf_90d is not None else 0.0
    pytd = perf_ytd if perf_ytd is not None else 0.0

    return round((0.20 * p30) + (0.30 * p90) + (0.50 * pytd), 2)


def compute_value_score(position: dict) -> Optional[float]:
    """Compute value score — higher for positions that are more 'on sale'.

    Based on inverse of recent gains: positions with lower momentum score higher.
    We negate the momentum score so that weak momentum = high value score.
    """
    momentum = position.get("momentum_score")
    if momentum is None:
        return None
    return round(-momentum, 2)


def compute_scores(positions: list[dict]) -> list[dict]:
    """Compute momentum, value, and buy priority scores for all positions.

    Buy priority is computed within separate ETF and STOCK pools.
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

        # Extract raw values for normalization
        value_scores = [p.get("value_score", 0) or 0 for p in pool]
        distances = [p.get("distance_from_52w_high_pct", 0) or 0 for p in pool]
        rsi_values = [p.get("rsi", 50) or 50 for p in pool]
        weights = [p.get("weight", 1) or 1 for p in pool]

        # Normalize each component to [0, 1]
        norm_value = _min_max_normalize(value_scores)
        # Distance from 52w high is negative when below high — more negative = more opportunity
        # We want higher score for more negative distance, so negate before normalizing
        norm_distance = _min_max_normalize([-d for d in distances])
        # RSI inverse: lower RSI = higher score (oversold = opportunity)
        norm_rsi_inv = _min_max_normalize([100 - r for r in rsi_values])
        # Portfolio weight inverse: lower weight = higher score (diversification)
        norm_weight_inv = _min_max_normalize([-w for w in weights])

        for i, pos in enumerate(pool):
            buy_score = (
                0.35 * norm_value[i]
                + 0.35 * norm_distance[i]
                + 0.20 * norm_rsi_inv[i]
                + 0.10 * norm_weight_inv[i]
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
        })

    return {"etfs": top_etfs, "stocks": top_stocks}
