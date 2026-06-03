"""Orchestration: enrich watchlist entries and score them in the same pool as owned
positions, then return just the (now-scored) watchlist items.

This is the single shared scoring path used by GET /api/watchlist, the dashboard's
top_candidates merge, the rebalancer display, and the Hermes export — so a watchlist
candidate's buy_priority_score is always directly comparable to owned holdings.
"""
import logging

from .market_data import enrich_watchlist
from .scoring import compute_scores

logger = logging.getLogger(__name__)


def score_universe(owned_positions: list[dict], watchlist_entries: list[dict]) -> list[dict]:
    """Enrich watchlist_entries and score them against owned_positions.

    owned_positions: already-enriched, already-weighted owned holdings (from session).
    watchlist_entries: raw store entries (isin, symbol, name, asset_type).

    Returns the enriched + scored watchlist dicts only. owned_positions provide pool
    context (z-score distribution).
    """
    if not watchlist_entries:
        return []
    enriched_watch = enrich_watchlist(watchlist_entries)
    # Shallow-copy owned dicts: compute_scores mutates in place, and we must not
    # overwrite the live session positions' real (owned-pool) scores with scores
    # computed in this watchlist-augmented pool.
    merged = [dict(p) for p in owned_positions] + enriched_watch
    compute_scores(merged)
    return [p for p in merged if p.get("source") == "watchlist"]
