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
