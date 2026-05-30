"""
Cash-Flow Rebalancing Planner — pure allocation logic.

Takes an enriched portfolio dict + a cash amount (EUR), returns a buy-only
plan that corrects allocation drift by directing new contributions.

Pure function — no I/O, no network, no side effects.
"""

import os
import math
from typing import Any

# Config — mirrors health_checks.py pattern
TARGET_ETF_PCT = int(os.getenv("TARGET_ETF_PCT", "70"))
TARGET_STOCK_PCT = int(os.getenv("TARGET_STOCK_PCT", "30"))
POSITION_THRESHOLD = int(os.getenv("HEALTH_POSITION_THRESHOLD", "20"))
SECTOR_THRESHOLD = int(os.getenv("HEALTH_SECTOR_THRESHOLD", "40"))


def plan_contribution(portfolio: dict[str, Any], amount_eur: float) -> dict[str, Any]:
    """
    Compute a buy-only allocation for `amount_eur` across owned positions.

    Algorithm:
      1. Split budget across asset classes (ETF/STOCK) proportional to drift gap
      2. Rank candidates within each class (drift-then-rank)
      3. Snap to whole shares with greedy top-up
      4. Hold reserve for un-deployable cash

    Returns a plan dict matching the RebalancePlanResponse schema.
    """
    if amount_eur <= 0:
        return _empty_plan(amount_eur, "Amount must be positive")

    positions = portfolio.get("positions", [])
    if not positions:
        return _empty_plan(amount_eur, "No positions in portfolio")

    total_value = portfolio.get("total_value_eur", 0)
    if total_value <= 0:
        return _empty_plan(amount_eur, "Portfolio has zero value")

    etf_alloc = portfolio.get("etf_allocation_pct", 0)
    stock_alloc = portfolio.get("stock_allocation_pct", 0)

    # Build sector breakdown from positions
    sector_values = _compute_sector_values(positions)

    # Split positions by asset type, filter out unbuyable ones
    etf_positions, stock_positions, excluded = _partition_positions(positions)

    # Step 1: Split budget across asset classes
    etf_budget, stock_budget = _split_budget_by_drift(
        amount_eur, total_value,
        etf_positions, stock_positions,
        etf_alloc, stock_alloc,
    )

    # Step 2+3: Rank and allocate within each class
    # Use future total for concentration cap checks (portfolio AFTER contribution)
    future_total = total_value + amount_eur

    etf_buys, etf_spent = _allocate_budget(
        etf_positions, etf_budget, future_total, sector_values, sector_threshold=SECTOR_THRESHOLD,
    )
    stock_buys, stock_spent = _allocate_budget(
        stock_positions, stock_budget, future_total, sector_values, sector_threshold=SECTOR_THRESHOLD,
    )

    all_buys = etf_buys + stock_buys
    total_spent = etf_spent + stock_spent
    hold_reserve = round(amount_eur - total_spent, 2)

    # Reconcile — floating point safety
    if hold_reserve < 0:
        hold_reserve = 0.0

    # Hold reasons
    hold_reasons = _compute_hold_reasons(
        hold_reserve, all_buys, etf_positions + stock_positions,
        etf_budget, stock_budget, etf_spent, stock_spent,
    )

    # Projected allocation after buys
    projected = _project_allocation(
        total_value, amount_eur,
        etf_alloc, stock_alloc,
        etf_spent, stock_spent,
    )

    # Warnings
    warnings = _collect_warnings(all_buys, etf_positions, stock_positions,
                                  etf_budget, stock_budget, etf_spent, stock_spent)

    return {
        "amount_requested": amount_eur,
        "currency": "EUR",
        "buys": all_buys,
        "hold_reserve_eur": hold_reserve,
        "hold_reasons": hold_reasons,
        "projected": projected,
        "excluded": excluded,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Step 1: Budget split by drift
# ---------------------------------------------------------------------------

def _split_budget_by_drift(
    amount: float,
    total_value: float,
    etf_positions: list[dict],
    stock_positions: list[dict],
    etf_alloc_pct: float,
    stock_alloc_pct: float,
) -> tuple[float, float]:
    """Split amount across ETF/STOCK proportional to drift gap."""
    current_etf_value = sum(p.get("current_value_eur", 0) for p in etf_positions)
    current_stock_value = sum(p.get("current_value_eur", 0) for p in stock_positions)

    future_total = total_value + amount

    # How much each side *should* have after the contribution
    target_etf = future_total * (TARGET_ETF_PCT / 100)
    target_stock = future_total * (TARGET_STOCK_PCT / 100)

    etf_gap = max(0, target_etf - current_etf_value)
    stock_gap = max(0, target_stock - current_stock_value)

    total_gap = etf_gap + stock_gap

    if total_gap > 0:
        # Split proportional to gap — each side capped at its gap
        etf_budget = min(etf_gap, amount * (etf_gap / total_gap))
        stock_budget = min(stock_gap, amount * (stock_gap / total_gap))
    else:
        # Already at target — split by target weights to preserve allocation
        etf_budget = amount * (TARGET_ETF_PCT / 100)
        stock_budget = amount * (TARGET_STOCK_PCT / 100)

    # Ensure we don't exceed total
    if etf_budget + stock_budget > amount:
        scale = amount / (etf_budget + stock_budget)
        etf_budget *= scale
        stock_budget *= scale

    return round(etf_budget, 2), round(stock_budget, 2)


# ---------------------------------------------------------------------------
# Step 2+3: Rank candidates and allocate
# ---------------------------------------------------------------------------

def _allocate_budget(
    positions: list[dict],
    budget: float,
    total_value: float,
    sector_values: dict[str, float],
    sector_threshold: float,
) -> tuple[list[dict], float]:
    """
    Rank positions by priority, compute weight-based allocations across ALL
    candidates simultaneously, snap to whole shares, then redistribute leftover.

    The key fix: instead of spending sequentially (first position gobbles budget),
    we compute proportional ideal amounts for every candidate at once, then snap
    to whole shares. Leftover from snapping is redistributed via greedy top-up.

    Returns (buys_list, total_spent).
    """
    if not positions or budget <= 0:
        return [], 0.0

    # Rank: concentration-safe first, then sector relief, then buy_priority_score
    ranked = _rank_candidates(positions, sector_values, sector_threshold, total_value)

    # ── Phase 1: Compute ideal proportional allocation for ALL candidates ──
    # Each candidate gets a weight; allocation is budget × (weight / sum_weights)
    weights: list[tuple[dict, float]] = []
    for pos in ranked:
        price_eur = _price_per_share_eur(pos)
        if price_eur is None or price_eur <= 0:
            continue

        weight = pos.get("weight", 0)
        # Skip positions already at or above concentration cap
        if weight >= POSITION_THRESHOLD:
            continue

        # Skip positions that are already well-represented (>5% of portfolio)
        # They'll only get shares via greedy top-up if budget remains
        if weight > 5.0:
            continue

        # Compute allocation weight: inverse of current weight (underweight = more allocation)
        # Quadratic headroom: positions far below cap get disproportionately more
        headroom = max(0.01, POSITION_THRESHOLD - weight)
        base = (headroom / POSITION_THRESHOLD) ** 1.5  # 0..1, steeper for low-weight

        # Sector bonus: under-represented sectors get a boost
        sector = pos.get("sector") or "Unknown"
        total_sector_val = sector_values.get(sector, 0)
        sector_pct = (total_sector_val / total_value * 100) if total_value > 0 else 0
        sector_bonus = 0.4 if sector_pct < sector_threshold else 0.0

        # Quality bonus: quality-gated positions get strong preference
        score = pos.get("buy_priority_score")
        if score is not None:
            quality_bonus = 0.5 + score * 0.3  # 0.5 base + up to 0.3 more
        else:
            quality_bonus = 0.0  # No quality gate = deprioritized

        factor = base + sector_bonus + quality_bonus
        factor = max(0.01, min(2.0, factor))
        weights.append((pos, factor))

    if not weights:
        return [], 0.0

    # ── Trim to top N candidates (avoid migajas) ──
    # Minimum €150 per position — below that, spreading too thin.
    # So N_max = budget / 150, capped at 6. Always keep at least 2.
    MIN_SPEND_PER_POS = 150.0
    max_candidates = max(2, min(6, int(budget / MIN_SPEND_PER_POS)))

    # Sort by weight desc (highest weight = highest priority) and keep top N
    weights.sort(key=lambda x: x[1], reverse=True)
    if len(weights) > max_candidates:
        weights = weights[:max_candidates]

    total_weight = sum(w for _, w in weights)

    # ── Phase 2: Allocate budget proportionally, snap to whole shares ──
    buys = []
    spent = 0.0
    allocated_ids = set()

    for pos, w in weights:
        share_of_budget = budget * (w / total_weight)
        price_eur = _price_per_share_eur(pos)
        if price_eur is None or price_eur <= 0:
            continue

        # Cap by concentration limit
        max_spend = _max_spend_under_cap(pos, total_value, POSITION_THRESHOLD)
        ideal_eur = min(share_of_budget, max_spend)

        shares = max(0, math.floor(ideal_eur / price_eur))
        spend = round(shares * price_eur, 2) if shares > 0 else 0.0

        if shares > 0 and spend > 0:
            buys.append({
                "name": pos.get("name", ""),
                "symbol": pos.get("symbol", ""),
                "isin": pos.get("isin", ""),
                "asset_type": pos.get("asset_type", ""),
                "shares": shares,
                "price_eur": round(price_eur, 2),
                "spend_eur": spend,
                "notional_target_eur": round(share_of_budget, 2),
                "reason": _buy_reason(pos, etf_alloc=None, total_value=total_value),
                "new_weight_pct": round(_projected_weight(pos, spend, total_value), 1),
                "buy_priority_score": pos.get("buy_priority_score"),
                "sector": pos.get("sector") or "Unknown",
            })
            spent += spend
            allocated_ids.add(pos.get("symbol", ""))

    remaining = round(budget - spent, 2)

    # ── Phase 3: Greedy top-up with leftover (one share at a time) ──
    # Redistribute leftover to already-allocated positions, then unallocated ones
    for _round in range(3):  # Max 3 passes to avoid infinite loops
        if remaining < 0.01:
            break
        improved = False
        for pos, w in weights:
            if remaining < 0.01:
                break
            price_eur = _price_per_share_eur(pos)
            if price_eur is None or price_eur <= 0 or price_eur > remaining:
                continue

            existing = next((b for b in buys if b["symbol"] == pos.get("symbol")), None)
            current_spend = existing["spend_eur"] if existing else 0
            new_total_spend = current_spend + price_eur

            new_weight = _projected_weight(pos, new_total_spend, total_value)
            if new_weight > POSITION_THRESHOLD:
                continue

            if existing:
                existing["shares"] += 1
                existing["spend_eur"] = round(existing["spend_eur"] + price_eur, 2)
                existing["new_weight_pct"] = round(new_weight, 1)
            else:
                buys.append({
                    "name": pos.get("name", ""),
                    "symbol": pos.get("symbol", ""),
                    "isin": pos.get("isin", ""),
                    "asset_type": pos.get("asset_type", ""),
                    "shares": 1,
                    "price_eur": round(price_eur, 2),
                    "spend_eur": round(price_eur, 2),
                    "notional_target_eur": round(price_eur, 2),
                    "reason": _buy_reason(pos, etf_alloc=None, total_value=total_value),
                    "new_weight_pct": round(new_weight, 1),
                    "buy_priority_score": pos.get("buy_priority_score"),
                    "sector": pos.get("sector") or "Unknown",
                })

            spent += price_eur
            remaining = round(remaining - price_eur, 2)
            improved = True

        if not improved:
            break

    return buys, round(spent, 2)


def _rank_candidates(
    positions: list[dict],
    sector_values: dict[str, float],
    sector_threshold: float,
    total_value: float,
) -> list[dict]:
    """
    Sort positions by priority:
    1. Hard: under concentration cap (always first)
    2. Soft: sector relief (under-represented sectors ranked higher)
    3. Tie-break: buy_priority_score desc (None last)
    """
    def sort_key(pos):
        # Concentration: lower weight = more room to buy
        weight = pos.get("weight", 0)
        over_cap = 1 if weight >= POSITION_THRESHOLD else 0

        # Sector: under-threshold sectors get priority
        sector = pos.get("sector") or "Unknown"
        total_sector_val = sector_values.get(sector, 0)
        sector_pct = (total_sector_val / total_value * 100) if total_value > 0 else 0
        over_sector = 1 if sector_pct > sector_threshold else 0

        # Quality: buy_priority_score (higher = better entry), None goes last
        score = pos.get("buy_priority_score")
        score_val = score if score is not None else -1

        return (over_cap, over_sector, -score_val)

    return sorted(positions, key=sort_key)


# (allocation weight logic is now inline in _allocate_budget Phase 1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _price_per_share_eur(pos: dict) -> float | None:
    """Derive per-share EUR price from existing portfolio data (no FX call)."""
    qty = pos.get("quantity", 0)
    val_eur = pos.get("current_value_eur", 0)
    if qty and qty > 0 and val_eur and val_eur > 0:
        return val_eur / qty
    # Fallback to current_price (may be in local currency — less accurate)
    price = pos.get("current_price")
    currency = pos.get("currency", "EUR")
    if price and price > 0 and currency == "EUR":
        return price
    return None


def _projected_weight(pos: dict, additional_spend: float, total_value: float) -> float:
    """Weight % after buying additional_spend worth of this position."""
    current_val = pos.get("current_value_eur", 0)
    new_val = current_val + additional_spend
    return (new_val / total_value * 100) if total_value > 0 else 0


def _max_spend_under_cap(pos: dict, total_value: float, cap: float) -> float:
    """Max EUR spend without pushing position above cap %."""
    current_val = pos.get("current_value_eur", 0)
    max_val = total_value * (cap / 100)
    return max(0, max_val - current_val)


def _compute_sector_values(positions: list[dict]) -> dict[str, float]:
    """Sum current_value_eur per sector."""
    result: dict[str, float] = {}
    for p in positions:
        sector = p.get("sector") or "Unknown"
        result[sector] = result.get(sector, 0) + p.get("current_value_eur", 0)
    return result


def _partition_positions(
    positions: list[dict],
) -> tuple[list[dict], list[dict], list[dict]]:
    """Split into (buyable_etfs, buyable_stocks, excluded)."""
    etfs, stocks, excluded = [], [], []
    for p in positions:
        # Exclude positions we can't price
        price_eur = _price_per_share_eur(p)
        if price_eur is None or price_eur <= 0:
            excluded.append({"name": p.get("name", ""), "symbol": p.get("symbol", ""),
                             "reason": "no_eur_price"})
            continue

        qty = p.get("quantity", 0)
        if qty <= 0:
            excluded.append({"name": p.get("name", ""), "symbol": p.get("symbol", ""),
                             "reason": "zero_quantity"})
            continue

        asset_type = p.get("asset_type", "STOCK")
        if asset_type == "ETF":
            etfs.append(p)
        else:
            stocks.append(p)

    return etfs, stocks, excluded


def _buy_reason(pos: dict, etf_alloc: float | None, total_value: float) -> str:
    """Human-readable reason for why this position was selected."""
    parts = []
    score = pos.get("buy_priority_score")
    if score is not None:
        parts.append(f"buy_priority {score:.2f}")
    else:
        parts.append("no quality gate (deprioritized)")

    weight = pos.get("weight", 0)
    if weight < 5:
        parts.append("underweight")
    sector = pos.get("sector") or "Unknown"
    parts.append(f"sector: {sector}")

    return "; ".join(parts)


def _compute_hold_reasons(
    hold_reserve: float,
    buys: list[dict],
    all_candidates: list[dict],
    etf_budget: float,
    stock_budget: float,
    etf_spent: float,
    stock_spent: float,
) -> list[dict]:
    """Tag hold reserve with reasons."""
    if hold_reserve <= 0.01:
        return []

    reasons = []

    # Check if leftover is too small for any share
    if buys:
        min_price = min(b["price_eur"] for b in buys)
        if hold_reserve < min_price:
            reasons.append({"amount_eur": hold_reserve, "reason": "leftover"})
            return reasons

    # Check if all candidates are gated
    ungated = [p for p in all_candidates if p.get("buy_priority_score") is not None]
    if not ungated and all_candidates:
        reasons.append({"amount_eur": hold_reserve, "reason": "all-candidates-overbought"})
        return reasons

    # Check if targets are reached
    if etf_budget > 0 and etf_spent < etf_budget * 0.5:
        pass  # Didn't deploy most of ETF budget
    if stock_budget > 0 and stock_spent < stock_budget * 0.5:
        pass

    # Default: leftover
    reasons.append({"amount_eur": hold_reserve, "reason": "leftover"})
    return reasons


def _project_allocation(
    total_value: float,
    amount: float,
    etf_alloc_before: float,
    stock_alloc_before: float,
    etf_spent: float,
    stock_spent: float,
) -> dict:
    """Compute projected ETF/STOCK allocation after buys."""
    future_total = total_value + etf_spent + stock_spent

    current_etf_value = total_value * (etf_alloc_before / 100)
    current_stock_value = total_value * (stock_alloc_before / 100)

    etf_after = ((current_etf_value + etf_spent) / future_total * 100) if future_total > 0 else 0
    stock_after = ((current_stock_value + stock_spent) / future_total * 100) if future_total > 0 else 0

    return {
        "etf_allocation_pct": round(etf_after, 1),
        "stock_allocation_pct": round(stock_after, 1),
        "etf_drift_before": round(etf_alloc_before - TARGET_ETF_PCT, 1),
        "etf_drift_after": round(etf_after - TARGET_ETF_PCT, 1),
        "stock_drift_before": round(stock_alloc_before - TARGET_STOCK_PCT, 1),
        "stock_drift_after": round(stock_after - TARGET_STOCK_PCT, 1),
    }


def _collect_warnings(
    buys: list[dict],
    etf_positions: list[dict],
    stock_positions: list[dict],
    etf_budget: float,
    stock_budget: float,
    etf_spent: float,
    stock_spent: float,
) -> list[str]:
    warnings = []

    # All quality-gated candidates
    if buys:
        gated_buys = [b for b in buys if b.get("buy_priority_score") is None]
        if len(gated_buys) == len(buys) and len(buys) > 0:
            warnings.append("All buys are from quality-gated positions — entries may not be optimal")

    # Undeployed budget
    if etf_budget > 0 and etf_spent < etf_budget * 0.5:
        warnings.append(f"Only €{etf_spent:.0f} of €{etf_budget:.0f} ETF budget deployed")
    if stock_budget > 0 and stock_spent < stock_budget * 0.5:
        warnings.append(f"Only €{stock_spent:.0f} of €{stock_budget:.0f} stock budget deployed")

    return warnings


def _empty_plan(amount_eur: float, message: str) -> dict:
    """Return an empty plan with full hold reserve."""
    return {
        "amount_requested": amount_eur,
        "currency": "EUR",
        "buys": [],
        "hold_reserve_eur": amount_eur,
        "hold_reasons": [{"amount_eur": amount_eur, "reason": message}],
        "projected": {
            "etf_allocation_pct": 0,
            "stock_allocation_pct": 0,
            "etf_drift_before": 0,
            "etf_drift_after": 0,
            "stock_drift_before": 0,
            "stock_drift_after": 0,
        },
        "excluded": [],
        "warnings": [message],
    }
