"""Tests for the Hermes context builder watchlist section."""
import sys
sys.path.insert(0, 'app')
from app.context_builder import build_hermes_context


def test_watchlist_appears_in_json_and_plaintext():
    portfolio = {
        "positions": [], "top_candidates": {"etfs": [], "stocks": []},
        "watchlist": [
            {"name": "NVIDIA", "symbol": "NVDA", "isin": "US67066G1040",
             "asset_type": "STOCK", "buy_priority_score": 0.81, "rsi": 42,
             "distance_from_52w_high_pct": -12.0, "momentum_score": 6.0}
        ],
    }
    ctx = build_hermes_context(portfolio)
    assert ctx["json"]["watchlist"][0]["symbol"] == "NVDA"
    assert "WATCHLIST" in ctx["plaintext"]
    assert "NVDA" in ctx["plaintext"]


def test_empty_watchlist_renders_placeholder():
    ctx = build_hermes_context({"positions": [], "top_candidates": {"etfs": [], "stocks": []}})
    assert ctx["json"]["watchlist"] == []
    assert "WATCHLIST" in ctx["plaintext"]  # section header still present
