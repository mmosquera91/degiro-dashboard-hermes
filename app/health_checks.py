"""Health checks — concentration, sector, drawdown, and rebalancing alerts."""

import os

HEALTH_POSITION_THRESHOLD  = int(os.getenv("HEALTH_POSITION_THRESHOLD", "20"))
HEALTH_SECTOR_THRESHOLD   = int(os.getenv("HEALTH_SECTOR_THRESHOLD", "40"))
HEALTH_DRAWDOWN_THRESHOLD = int(os.getenv("HEALTH_DRAWDOWN_THRESHOLD", "-10"))
HEALTH_REBALANCE_THRESHOLD = int(os.getenv("HEALTH_REBALANCE_THRESHOLD", "5"))
TARGET_ETF_PCT   = int(os.getenv("TARGET_ETF_PCT", "70"))
TARGET_STOCK_PCT = int(os.getenv("TARGET_STOCK_PCT", "30"))


def compute_health_alerts(portfolio: dict) -> list[dict]:
    """Compute all health alerts from a portfolio dict.

    Called after enrich_positions, compute_portfolio_weights, compute_scores.
    """
    alerts = []
    positions = portfolio.get("positions", [])
    sector_breakdown = portfolio.get("sector_breakdown", {})
    etf_pct = portfolio.get("etf_allocation_pct", 0)
    stock_pct = portfolio.get("stock_allocation_pct", 0)

    # HEALTH-01: Concentration risk
    alerts.extend(_check_concentration(positions))

    # HEALTH-02: Sector weighting
    alerts.extend(_check_sector_weighting(positions))

    # HEALTH-03: Drawdown
    alerts.append(_check_drawdown(positions))

    # HEALTH-04: Rebalancing
    alerts.append(_check_rebalancing(etf_pct, stock_pct))

    return [a for a in alerts if a is not None]


def _check_concentration(positions: list) -> list[dict]:
    """HEALTH-01: Warn when a single position exceeds HEALTH_POSITION_THRESHOLD."""
    alerts = []
    for pos in positions:
        weight = pos.get("weight") or 0
        if weight > HEALTH_POSITION_THRESHOLD:
            alerts.append({
                "type": "concentration",
                "severity": "warn",
                "message": f"{pos.get('name', 'Unknown')} is {weight:.1f}% of portfolio (threshold {HEALTH_POSITION_THRESHOLD}%)",
                "current_value": weight,
                "threshold": float(HEALTH_POSITION_THRESHOLD),
                "triggering_positions": [{
                    "name": pos.get("name", ""),
                    "symbol": pos.get("symbol", ""),
                    "value": weight,
                }],
            })
    return alerts


def _check_sector_weighting(positions: list) -> list[dict]:
    """HEALTH-02: Warn when any stock sector exceeds HEALTH_SECTOR_THRESHOLD."""
    stock_positions = [p for p in positions if p.get("asset_type") != "ETF"]
    stock_sector_breakdown = {}
    for p in stock_positions:
        s = p.get("sector") or "Unknown"
        stock_sector_breakdown[s] = stock_sector_breakdown.get(s, 0) + (p.get("current_value_eur") or 0)
    stock_total = sum(stock_sector_breakdown.values())
    if stock_total == 0:
        return []
    alerts = []
    for sector, val in stock_sector_breakdown.items():
        pct = (val / stock_total) * 100
        if pct > HEALTH_SECTOR_THRESHOLD:
            alerts.append({
                "type": "sector",
                "severity": "warn",
                "message": f"Stock sector concentration: {sector} is {pct:.1f}% of stock holdings (threshold {HEALTH_SECTOR_THRESHOLD}%)",
                "current_value": pct,
                "threshold": float(HEALTH_SECTOR_THRESHOLD),
                "triggering_positions": None,
            })
    return alerts


def _check_drawdown(positions: list) -> dict | None:
    """HEALTH-03: Warn when portfolio YTD return is below HEALTH_DRAWDOWN_THRESHOLD.

    Uses weighted average of perf_ytd by current_value_eur as a proxy for drawdown.
    """
    total_value = sum(p.get("current_value_eur", 0) or 0 for p in positions)
    if total_value == 0:
        return None

    weighted_ytd = sum(
        (p.get("perf_ytd") or 0) * (p.get("current_value_eur", 0) or 0)
        for p in positions
    )
    portfolio_ytd = weighted_ytd / total_value

    if portfolio_ytd < HEALTH_DRAWDOWN_THRESHOLD:
        return {
            "type": "drawdown",
            "severity": "warn",
            "message": f"Portfolio YTD return is {portfolio_ytd:+.1f}% (threshold {HEALTH_DRAWDOWN_THRESHOLD}%)",
            "current_value": portfolio_ytd,
            "threshold": float(HEALTH_DRAWDOWN_THRESHOLD),
            "triggering_positions": None,
        }
    return None


def _check_rebalancing(etf_pct: float, stock_pct: float) -> dict | None:
    """HEALTH-04: Warn when ETF/stock allocation drifts beyond HEALTH_REBALANCE_THRESHOLD."""
    etf_drift = abs(etf_pct - TARGET_ETF_PCT)
    stock_drift = abs(stock_pct - TARGET_STOCK_PCT)

    if etf_drift > HEALTH_REBALANCE_THRESHOLD or stock_drift > HEALTH_REBALANCE_THRESHOLD:
        return {
            "type": "rebalancing",
            "severity": "warn",
            "message": (
                f"ETF allocation at {etf_pct:.1f}% (target {TARGET_ETF_PCT}%, drift {etf_drift:.1f}pp), "
                f"Stock at {stock_pct:.1f}% (target {TARGET_STOCK_PCT}%, drift {stock_drift:.1f}pp)"
            ),
            "current_value": etf_pct,
            "threshold": float(HEALTH_REBALANCE_THRESHOLD),
            "triggering_positions": None,
        }
    return None
