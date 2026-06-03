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
            "asset_type_source": "auto",
            "note": "",
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
