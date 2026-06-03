# Watchlist / Candidate Universe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user track tickers they don't own yet, enrich and score them in the same ETF/STOCK pool as owned holdings, and surface them in a dedicated panel, the top-candidates list, the rebalancer, and the Hermes export.

**Architecture:** A JSON-backed store (`watchlist_store.py`) mirrors the `symbol_overrides.json` pattern (threading.Lock, env-configurable path) but adds an atomic write path. Watchlist entries are resolved to a yfinance ticker + classified ETF/STOCK once at add-time via `market_data.resolve_and_classify`. A single shared scoring helper, `score_universe(owned, watchlist)`, enriches watchlist entries through the existing `enrich_positions` path and runs `compute_scores` over the merged pool, with the weight factor neutralized (0.5) for unowned names. The same helper feeds the dedicated panel (`GET /api/watchlist`), the dashboard's `top_candidates`, the rebalancer display, and the Hermes export.

**Tech Stack:** Python 3 / FastAPI / Pydantic, pytest, yfinance, vanilla JS (CSP-strict: external `/static` only).

**Reference spec:** `docs/superpowers/specs/2026-06-03-watchlist-candidate-universe-design.md`

---

## File Structure

**Create:**
- `app/watchlist_store.py` — persistence: load/add/remove/override/list under a lock with atomic load-modify-write.
- `app/universe.py` — `score_universe(owned, watchlist)` orchestration helper (enrich + merge + score). Kept separate from `scoring.py` so pure scoring math stays untouched by I/O orchestration.
- `tests/test_watchlist_store.py` — store unit tests.
- `tests/test_watchlist_scoring.py` — weight-factor neutralization + `score_universe` tests.
- `tests/test_watchlist_routes.py` — API endpoint + auth-exemption + pipeline-merge tests.
- `tests/test_context_builder.py` — Hermes watchlist-section test (create if absent).
- `app/static/watchlist.js` — watchlist panel client logic (CSP-compliant external JS).

**Modify:**
- `app/scoring.py` — neutralize weight factor for `owned == False`; tag candidates with `owned`. (Pure scoring math only — no orchestration.)
- `app/market_data.py` — add `resolve_and_classify(isin)`; add `enrich_watchlist(entries)`.
- `app/schemas.py` — watchlist request/response models; extend `RebalancePlanResponse`.
- `app/main.py` — five `/api/watchlist*` routes; `GET /api/watchlist` added to cookie exemption; `merge_watchlist_candidates` into `top_candidates`; `build_watchlist_candidate_display` into the rebalance plan; watchlist into the hermes route.
- `app/context_builder.py` — watchlist section in JSON + plaintext export.
- `app/index.html` — watchlist `<details>` panel + script tag.
- `app/static/style.css` — minimal panel styles (reuse rebalance classes where possible).
- `app/static/app.js` — expose `apiFetch` as `window.Brokr.apiFetch` (if not already).
- `README.md` — document the feature.

Note: `app/rebalance.py` is **not** modified — the watchlist display is attached in the `main.py` route, leaving `plan_contribution`'s allocation math untouched.

---

## Part A — Watchlist store

### Task A1: Watchlist store module

**Files:**
- Create: `app/watchlist_store.py`
- Test: `tests/test_watchlist_store.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_watchlist_store.py
"""Unit tests for watchlist_store — JSON-backed watchlist persistence."""
import json
import importlib
import pytest


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Fresh watchlist_store pointed at a temp file."""
    path = tmp_path / "watchlist.json"
    monkeypatch.setenv("WATCHLIST_PATH", str(path))
    import app.watchlist_store as ws
    importlib.reload(ws)
    return ws


def _entry(isin="US0378331005", symbol="AAPL", name="Apple Inc.", asset_type="STOCK"):
    return {"isin": isin, "symbol": symbol, "name": name, "asset_type": asset_type}


class TestAddRemoveList:
    def test_add_then_list_returns_entry(self, store):
        store.add_entry(_entry())
        items = store.list_entries()
        assert len(items) == 1
        assert items[0]["isin"] == "US0378331005"
        assert items[0]["asset_type_source"] == "auto"
        assert items[0]["added_at"]  # stamped

    def test_add_persists_to_disk(self, store, tmp_path):
        store.add_entry(_entry())
        on_disk = json.loads((tmp_path / "watchlist.json").read_text())
        assert on_disk["version"] == 1
        assert on_disk["items"][0]["isin"] == "US0378331005"

    def test_add_duplicate_isin_raises(self, store):
        store.add_entry(_entry())
        with pytest.raises(ValueError, match="already on the watchlist"):
            store.add_entry(_entry())

    def test_add_normalizes_isin_uppercase(self, store):
        store.add_entry(_entry(isin="us0378331005"))
        assert store.list_entries()[0]["isin"] == "US0378331005"

    def test_remove_deletes_entry(self, store):
        store.add_entry(_entry())
        store.remove_entry("US0378331005")
        assert store.list_entries() == []

    def test_remove_missing_isin_raises(self, store):
        with pytest.raises(KeyError):
            store.remove_entry("NONEXISTENT")

    def test_cap_rejects_31st_add(self, store):
        for i in range(30):
            store.add_entry(_entry(isin=f"ISIN{i:010d}", symbol=f"S{i}"))
        with pytest.raises(ValueError, match="maximum of 30"):
            store.add_entry(_entry(isin="ISIN0000000099", symbol="OVER"))


class TestOverride:
    def test_set_asset_type_marks_manual(self, store):
        store.add_entry(_entry(asset_type="STOCK"))
        store.set_asset_type("US0378331005", "ETF")
        e = store.list_entries()[0]
        assert e["asset_type"] == "ETF"
        assert e["asset_type_source"] == "manual"

    def test_set_asset_type_rejects_bad_value(self, store):
        store.add_entry(_entry())
        with pytest.raises(ValueError, match="ETF or STOCK"):
            store.set_asset_type("US0378331005", "CRYPTO")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_watchlist_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.watchlist_store'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/watchlist_store.py
"""JSON-backed watchlist store.

Mirrors the symbol_overrides persistence pattern (module-level threading.Lock,
env-configurable path) but adds an atomic write path: every mutation re-reads the
file, mutates, and writes back inside the lock so concurrent add/remove calls do
not lose updates.
"""
import json
import logging
import os
import pathlib
import threading
from datetime import date

logger = logging.getLogger(__name__)

WATCHLIST_PATH = pathlib.Path(os.environ.get("WATCHLIST_PATH", "/data/watchlist.json"))
MAX_ENTRIES = 30
_VALID_TYPES = {"ETF", "STOCK"}
_lock = threading.Lock()


def _read_unlocked() -> dict:
    """Read the watchlist file. Caller holds _lock. Returns {version, items}."""
    if not WATCHLIST_PATH.exists():
        return {"version": 1, "items": []}
    try:
        content = WATCHLIST_PATH.read_text().strip()
        if not content:
            return {"version": 1, "items": []}
        data = json.loads(content)
        if not isinstance(data, dict) or "items" not in data:
            logger.warning("Malformed watchlist file — starting empty")
            return {"version": 1, "items": []}
        return data
    except Exception as e:
        logger.warning("Failed to read watchlist: %s", e)
        return {"version": 1, "items": []}


def _write_unlocked(data: dict) -> None:
    """Write the watchlist file. Caller holds _lock."""
    WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    WATCHLIST_PATH.write_text(json.dumps(data, indent=2))


def list_entries() -> list[dict]:
    """Return a copy of the watchlist entries."""
    with _lock:
        return list(_read_unlocked()["items"])


def add_entry(entry: dict) -> dict:
    """Add an entry (atomic). entry needs isin, symbol, name, asset_type.

    Stamps asset_type_source='auto', note='', added_at=today. Raises ValueError on
    duplicate or cap breach.
    """
    isin = (entry.get("isin") or "").strip().upper()
    if not isin:
        raise ValueError("ISIN is required")
    with _lock:
        data = _read_unlocked()
        items = data["items"]
        if len(items) >= MAX_ENTRIES:
            raise ValueError(f"Watchlist is at its maximum of {MAX_ENTRIES} entries")
        if any(it["isin"] == isin for it in items):
            raise ValueError(f"{isin} is already on the watchlist")
        record = {
            "isin": isin,
            "symbol": entry.get("symbol", ""),
            "name": entry.get("name", ""),
            "asset_type": entry.get("asset_type", "STOCK"),
            "asset_type_source": entry.get("asset_type_source", "auto"),
            "note": entry.get("note", ""),
            "added_at": date.today().isoformat(),
        }
        items.append(record)
        _write_unlocked(data)
        return record


def remove_entry(isin: str) -> None:
    """Remove the entry with the given ISIN (atomic). Raises KeyError if absent."""
    isin = (isin or "").strip().upper()
    with _lock:
        data = _read_unlocked()
        before = len(data["items"])
        data["items"] = [it for it in data["items"] if it["isin"] != isin]
        if len(data["items"]) == before:
            raise KeyError(isin)
        _write_unlocked(data)


def set_asset_type(isin: str, asset_type: str) -> dict:
    """Override an entry's asset_type and mark it manual (atomic)."""
    isin = (isin or "").strip().upper()
    asset_type = (asset_type or "").strip().upper()
    if asset_type not in _VALID_TYPES:
        raise ValueError("asset_type must be ETF or STOCK")
    with _lock:
        data = _read_unlocked()
        for it in data["items"]:
            if it["isin"] == isin:
                it["asset_type"] = asset_type
                it["asset_type_source"] = "manual"
                _write_unlocked(data)
                return it
        raise KeyError(isin)


def update_resolution(isin: str, symbol: str, name: str, asset_type: str,
                      keep_manual_type: bool = True) -> dict:
    """Update symbol/name/asset_type after a re-resolution (atomic).

    If keep_manual_type and the entry's asset_type_source is 'manual', the
    asset_type is preserved (only symbol/name refreshed).
    """
    isin = (isin or "").strip().upper()
    with _lock:
        data = _read_unlocked()
        for it in data["items"]:
            if it["isin"] == isin:
                it["symbol"] = symbol
                it["name"] = name or it.get("name", "")
                if not (keep_manual_type and it.get("asset_type_source") == "manual"):
                    it["asset_type"] = asset_type
                    it["asset_type_source"] = "auto"
                _write_unlocked(data)
                return it
        raise KeyError(isin)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_watchlist_store.py -v`
Expected: PASS (all tests green)

- [ ] **Step 5: Commit**

```bash
git add app/watchlist_store.py tests/test_watchlist_store.py
git commit -m "feat(watchlist): JSON-backed store with atomic load-modify-write"
```

---

## Part B — Scoring & enrichment

### Task B1: Neutralize weight factor for unowned names

**Files:**
- Modify: `app/scoring.py` (the weight-factor block, lines ~242-251, and the candidate dict builders ~358-386)
- Test: `tests/test_watchlist_scoring.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_watchlist_scoring.py
"""Watchlist scoring: weight factor is neutral 0.5 for owned == False entries."""
import sys
sys.path.insert(0, 'app')
from scoring import compute_scores, get_top_candidates


def _etf(isin, weight, owned=True):
    """An ETF with all non-weight factors absent (→ 0.5) so buy_priority isolates weight."""
    return {
        "isin": isin, "symbol": isin, "name": isin, "asset_type": "ETF",
        "weight": weight, "owned": owned,
        # everything else None → normalizes to 0.5
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
    # The watchlist item's weight=0 must NOT distort owned items' weight z-score.
    owned_only = [_etf(f"OWN{i}", float(i)) for i in range(1, 5)]
    compute_scores(owned_only)
    baseline = {p["isin"]: p["buy_priority_score"] for p in owned_only}

    owned_with_watch = [_etf(f"OWN{i}", float(i)) for i in range(1, 5)]
    compute_scores(owned_with_watch + [_etf("WATCH", 0.0, owned=False)])
    after = {p["isin"]: p["buy_priority_score"] for p in owned_with_watch}
    # Non-weight factors are all 0.5 regardless of pool membership, and the weight
    # factor is computed over owned-only in both runs → owned scores are unchanged.
    assert after == baseline


def test_candidates_tagged_with_owned_flag():
    pool = [_etf(f"OWN{i}", float(i)) for i in range(1, 5)]
    watch = _etf("WATCH", 0.0, owned=False)
    scored = compute_scores(pool + [watch])
    cands = get_top_candidates(scored, n=10)
    by_isin = {c["isin"]: c for c in cands["etfs"]}
    assert by_isin["WATCH"]["owned"] is False
    assert by_isin["OWN1"]["owned"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_watchlist_scoring.py -v`
Expected: FAIL — watchlist item's weight factor currently uses weight 0 (maxes the factor), so `buy_priority_score != 0.5`; and candidate dicts have no `owned` key (`KeyError`).

- [ ] **Step 3: Implement — replace the weight-factor block in `compute_scores`**

In `app/scoring.py`, replace the existing weight block (currently):

```python
        # weight
        weights = [p.get("weight", 0) or 0 for p in pool]
        weight_none_mask = [w is None for w in weights]
        weight_clean = [w for w in weights if w is not None]
        norm_weight_inv = _zscore_normalize([-w for w in weight_clean]) if weight_clean else [0.5]
        norm_weight_full = []
        ni = 0
        for has_none in weight_none_mask:
            norm_weight_full.append(0.5 if has_none else norm_weight_inv[ni])
            if not has_none:
                ni += 1
```

with:

```python
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
```

- [ ] **Step 4: Implement — tag candidate dicts with `owned`**

In `app/scoring.py`, in `get_top_candidates`, add `"owned": p.get("owned", True),` to BOTH the `top_etfs.append({...})` and `top_stocks.append({...})` dicts (alongside the existing `"weight"` key).

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/test_watchlist_scoring.py tests/test_scoring.py -v`
Expected: PASS — new tests green AND existing `test_scoring.py` still green (owned-only behavior unchanged because `owned` defaults True and owned_weights == all weights).

- [ ] **Step 6: Commit**

```bash
git add app/scoring.py tests/test_watchlist_scoring.py
git commit -m "feat(scoring): neutral weight factor for unowned watchlist names; tag candidates with owned"
```

---

### Task B2: Resolve + classify an ISIN at add-time

**Files:**
- Modify: `app/market_data.py` (add `resolve_and_classify` near `_resolve_by_isin`, ~line 274)
- Test: `tests/test_market_data.py` (append a class)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_market_data.py — append
import sys
sys.path.insert(0, 'app')


class TestResolveAndClassify:
    def test_returns_symbol_name_and_etf_type(self, monkeypatch):
        import app.market_data as md

        monkeypatch.setattr(md, "_resolve_by_isin", lambda isin, position_currency="EUR": "SXRU.AS")

        class FakeTicker:
            info = {"quoteType": "ETF", "shortName": "iShares S&P 500", "longName": "iShares Core S&P 500 UCITS ETF"}

        monkeypatch.setattr(md.yf, "Ticker", lambda s: FakeTicker())
        out = md.resolve_and_classify("IE00B5BMR087")
        assert out == {"symbol": "SXRU.AS", "name": "iShares Core S&P 500 UCITS ETF", "asset_type": "ETF"}

    def test_equity_maps_to_stock(self, monkeypatch):
        import app.market_data as md
        monkeypatch.setattr(md, "_resolve_by_isin", lambda isin, position_currency="EUR": "AAPL")

        class FakeTicker:
            info = {"quoteType": "EQUITY", "shortName": "Apple Inc."}

        monkeypatch.setattr(md.yf, "Ticker", lambda s: FakeTicker())
        out = md.resolve_and_classify("US0378331005")
        assert out["asset_type"] == "STOCK"
        assert out["symbol"] == "AAPL"
        assert out["name"] == "Apple Inc."

    def test_unresolvable_isin_raises(self, monkeypatch):
        import app.market_data as md
        monkeypatch.setattr(md, "_resolve_by_isin", lambda isin, position_currency="EUR": "")
        with pytest.raises(ValueError, match="Could not resolve"):
            md.resolve_and_classify("XX0000000000")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_market_data.py::TestResolveAndClassify -v`
Expected: FAIL — `AttributeError: module 'app.market_data' has no attribute 'resolve_and_classify'`

- [ ] **Step 3: Write implementation**

Add to `app/market_data.py` (after `_resolve_by_isin`):

```python
def resolve_and_classify(isin: str, position_currency: str = "EUR") -> dict:
    """Resolve an ISIN to a yfinance ticker and classify it ETF vs STOCK.

    Used by the watchlist add/resolve flow. Returns {symbol, name, asset_type}.
    Raises ValueError if the ISIN cannot be resolved.
    """
    symbol = _resolve_by_isin(isin, position_currency=position_currency)
    if not symbol:
        raise ValueError(f"Could not resolve ISIN {isin} to a ticker")
    name = ""
    asset_type = "STOCK"
    try:
        info = yf.Ticker(symbol).info or {}
        quote_type = str(info.get("quoteType", "")).upper()
        asset_type = "ETF" if quote_type == "ETF" else "STOCK"
        name = info.get("longName") or info.get("shortName") or ""
    except Exception as e:
        logger.warning("Classification of %s (%s) failed, defaulting STOCK: %s", isin, symbol, e)
    return {"symbol": symbol, "name": name, "asset_type": asset_type}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_market_data.py::TestResolveAndClassify -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/market_data.py tests/test_market_data.py
git commit -m "feat(market-data): resolve_and_classify for watchlist add flow"
```

---

### Task B3: Enrich watchlist entries

**Files:**
- Modify: `app/market_data.py` (add `enrich_watchlist`)
- Test: `tests/test_market_data.py` (append a class)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_market_data.py — append
class TestEnrichWatchlist:
    def test_builds_position_dicts_and_enriches(self, monkeypatch):
        import app.market_data as md

        captured = {}

        def fake_enrich_positions(raw):
            captured["positions"] = raw["positions"]
            # Simulate enrichment stamping a price/RSI
            for p in raw["positions"]:
                p["current_price"] = 100.0
                p["rsi"] = 55.0
            return raw["positions"]

        monkeypatch.setattr(md, "enrich_positions", fake_enrich_positions)

        entries = [{"isin": "US0378331005", "symbol": "AAPL", "name": "Apple", "asset_type": "STOCK"}]
        out = md.enrich_watchlist(entries)

        # Built a position-like dict with the watchlist markers
        built = captured["positions"][0]
        assert built["symbol"] == "AAPL"
        assert built["quantity"] == 0
        assert built["owned"] is False
        assert built["source"] == "watchlist"
        # Enrichment results flow through
        assert out[0]["rsi"] == 55.0

    def test_empty_list_returns_empty(self, monkeypatch):
        import app.market_data as md
        assert md.enrich_watchlist([]) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_market_data.py::TestEnrichWatchlist -v`
Expected: FAIL — no attribute `enrich_watchlist`

- [ ] **Step 3: Write implementation**

Add to `app/market_data.py`:

```python
def enrich_watchlist(entries: list[dict]) -> list[dict]:
    """Enrich watchlist entries through the same path as owned positions.

    Each entry (isin, symbol, name, asset_type) becomes a position-like dict with
    quantity 0, weight 0, owned=False, source='watchlist', then runs through
    enrich_positions (batch yfinance history + fundamentals). Returns the enriched
    dicts (RSI / perf / 52w / P-E / sector / current_price populated).
    """
    if not entries:
        return []
    positions = [
        {
            "isin": e.get("isin", ""),
            "symbol": e.get("symbol", ""),
            "name": e.get("name", ""),
            "asset_type": e.get("asset_type", "STOCK"),
            "quantity": 0,
            "weight": 0,
            "owned": False,
            "source": "watchlist",
        }
        for e in entries
    ]
    return enrich_positions({"positions": positions})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_market_data.py::TestEnrichWatchlist -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/market_data.py tests/test_market_data.py
git commit -m "feat(market-data): enrich_watchlist builds + enriches unowned position dicts"
```

---

### Task B4: `score_universe` orchestration helper

**Files:**
- Create: `app/universe.py`
- Test: `tests/test_watchlist_scoring.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_watchlist_scoring.py — append
import app.universe as universe
from unittest.mock import patch


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
    # Only the watchlist item is returned, and it is scored in the merged pool.
    assert len(result) == 1
    assert result[0]["isin"] == "WATCH"
    assert result[0]["owned"] is False
    assert result[0]["buy_priority_score"] == 0.5  # neutral, as in Task B1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_watchlist_scoring.py::test_score_universe_returns_only_watchlist_scored -v`
Expected: FAIL — no module `app.universe`

- [ ] **Step 3: Write implementation**

```python
# app/universe.py
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

    Returns the enriched + scored watchlist dicts only. owned_positions are used for
    pool context (z-score distribution) but are not mutated destructively beyond the
    score fields compute_scores already sets — pass copies if that matters to the caller.
    """
    if not watchlist_entries:
        return []
    enriched_watch = enrich_watchlist(watchlist_entries)
    merged = list(owned_positions) + enriched_watch
    compute_scores(merged)
    return [p for p in merged if p.get("source") == "watchlist"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_watchlist_scoring.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/universe.py tests/test_watchlist_scoring.py
git commit -m "feat(universe): score_universe — shared enrich+score path for watchlist"
```

---

## Part C — API endpoints

### Task C1: Watchlist schemas

**Files:**
- Modify: `app/schemas.py`

- [ ] **Step 1: Add schemas (no separate test — exercised by C2 route tests)**

Append to `app/schemas.py`:

```python
# ─── Watchlist ──────────────────────────────────────────────────────────────────


class WatchlistAddRequest(BaseModel):
    isin: str


class WatchlistTypeOverrideRequest(BaseModel):
    asset_type: str  # "ETF" | "STOCK"


class WatchlistItem(BaseModel):
    model_config = ConfigDict(extra="allow")  # enriched signal fields ride along

    isin: str
    symbol: str
    name: str
    asset_type: str
    asset_type_source: str
    note: str = ""
    added_at: str
    buy_priority_score: float | None = None


class WatchlistResponse(BaseModel):
    items: list[dict[str, Any]] = []


class WatchlistMutationResponse(BaseModel):
    status: str
    item: dict[str, Any] | None = None
```

Extend `RebalancePlanResponse` — add this field to the existing class:

```python
    watchlist_candidates: list[dict[str, Any]] = []  # display-only, tagged owned=False
```

- [ ] **Step 2: Verify import**

Run: `PYTHONPATH=. python -c "import app.schemas as s; print(s.WatchlistResponse, s.WatchlistAddRequest)"`
Expected: prints both class reprs, no error.

- [ ] **Step 3: Commit**

```bash
git add app/schemas.py
git commit -m "feat(schemas): watchlist request/response models; rebalance watchlist_candidates"
```

---

### Task C2: Watchlist routes + cookie exemption

**Files:**
- Modify: `app/main.py` (add 5 routes; add `GET /api/watchlist` to the `check_session_cookie` exemption at ~line 560)
- Test: `tests/test_watchlist_routes.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_watchlist_routes.py
"""API tests for /api/watchlist* — CRUD + auth exemption."""
import importlib
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    import app.rate_limiter as rl
    with rl._store_lock:
        rl._rate_limit_store.clear()
    yield


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "testpassword123")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-hmac")
    monkeypatch.setenv("BROKR_AUTH_TOKEN", "test-bearer-token-12345")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("WATCHLIST_PATH", str(tmp_path / "watchlist.json"))
    import app.watchlist_store as ws
    importlib.reload(ws)
    from app.main import app
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    app.router.lifespan_context = noop_lifespan
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _headers():
    from app.auth import make_session_cookie
    token, _ = make_session_cookie()
    return {"cookies": {"brokr_session": token},
            "headers": {"Authorization": "Bearer test-bearer-token-12345"}}


class TestWatchlistCrud:
    def test_add_then_get(self, client):
        from app.auth import make_session_cookie
        token, _ = make_session_cookie()
        client.cookies.set("brokr_session", token)
        h = {"Authorization": "Bearer test-bearer-token-12345"}
        with patch("app.main.resolve_and_classify") as mock_rc:
            mock_rc.return_value = {"symbol": "AAPL", "name": "Apple Inc.", "asset_type": "STOCK"}
            r = client.post("/api/watchlist", json={"isin": "US0378331005"}, headers=h)
            assert r.status_code == 200
            assert r.json()["item"]["symbol"] == "AAPL"

        # GET returns the entry (scoring mocked to avoid yfinance)
        with patch("app.main.score_universe", return_value=[]):
            r = client.get("/api/watchlist", headers=h)
            assert r.status_code == 200
            isins = [it["isin"] for it in r.json()["items"]]
            assert "US0378331005" in isins

    def test_add_unresolvable_returns_400(self, client):
        from app.auth import make_session_cookie
        token, _ = make_session_cookie()
        client.cookies.set("brokr_session", token)
        h = {"Authorization": "Bearer test-bearer-token-12345"}
        with patch("app.main.resolve_and_classify", side_effect=ValueError("Could not resolve ISIN")):
            r = client.post("/api/watchlist", json={"isin": "XX0000000000"}, headers=h)
            assert r.status_code == 400

    def test_delete_removes(self, client):
        from app.auth import make_session_cookie
        token, _ = make_session_cookie()
        client.cookies.set("brokr_session", token)
        h = {"Authorization": "Bearer test-bearer-token-12345"}
        with patch("app.main.resolve_and_classify",
                   return_value={"symbol": "AAPL", "name": "Apple", "asset_type": "STOCK"}):
            client.post("/api/watchlist", json={"isin": "US0378331005"}, headers=h)
        r = client.delete("/api/watchlist/US0378331005", headers=h)
        assert r.status_code == 200

    def test_patch_overrides_type(self, client):
        from app.auth import make_session_cookie
        token, _ = make_session_cookie()
        client.cookies.set("brokr_session", token)
        h = {"Authorization": "Bearer test-bearer-token-12345"}
        with patch("app.main.resolve_and_classify",
                   return_value={"symbol": "AAPL", "name": "Apple", "asset_type": "STOCK"}):
            client.post("/api/watchlist", json={"isin": "US0378331005"}, headers=h)
        r = client.patch("/api/watchlist/US0378331005", json={"asset_type": "ETF"}, headers=h)
        assert r.status_code == 200
        assert r.json()["item"]["asset_type"] == "ETF"


class TestWatchlistAuthExemption:
    def test_get_watchlist_works_with_bearer_only_no_cookie(self, client):
        """GET /api/watchlist is agent-accessible: bearer token, NO browser session cookie."""
        client.cookies.clear()
        with patch("app.main.score_universe", return_value=[]):
            r = client.get("/api/watchlist",
                            headers={"Authorization": "Bearer test-bearer-token-12345"},
                            follow_redirects=False)
        # Must NOT 303-redirect to /login (i.e. it is exempt from check_session_cookie)
        assert r.status_code == 200

    def test_post_watchlist_requires_cookie(self, client):
        """Mutating endpoints are UI-only: no cookie → 303 redirect to /login."""
        client.cookies.clear()
        r = client.post("/api/watchlist", json={"isin": "US0378331005"},
                        headers={"Authorization": "Bearer test-bearer-token-12345"},
                        follow_redirects=False)
        assert r.status_code == 303
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_watchlist_routes.py -v`
Expected: FAIL — routes don't exist (404) and exemption not present.

- [ ] **Step 3: Add `GET /api/watchlist` to the cookie exemption**

In `app/main.py`, in `check_session_cookie` (~line 560), add one condition to the exemption `if`:

```python
        or path == "/api/watchlist"
```

(Place it next to `path == "/api/hermes-context"`. Note: this exempts ONLY the exact path `/api/watchlist` — the `GET`. The mutating routes use the same path for POST but `check_session_cookie` runs per-request regardless of method, so to keep POST/DELETE/PATCH cookie-gated we must exempt by method too. Implement the method guard:)

Replace that single condition with a method-aware check just before the exemption `return`:

```python
    # GET /api/watchlist is agent-accessible (bearer only); its mutations stay UI-only.
    if path == "/api/watchlist" and request.method == "GET":
        return await call_next(request)
```

Put this block immediately BEFORE the existing `if (path == "/login" ...)` exemption so the GET short-circuits cleanly.

- [ ] **Step 4: Add imports and routes in `app/main.py`**

Add imports near the existing market_data/scoring imports (top of file):

```python
from .market_data import resolve_and_classify
from .universe import score_universe
from . import watchlist_store
from .schemas import (
    WatchlistAddRequest, WatchlistTypeOverrideRequest,
    WatchlistResponse, WatchlistMutationResponse,
)
```

Add routes (place after the rebalance route, ~line 1158).

> **Session access pattern (verified):** `main.py` has TWO locks — `_session_lock` (an `asyncio.Lock`, used in async contexts via `async with`) and `_sync_lock` (a `threading.Lock`, used in sync contexts via `with`). Reads from helper functions that may run inside `asyncio.to_thread` MUST use `_sync_lock`, exactly like the hermes route (`with _sync_lock: portfolio = _session["portfolio"]`). `_session["portfolio"]` may be `None`.

```python
def _current_owned_positions() -> list[dict]:
    """Owned, enriched positions from the live session (empty if none loaded)."""
    with _sync_lock:
        portfolio = _session["portfolio"]
    if not portfolio:
        return []
    return list(portfolio.get("positions", []))


@app.get("/api/watchlist", dependencies=[Depends(verify_brok_token)], response_model=WatchlistResponse)
async def get_watchlist():
    """List watchlist entries enriched + scored against the owned pool. Agent-accessible."""
    entries = watchlist_store.list_entries()
    if not entries:
        return WatchlistResponse(items=[])
    owned = _current_owned_positions()
    scored = await asyncio.to_thread(score_universe, owned, entries)
    by_isin = {p["isin"]: p for p in scored}
    # Merge stored metadata with enriched/scored signals
    items = []
    for e in entries:
        merged = {**e, **by_isin.get(e["isin"], {})}
        items.append(_sanitize_floats(merged))
    return WatchlistResponse(items=items)


@app.post("/api/watchlist", dependencies=[Depends(verify_brok_token), Depends(check_rate_limit)], response_model=WatchlistMutationResponse)
async def add_watchlist(req: WatchlistAddRequest):
    """Add an ISIN to the watchlist (resolve + classify once)."""
    isin = req.isin.strip().upper()
    # Reject if already owned
    if any((p.get("isin") or "").upper() == isin for p in _current_owned_positions()):
        raise HTTPException(status_code=400, detail="You already own this position")
    try:
        resolved = await asyncio.to_thread(resolve_and_classify, isin)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        record = watchlist_store.add_entry({"isin": isin, **resolved})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return WatchlistMutationResponse(status="added", item=record)


@app.delete("/api/watchlist/{isin}", dependencies=[Depends(verify_brok_token)], response_model=WatchlistMutationResponse)
async def delete_watchlist(isin: str):
    try:
        watchlist_store.remove_entry(isin)
    except KeyError:
        raise HTTPException(status_code=404, detail="Not on the watchlist")
    return WatchlistMutationResponse(status="removed")


@app.patch("/api/watchlist/{isin}", dependencies=[Depends(verify_brok_token)], response_model=WatchlistMutationResponse)
async def patch_watchlist(isin: str, req: WatchlistTypeOverrideRequest):
    try:
        record = watchlist_store.set_asset_type(isin, req.asset_type)
    except KeyError:
        raise HTTPException(status_code=404, detail="Not on the watchlist")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return WatchlistMutationResponse(status="updated", item=record)


@app.post("/api/watchlist/{isin}/resolve", dependencies=[Depends(verify_brok_token), Depends(check_rate_limit)], response_model=WatchlistMutationResponse)
async def resolve_watchlist(isin: str):
    """Re-run resolution + classification for an existing entry (preserves manual type)."""
    try:
        resolved = await asyncio.to_thread(resolve_and_classify, isin.strip().upper())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        record = watchlist_store.update_resolution(
            isin.strip().upper(), resolved["symbol"], resolved["name"], resolved["asset_type"]
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Not on the watchlist")
    return WatchlistMutationResponse(status="resolved", item=record)
```

> Verify `_session`, `_session_lock`, `HTTPException`, and `asyncio` are already imported/defined in `main.py` (they are used by existing routes). If the session accessor differs, match the exact pattern used by `GET /api/portfolio` (~line 671).

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/test_watchlist_routes.py -v`
Expected: PASS (CRUD + both auth-exemption tests)

- [ ] **Step 6: Run the middleware test suite to confirm no regression**

Run: `PYTHONPATH=. pytest tests/test_middleware.py tests/test_routes.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/main.py tests/test_watchlist_routes.py
git commit -m "feat(watchlist): /api/watchlist CRUD + resolve; GET exempt from cookie gate"
```

---

## Part D — Pipeline integration (candidates + rebalancer)

### Task D1: Merge watchlist into dashboard top_candidates

**Files:**
- Modify: `app/main.py` (the portfolio assembly — where `get_top_candidates` is called, ~line 310, inside `_compute_metrics`; and the callers that build the response at ~726/856)
- Test: `tests/test_watchlist_routes.py` (append a portfolio-merge test) OR `tests/test_integration.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_watchlist_routes.py — append
class TestPortfolioCandidateMerge:
    def test_watchlist_candidates_tagged_in_portfolio(self, client, monkeypatch):
        """top_candidates includes watchlist items tagged owned=False."""
        from app.auth import make_session_cookie
        token, _ = make_session_cookie()
        client.cookies.set("brokr_session", token)
        h = {"Authorization": "Bearer test-bearer-token-12345"}

        with patch("app.main.resolve_and_classify",
                   return_value={"symbol": "NVDA", "name": "NVIDIA", "asset_type": "STOCK"}):
            client.post("/api/watchlist", json={"isin": "US67066G1040"}, headers=h)

        # The merge helper should surface watchlist candidates. We test the helper directly:
        import app.main as m
        fake_scored = [{"isin": "US67066G1040", "symbol": "NVDA", "name": "NVIDIA",
                        "asset_type": "STOCK", "owned": False, "buy_priority_score": 0.8,
                        "rsi": 40, "distance_from_52w_high_pct": -10, "momentum_score": 5, "weight": 0}]
        with patch("app.main.score_universe", return_value=fake_scored):
            owned = [{"isin": "X", "asset_type": "STOCK", "buy_priority_score": 0.5,
                      "name": "X", "symbol": "X", "owned": True, "weight": 5}]
            cands = m.merge_watchlist_candidates(owned, {"etfs": [], "stocks": []}, n=3)
        nvda = [c for c in cands["stocks"] if c["isin"] == "US67066G1040"]
        assert nvda and nvda[0]["owned"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_watchlist_routes.py::TestPortfolioCandidateMerge -v`
Expected: FAIL — `merge_watchlist_candidates` does not exist.

- [ ] **Step 3: Implement the merge helper + wire it into the portfolio response**

Add to `app/main.py`:

```python
def merge_watchlist_candidates(owned_positions: list[dict], top_candidates: dict, n: int = 3) -> dict:
    """Score the watchlist against the owned pool and merge its names into top_candidates.

    Watchlist candidates are tagged owned=False and re-sorted with owned candidates by
    buy_priority_score; each pool (etfs/stocks) is trimmed to top n. Returns a new dict.
    """
    entries = watchlist_store.list_entries()
    if not entries:
        return top_candidates
    scored = score_universe(owned_positions, entries)
    from .scoring import get_top_candidates
    watch_cands = get_top_candidates(scored, n=len(scored))  # all watchlist, already tagged owned=False
    merged = {"etfs": list(top_candidates.get("etfs", [])),
              "stocks": list(top_candidates.get("stocks", []))}
    for pool in ("etfs", "stocks"):
        combined = merged[pool] + watch_cands.get(pool, [])
        combined = [c for c in combined if c.get("buy_priority_score") is not None]
        combined.sort(key=lambda c: c["buy_priority_score"], reverse=True)
        merged[pool] = combined[:n]
    return merged
```

Then, at the point where the portfolio response is finalized (the route at ~line 726 after `compute_scores`, and ~856), wrap the existing `top_candidates`:

```python
        portfolio_data["top_candidates"] = await asyncio.to_thread(
            merge_watchlist_candidates,
            portfolio_data["positions"],
            portfolio_data.get("top_candidates", {"etfs": [], "stocks": []}),
            3,
        )
```

> Apply this AFTER `_compute_metrics` has produced `top_candidates`. Do it in the `/api/portfolio` route (~726) and the refresh path (~856) — the two places `compute_scores` is called for live data. Do NOT add it to `_restore_portfolio_from_snapshot` (startup must not block on yfinance).

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_watchlist_routes.py::TestPortfolioCandidateMerge -v`
Expected: PASS

- [ ] **Step 5: Run portfolio/integration tests for regressions**

Run: `PYTHONPATH=. pytest tests/test_integration.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_watchlist_routes.py
git commit -m "feat(watchlist): merge watchlist names into dashboard top_candidates (tagged)"
```

---

### Task D2: Display watchlist candidates in the rebalancer

**Files:**
- Modify: `app/main.py` (the `/api/rebalance-plan` route, ~line 1105) — attach `watchlist_candidates` to the response.
- Test: `tests/test_rebalance.py` or `tests/test_watchlist_routes.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_watchlist_routes.py — append
class TestRebalanceWatchlistDisplay:
    def test_rebalance_plan_includes_watchlist_candidates(self, client, monkeypatch):
        from app.auth import make_session_cookie
        token, _ = make_session_cookie()
        client.cookies.set("brokr_session", token)
        h = {"Authorization": "Bearer test-bearer-token-12345"}

        import app.main as m
        # A scored watchlist name (display-only)
        fake_scored = [{"isin": "US67066G1040", "symbol": "NVDA", "name": "NVIDIA",
                        "asset_type": "STOCK", "owned": False, "buy_priority_score": 0.8,
                        "rsi": 40, "distance_from_52w_high_pct": -10, "momentum_score": 5, "weight": 0}]
        out = m.build_watchlist_candidate_display(
            [{"isin": "X", "asset_type": "STOCK", "owned": True}], scored=fake_scored, n=5)
        assert out and out[0]["isin"] == "US67066G1040"
        assert out[0]["owned"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_watchlist_routes.py::TestRebalanceWatchlistDisplay -v`
Expected: FAIL — no `build_watchlist_candidate_display`.

- [ ] **Step 3: Implement**

Add to `app/main.py`:

```python
def build_watchlist_candidate_display(owned_positions: list[dict], scored: list[dict] | None = None, n: int = 5) -> list[dict]:
    """Top-n scored watchlist names for display in the rebalancer (allocation untouched)."""
    if scored is None:
        entries = watchlist_store.list_entries()
        if not entries:
            return []
        scored = score_universe(owned_positions, entries)
    ranked = [s for s in scored if s.get("buy_priority_score") is not None]
    ranked.sort(key=lambda s: s["buy_priority_score"], reverse=True)
    out = []
    for s in ranked[:n]:
        out.append({
            "isin": s.get("isin", ""), "symbol": s.get("symbol", ""),
            "name": s.get("name", ""), "asset_type": s.get("asset_type", ""),
            "buy_priority_score": s.get("buy_priority_score"),
            "rsi": s.get("rsi"), "distance_from_52w_high_pct": s.get("distance_from_52w_high_pct"),
            "owned": False,
        })
    return out
```

Wire it into the rebalance route (~1105). The route currently ends with:

```python
    plan = plan_contribution(portfolio, amount)
    plan = _sanitize_floats(plan)
    return plan
```

Insert the watchlist display between `plan_contribution` and `_sanitize_floats` (so its float fields get sanitized too):

```python
    plan = plan_contribution(portfolio, amount)
    plan["watchlist_candidates"] = await asyncio.to_thread(
        build_watchlist_candidate_display, _current_owned_positions(), None, 5
    )
    plan = _sanitize_floats(plan)
    return plan
```

> The early empty-plan return (when no portfolio is loaded) is a separate dict literal and needs no change — the schema field added in C1 defaults to `[]`, so it stays backward-compatible.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_watchlist_routes.py::TestRebalanceWatchlistDisplay -v`
Expected: PASS

- [ ] **Step 5: Run rebalance tests for regressions**

Run: `PYTHONPATH=. pytest tests/test_rebalance.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_watchlist_routes.py
git commit -m "feat(rebalance): display-only watchlist candidates in the plan"
```

---

## Part E — Hermes export

### Task E1: Watchlist section in the export

**Files:**
- Modify: `app/context_builder.py`
- Test: `tests/test_context_builder.py` (create if absent, else append)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_context_builder.py — append (create file with imports if missing)
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_context_builder.py::test_watchlist_appears_in_json_and_plaintext -v`
Expected: FAIL — `watchlist` not in JSON / "WATCHLIST" not in plaintext.

- [ ] **Step 3: Implement**

In `build_hermes_context`, after `top_candidates = portfolio.get(...)`:

```python
    watchlist = portfolio.get("watchlist", [])
```

Add `"watchlist": watchlist,` to the `json_context` dict.

In `_build_plaintext`, after the TOP BUY CANDIDATES block (before the benchmark section), insert:

```python
    # Watchlist (candidate new buys, not owned)
    watchlist = context.get("watchlist", [])
    lines.append("═══ WATCHLIST (candidate new buys — not owned) ═══")
    lines.append("")
    if watchlist:
        for w in watchlist:
            score = w.get("buy_priority_score")
            score_s = f"{score:.2f}" if score is not None else "N/A"
            rsi = w.get("rsi")
            rsi_s = f"{rsi:.0f}" if rsi is not None else "N/A"
            dist = w.get("distance_from_52w_high_pct")
            dist_s = f"{dist:+.1f}%" if dist is not None else "N/A"
            lines.append(f"  {w.get('name','N/A')} ({w.get('symbol','N/A')}) [{w.get('asset_type','?')}]")
            lines.append(f"     Buy Priority: {score_s}  RSI: {rsi_s}  Dist from 52w high: {dist_s}")
    else:
        lines.append("  No watchlist entries.")
    lines.append("")
```

And pass `watchlist` through `json_context` (already added) so `_build_plaintext` sees it via `context`.

- [ ] **Step 4: Wire the watchlist into the hermes-context route**

In `app/main.py`, the `/api/hermes-context` route (~937). The existing body is:

```python
    with _sync_lock:
        portfolio = _session["portfolio"]

    return build_hermes_context(portfolio if portfolio is not None else {})
```

Replace it with (attach the scored watchlist onto a shallow copy, guarding `None`):

```python
    with _sync_lock:
        portfolio = _session["portfolio"]

    ctx_portfolio = dict(portfolio) if portfolio is not None else {}
    entries = watchlist_store.list_entries()
    if entries:
        ctx_portfolio["watchlist"] = await asyncio.to_thread(
            score_universe, ctx_portfolio.get("positions", []), entries
        )
    return build_hermes_context(ctx_portfolio)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_context_builder.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/context_builder.py app/main.py tests/test_context_builder.py
git commit -m "feat(hermes): watchlist section in export JSON + plaintext"
```

---

## Part F — UI

### Task F1: Watchlist panel markup + styles

**Files:**
- Modify: `app/index.html` (add a `<details>` panel after the rebalance panel, ~line 176; add `<script src="/static/watchlist.js" defer></script>` near the existing app.js script tag)
- Modify: `app/static/style.css` (minimal additions; reuse rebalance classes)

- [ ] **Step 1: Add the panel markup** (after the rebalance `<details>` block)

```html
      <details id="watchlist-panel" class="rebalance-panel">
        <summary class="rebalance-summary">
          <span class="rebalance-toggle-icon"><i data-lucide="chevron-right"></i></span>
          <span>Watchlist — candidate new buys</span>
        </summary>
        <div class="rebalance-content">
          <div class="rebalance-input-row">
            <div class="rebalance-input-group">
              <label for="watchlist-isin">Add by ISIN</label>
              <input type="text" id="watchlist-isin" placeholder="e.g. US0378331005" autocomplete="off">
            </div>
            <button id="btn-watchlist-add" class="btn btn-primary">Add</button>
          </div>
          <div id="watchlist-error" class="rebalance-error hidden"></div>
          <div id="watchlist-loading" class="rebalance-loading hidden">Loading…</div>
          <div id="watchlist-empty" class="rebalance-empty">No watchlist entries yet.</div>
          <table id="watchlist-table" class="watchlist-table hidden">
            <thead>
              <tr><th>Name</th><th>Type</th><th>BuyPr</th><th>RSI</th><th>52w</th><th></th></tr>
            </thead>
            <tbody id="watchlist-tbody"></tbody>
          </table>
        </div>
      </details>
```

- [ ] **Step 2: Add the script tag** (next to the existing `<script src="/static/app.js" ...>`)

```html
    <script src="/static/watchlist.js" defer></script>
```

- [ ] **Step 3: Add minimal styles to `style.css`**

```css
.watchlist-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
.watchlist-table th, .watchlist-table td { padding: 0.4rem 0.5rem; text-align: left; border-bottom: 1px solid var(--border, #2a2a2a); }
.watchlist-table td.num { text-align: right; font-variant-numeric: tabular-nums; }
.watchlist-remove { cursor: pointer; background: none; border: none; color: var(--danger, #e06c75); }
.watchlist-type-toggle { cursor: pointer; background: none; border: 1px solid var(--border, #2a2a2a); border-radius: 4px; color: inherit; font-size: 0.8rem; padding: 0.1rem 0.3rem; }
```

- [ ] **Step 4: Commit**

```bash
git add app/index.html app/static/style.css
git commit -m "feat(watchlist): dashboard panel markup + styles"
```

---

### Task F2: Watchlist panel client logic

**Files:**
- Create: `app/static/watchlist.js`

> CSP: external file only, no inline JS. Reuse the global `apiFetch` exposed by `app.js`. Verify `app.js` exposes `apiFetch` on `window` (e.g. `window.Brokr = { apiFetch }`); if not, add that export to `app.js` in this task and commit together.

- [ ] **Step 1: Implement `watchlist.js`**

```javascript
// app/static/watchlist.js — Watchlist panel. Depends on window.Brokr.apiFetch from app.js.
(function () {
  "use strict";

  function api(url, opts) { return window.Brokr.apiFetch(url, opts); }

  const els = {};
  function cache() {
    els.panel = document.getElementById("watchlist-panel");
    els.isin = document.getElementById("watchlist-isin");
    els.add = document.getElementById("btn-watchlist-add");
    els.error = document.getElementById("watchlist-error");
    els.loading = document.getElementById("watchlist-loading");
    els.empty = document.getElementById("watchlist-empty");
    els.table = document.getElementById("watchlist-table");
    els.tbody = document.getElementById("watchlist-tbody");
  }

  function showError(msg) {
    els.error.textContent = msg;
    els.error.classList.remove("hidden");
  }
  function clearError() { els.error.classList.add("hidden"); els.error.textContent = ""; }

  function fmt(v, digits) { return (v === null || v === undefined) ? "—" : Number(v).toFixed(digits); }

  function render(items) {
    els.tbody.innerHTML = "";
    if (!items.length) {
      els.empty.classList.remove("hidden");
      els.table.classList.add("hidden");
      return;
    }
    els.empty.classList.add("hidden");
    els.table.classList.remove("hidden");
    items.forEach(function (it) {
      const tr = document.createElement("tr");

      const nameTd = document.createElement("td");
      nameTd.textContent = it.name || it.symbol || it.isin;
      tr.appendChild(nameTd);

      const typeTd = document.createElement("td");
      const typeBtn = document.createElement("button");
      typeBtn.className = "watchlist-type-toggle";
      typeBtn.textContent = it.asset_type;
      typeBtn.title = "Toggle ETF / STOCK";
      typeBtn.addEventListener("click", function () { toggleType(it); });
      typeTd.appendChild(typeBtn);
      tr.appendChild(typeTd);

      const scoreTd = document.createElement("td");
      scoreTd.className = "num";
      scoreTd.textContent = fmt(it.buy_priority_score, 2);
      tr.appendChild(scoreTd);

      const rsiTd = document.createElement("td");
      rsiTd.className = "num";
      rsiTd.textContent = fmt(it.rsi, 0);
      tr.appendChild(rsiTd);

      const distTd = document.createElement("td");
      distTd.className = "num";
      distTd.textContent = fmt(it.distance_from_52w_high_pct, 1);
      tr.appendChild(distTd);

      const rmTd = document.createElement("td");
      const rmBtn = document.createElement("button");
      rmBtn.className = "watchlist-remove";
      rmBtn.textContent = "✕";
      rmBtn.setAttribute("aria-label", "Remove " + (it.symbol || it.isin));
      rmBtn.addEventListener("click", function () { remove(it.isin); });
      rmTd.appendChild(rmBtn);
      tr.appendChild(rmTd);

      els.tbody.appendChild(tr);
    });
  }

  async function load() {
    clearError();
    els.loading.classList.remove("hidden");
    try {
      const res = await api("/api/watchlist");
      const data = await res.json();
      render(data.items || []);
    } catch (e) {
      showError("Failed to load watchlist");
    } finally {
      els.loading.classList.add("hidden");
    }
  }

  async function add() {
    clearError();
    const isin = (els.isin.value || "").trim().toUpperCase();
    if (!isin) { showError("Enter an ISIN"); return; }
    els.add.disabled = true;
    try {
      const res = await api("/api/watchlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ isin: isin }),
      });
      if (!res.ok) {
        const err = await res.json().catch(function () { return {}; });
        showError(err.detail || "Could not add");
        return;
      }
      els.isin.value = "";
      await load();
    } catch (e) {
      showError("Could not add");
    } finally {
      els.add.disabled = false;
    }
  }

  async function remove(isin) {
    clearError();
    try {
      await api("/api/watchlist/" + encodeURIComponent(isin), { method: "DELETE" });
      await load();
    } catch (e) { showError("Could not remove"); }
  }

  async function toggleType(item) {
    clearError();
    const next = item.asset_type === "ETF" ? "STOCK" : "ETF";
    try {
      await api("/api/watchlist/" + encodeURIComponent(item.isin), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ asset_type: next }),
      });
      await load();
    } catch (e) { showError("Could not update type"); }
  }

  document.addEventListener("DOMContentLoaded", function () {
    cache();
    if (!els.panel) return;
    els.add.addEventListener("click", add);
    els.isin.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); add(); }
    });
    // Lazy-load on first expand
    els.panel.addEventListener("toggle", function () {
      if (els.panel.open && !els.tbody.children.length) load();
    });
  });
})();
```

- [ ] **Step 2: Ensure `app.js` exposes `apiFetch`**

If `app.js` does not already expose it, add near the top of its IIFE (after `apiFetch` is defined):

```javascript
  window.Brokr = window.Brokr || {};
  window.Brokr.apiFetch = apiFetch;
```

- [ ] **Step 3: Manual smoke test (documented, run by executor)**

Run the app per project convention (use `-f docker-compose.dev.yml`):
```bash
docker compose -f docker-compose.dev.yml up -d --build
```
Open the dashboard, expand "Watchlist", paste a known ISIN (e.g. `US0378331005`), confirm it resolves, shows a type + score, the type toggle flips ETF/STOCK, and remove works. Confirm no CSP violations in the browser console.

- [ ] **Step 4: Commit**

```bash
git add app/static/watchlist.js app/static/app.js
git commit -m "feat(watchlist): panel client logic (add/remove/override, lazy load)"
```

---

## Part G — Documentation

### Task G1: README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the relevant sections**

- **What Brokr Does:** add a bullet — "Watchlist / candidate universe: track tickers you don't own yet; they're enriched and scored in the same pool as your holdings so new buys rank beside top-ups."
- **Scoring System:** add a note — "Watchlist candidates share the ETF/STOCK scoring pool. Because they have no portfolio weight, the weight factor is neutralized to 0.5 for unowned names (they rank on value/momentum/distance/RSI, not on being unowned)."
- **API:** document the five endpoints — `GET /api/watchlist` (agent-accessible, read-only), `POST /api/watchlist`, `DELETE /api/watchlist/{isin}`, `PATCH /api/watchlist/{isin}`, `POST /api/watchlist/{isin}/resolve`.
- **Environment Variables:** add `WATCHLIST_PATH` (default `/data/watchlist.json`) and note the 30-entry cap.

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs(readme): document watchlist / candidate universe feature"
```

---

## Final verification

- [ ] **Run the full test suite**

Run: `PYTHONPATH=. pytest -q`
Expected: all tests pass (no regressions in scoring, routes, middleware, rebalance, integration).

- [ ] **Confirm the four surfaces work end-to-end** (manual, via the running dev container)
  1. Watchlist panel: add/score/override/remove.
  2. Dashboard top-candidates list: a watchlist name appears tagged "not owned" when its score ranks.
  3. Rebalancer: `watchlist_candidates` shown, allocation unchanged.
  4. Hermes export (`btn-export`): WATCHLIST section present in the plaintext.
