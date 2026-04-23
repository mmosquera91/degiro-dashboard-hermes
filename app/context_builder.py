"""Hermes context builder — structured JSON and plaintext for AI analysis."""

import logging
import os
from datetime import datetime
from typing import Optional

from .snapshots import load_snapshots, fetch_benchmark_series, compute_attribution

logger = logging.getLogger(__name__)

TARGET_ETF_PCT   = int(os.getenv("TARGET_ETF_PCT", "70"))
TARGET_STOCK_PCT = int(os.getenv("TARGET_STOCK_PCT", "30"))


def build_hermes_context(portfolio: dict) -> dict:
    """Build Hermes-ready context from portfolio data.

    Returns:
        {
            "json": {...},       # Full structured data
            "plaintext": "..."   # Ready-to-paste text block
        }
    """
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    positions = portfolio.get("positions", [])
    top_candidates = portfolio.get("top_candidates", {"etfs": [], "stocks": []})

    # Build JSON structure
    json_context = {
        "snapshot_date": date_str,
        "portfolio_summary": {
            "total_value_eur": portfolio.get("total_value"),
            "total_invested": portfolio.get("total_invested"),
            "total_pl": portfolio.get("total_pl"),
            "total_pl_pct": portfolio.get("total_pl_pct"),
            "etf_allocation_pct": portfolio.get("etf_allocation_pct"),
            "stock_allocation_pct": portfolio.get("stock_allocation_pct"),
            "target_etf_pct": TARGET_ETF_PCT,
            "target_stock_pct": TARGET_STOCK_PCT,
            "allocation_delta_etf": portfolio.get("etf_allocation_pct", 0) - TARGET_ETF_PCT,
            "allocation_delta_stock": portfolio.get("stock_allocation_pct", 0) - TARGET_STOCK_PCT,
            "num_positions": portfolio.get("num_positions"),
            "cash_available": portfolio.get("cash_available"),
        },
        "positions": sorted(positions, key=lambda p: p.get("momentum_score") or 0),
        "top_candidates": top_candidates,
        "health_alerts": portfolio.get("health_alerts", []),
    }

    # Load snapshot data for benchmark comparison
    snapshots = load_snapshots()
    benchmark_data = {"snapshots": [], "benchmark_series": [], "latest_benchmark_return_pct": None}

    if snapshots:
        first_date = snapshots[0]["date"]
        today = datetime.now().strftime("%Y-%m-%d")
        benchmark_series = fetch_benchmark_series(first_date, today)
        latest_benchmark_return_pct = snapshots[-1].get("benchmark_return_pct") if snapshots else None
        benchmark_data = {
            "snapshots": snapshots,
            "benchmark_series": benchmark_series,
            "latest_benchmark_return_pct": latest_benchmark_return_pct,
        }

    # Compute attribution if portfolio is available
    attribution = []
    if positions and snapshots:
        latest_benchmark_return = snapshots[-1].get("benchmark_return_pct", 0)
        attribution = compute_attribution(positions, latest_benchmark_return)

    json_context["benchmark"] = benchmark_data
    json_context["attribution"] = attribution

    # Build plaintext
    plaintext = _build_plaintext(json_context, date_str)

    return {"json": json_context, "plaintext": plaintext}


def _build_plaintext(context: dict, date_str: str) -> str:
    """Build a formatted plaintext block for pasting into Hermes."""
    lines = []

    summary = context["portfolio_summary"]

    lines.append(f"PORTFOLIO CONTEXT FOR ANALYSIS — {date_str}")
    lines.append("")
    lines.append(
        "You are analyzing a long-term investor's DeGiro portfolio. "
        "The investor adds cash periodically and wants to know what to buy next. "
        "Do not recommend selling. Strategy is buy-and-hold. "
        f"The {TARGET_ETF_PCT}/{TARGET_STOCK_PCT} ETF/stock target is a soft guideline, not a hard constraint — "
        "if metrics strongly favor stocks, recommending stocks is valid and encouraged. "
        "Below is the full portfolio data and metrics."
    )
    lines.append("")

    # Portfolio summary
    lines.append("═══ PORTFOLIO SUMMARY ═══")
    lines.append(f"  Total Value:      €{summary['total_value_eur']:,.2f}" if summary.get('total_value_eur') else "  Total Value:      N/A")
    lines.append(f"  Total Invested:   €{summary['total_invested']:,.2f}" if summary.get('total_invested') else "  Total Invested:   N/A")
    lines.append(f"  Total P&L:        €{summary['total_pl']:,.2f} ({summary['total_pl_pct']:+.2f}%)" if summary.get('total_pl') is not None else "  Total P&L:        N/A")
    lines.append(f"  ETF Allocation:   {summary['etf_allocation_pct']:.1f}% (target: {TARGET_ETF_PCT}%)" if summary.get('etf_allocation_pct') is not None else "  ETF Allocation:   N/A")
    lines.append(f"  Stock Allocation: {summary['stock_allocation_pct']:.1f}% (target: {TARGET_STOCK_PCT}%)" if summary.get('stock_allocation_pct') is not None else "  Stock Allocation: N/A")
    lines.append(f"  Positions:        {summary['num_positions']}")
    lines.append(f"  Cash Available:   €{summary['cash_available']:,.2f}" if summary.get('cash_available') is not None else "  Cash Available:   N/A")
    lines.append("")

    # Rebalancing note
    delta_etf = summary.get("allocation_delta_etf", 0) or 0
    delta_stock = summary.get("allocation_delta_stock", 0) or 0
    lines.append("═══ REBALANCING NOTE ═══")
    if delta_etf > 0:
        lines.append(f"  ETFs are {delta_etf:+.1f}pp above target. Stocks are {delta_stock:+.1f}pp below.")
        lines.append("  This is informational — do not block stock recommendations based on this alone.")
    elif delta_etf < 0:
        lines.append(f"  ETFs are {delta_etf:+.1f}pp below target. Stocks are {delta_stock:+.1f}pp above.")
        lines.append("  This is informational — do not block ETF recommendations based on this alone.")
    else:
        lines.append("  Portfolio is at target allocation.")
    lines.append("")

    # Positions table — sorted by momentum score ascending (weakest first)
    positions = context.get("positions", [])
    lines.append("═══ POSITIONS (sorted by momentum, weakest first) ═══")
    lines.append("")

    if positions:
        header = f"{'Name':<30} {'Type':<5} {'Value€':>10} {'P&L%':>8} {'Wt%':>6} {'RSI':>5} {'Mom':>7} {'BuyPr':>6}"
        lines.append(header)
        lines.append("─" * len(header))

        for p in positions:
            name = (p.get("name", "")[:28] or "N/A").ljust(30)
            atype = p.get("asset_type", "?")[:5].ljust(5)
            val_eur = f"{p.get('current_value_eur', 0):,.0f}".rjust(10) if p.get("current_value_eur") else "N/A".rjust(10)
            pl_pct = f"{p.get('unrealized_pl_pct', 0):+.1f}".rjust(8) if p.get("unrealized_pl_pct") is not None else "N/A".rjust(8)
            weight = f"{p.get('weight', 0):.1f}".rjust(6) if p.get("weight") is not None else "N/A".rjust(6)
            rsi = f"{p.get('rsi', 0):.0f}".rjust(5) if p.get("rsi") is not None else "N/A".rjust(5)
            mom = f"{p.get('momentum_score', 0):+.1f}".rjust(7) if p.get("momentum_score") is not None else "N/A".rjust(7)
            buy = f"{p.get('buy_priority_score', 0):.2f}".rjust(6) if p.get("buy_priority_score") is not None else "N/A".rjust(6)

            lines.append(f"{name} {atype} {val_eur} {pl_pct} {weight} {rsi} {mom} {buy}")

        lines.append("")

        # Detailed metrics per position
        lines.append("═══ DETAILED METRICS ═══")
        lines.append("")

        for p in positions:
            lines.append(f"  {p.get('name', 'N/A')} ({p.get('symbol', 'N/A')}) [{p.get('asset_type', '?')}]")
            lines.append(f"    ISIN: {p.get('isin', 'N/A')}  Currency: {p.get('currency', 'N/A')}  Sector: {p.get('sector', 'N/A')}")
            lines.append(f"    Qty: {p.get('quantity', 0)}  Avg Buy: {p.get('avg_buy_price', 'N/A')}  Current: {p.get('current_price', 'N/A')}")
            lines.append(f"    Value: €{p.get('current_value_eur', 0):,.2f}  P&L: €{p.get('unrealized_pl_eur', 0):,.2f} ({p.get('unrealized_pl_pct', 0):+.2f}%)")
            lines.append(f"    52w High/Low: {p.get('52w_high', 'N/A')} / {p.get('52w_low', 'N/A')}  Distance from high: {p.get('distance_from_52w_high_pct', 'N/A')}%")
            lines.append(f"    RSI(14): {p.get('rsi', 'N/A')}  P/E: {p.get('pe_ratio', 'N/A')}")
            lines.append(f"    Perf 30d: {p.get('perf_30d', 'N/A')}%  90d: {p.get('perf_90d', 'N/A')}%  YTD: {p.get('perf_ytd', 'N/A')}%")
            lines.append(f"    Momentum Score: {p.get('momentum_score', 'N/A')}  Value Score: {p.get('value_score', 'N/A')}  Buy Priority: {p.get('buy_priority_score', 'N/A')}")
            lines.append("")

    # Top candidates
    candidates = context.get("top_candidates", {})
    lines.append("═══ TOP BUY CANDIDATES ═══")
    lines.append("")

    lines.append("  ▸ TOP 3 ETF CANDIDATES:")
    for i, c in enumerate(candidates.get("etfs", []), 1):
        lines.append(f"    {i}. {c.get('name', 'N/A')} ({c.get('symbol', 'N/A')})")
        lines.append(f"       Buy Priority: {c.get('buy_priority_score', 'N/A')}  —  {c.get('reason', 'N/A')}")
    if not candidates.get("etfs"):
        lines.append("    No ETF candidates available.")

    lines.append("")
    lines.append("  ▸ TOP 3 STOCK CANDIDATES:")
    for i, c in enumerate(candidates.get("stocks", []), 1):
        lines.append(f"    {i}. {c.get('name', 'N/A')} ({c.get('symbol', 'N/A')})")
        lines.append(f"       Buy Priority: {c.get('buy_priority_score', 'N/A')}  —  {c.get('reason', 'N/A')}")
    if not candidates.get("stocks"):
        lines.append("    No stock candidates available.")

    lines.append("")

    # Benchmark section
    benchmark = context.get("benchmark", {})
    snapshots = benchmark.get("snapshots", [])
    if snapshots:
        first_date = snapshots[0]["date"]
        today = datetime.now().strftime("%Y-%m-%d")
        benchmark_series = fetch_benchmark_series(first_date, today)

        lines.append("═══ BENCHMARK COMPARISON (S&P 500) ═══")
        lines.append("")
        lines.append(f"  Latest Snapshot: {snapshots[-1]['date']}")
        lines.append(f"  Portfolio Value: €{snapshots[-1]['total_value_eur']:,.2f}")
        benchmark_return = snapshots[-1].get('benchmark_return_pct')
        if benchmark_return is not None:
            lines.append(f"  Benchmark Return: {benchmark_return:+.2f}%")
        else:
            lines.append("  Benchmark Return: N/A")
        lines.append(f"  Indexed to 100 at: {first_date}")
        lines.append("")
        lines.append("  Historical Snapshots:")
        for s in snapshots:
            bv = s.get('benchmark_value', 100)
            br = s.get('benchmark_return_pct', 0)
            lines.append(f"    {s['date']}: Portfolio €{s['total_value_eur']:,.2f} | Benchmark {bv:.2f} | Return {br:+.2f}%")

        # Attribution section
        attribution = context.get("attribution", [])
        if attribution:
            lines.append("")
            lines.append("═══ POSITION ATTRIBUTION ═══")
            lines.append("")
            lines.append(f"  {'Position':<30} {'Abs Cont':>12} {'Rel Cont':>12}")
            lines.append("  " + "─" * 56)
            for a in attribution[:15]:  # Top 15 positions
                name = (a.get('name', 'N/A')[:28]).ljust(30)
                abs_c = f"{a.get('absolute_contribution', 0):+.4f}".rjust(12)
                rel_c = f"{a.get('relative_contribution', 0):+.4f}".rjust(12)
                lines.append(f"  {name} {abs_c} {rel_c}")
            lines.append("")
            lines.append("  Absolute: position_return × weight | Relative: (position_return − benchmark_return) × weight × direction")

    lines.append("")
    lines.append(f"— End of context — {date_str}")

    return "\n".join(lines)
