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


def _bearer():
    return {"Authorization": "Bearer test-bearer-token-12345"}


def _set_cookie(client):
    from app.auth import make_session_cookie
    token, _ = make_session_cookie()
    client.cookies.set("brokr_session", token)


class TestWatchlistCrud:
    def test_add_then_get(self, client):
        _set_cookie(client)
        with patch("app.main.resolve_and_classify",
                   return_value={"symbol": "AAPL", "name": "Apple Inc.", "asset_type": "STOCK"}):
            r = client.post("/api/watchlist", json={"isin": "US0378331005"}, headers=_bearer())
            assert r.status_code == 200
            assert r.json()["item"]["symbol"] == "AAPL"
        with patch("app.main.score_universe", return_value=[]):
            r = client.get("/api/watchlist", headers=_bearer())
            assert r.status_code == 200
            assert "US0378331005" in [it["isin"] for it in r.json()["items"]]

    def test_add_unresolvable_returns_400(self, client):
        _set_cookie(client)
        with patch("app.main.resolve_and_classify", side_effect=ValueError("Could not resolve ISIN")):
            r = client.post("/api/watchlist", json={"isin": "XX0000000000"}, headers=_bearer())
            assert r.status_code == 400

    def test_delete_removes(self, client):
        _set_cookie(client)
        with patch("app.main.resolve_and_classify",
                   return_value={"symbol": "AAPL", "name": "Apple", "asset_type": "STOCK"}):
            client.post("/api/watchlist", json={"isin": "US0378331005"}, headers=_bearer())
        r = client.delete("/api/watchlist/US0378331005", headers=_bearer())
        assert r.status_code == 200

    def test_patch_overrides_type(self, client):
        _set_cookie(client)
        with patch("app.main.resolve_and_classify",
                   return_value={"symbol": "AAPL", "name": "Apple", "asset_type": "STOCK"}):
            client.post("/api/watchlist", json={"isin": "US0378331005"}, headers=_bearer())
        r = client.patch("/api/watchlist/US0378331005", json={"asset_type": "ETF"}, headers=_bearer())
        assert r.status_code == 200
        assert r.json()["item"]["asset_type"] == "ETF"


class TestWatchlistAuthExemption:
    def test_get_watchlist_works_with_bearer_only_no_cookie(self, client):
        """GET /api/watchlist is agent-accessible: bearer token, NO browser session cookie."""
        client.cookies.clear()
        with patch("app.main.score_universe", return_value=[]):
            r = client.get("/api/watchlist", headers=_bearer(), follow_redirects=False)
        assert r.status_code == 200

    def test_post_watchlist_requires_cookie(self, client):
        """Mutating endpoints are UI-only: no cookie → 303 redirect to /login."""
        client.cookies.clear()
        r = client.post("/api/watchlist", json={"isin": "US0378331005"},
                        headers=_bearer(), follow_redirects=False)
        assert r.status_code == 303

    def test_get_watchlist_without_bearer_returns_401(self, client):
        """Cookie exemption must NOT open an unauthenticated path — bearer still required."""
        client.cookies.clear()
        with patch("app.main.score_universe", return_value=[]):
            r = client.get("/api/watchlist", follow_redirects=False)
        assert r.status_code == 401

    def test_delete_without_cookie_redirects(self, client):
        """DELETE is UI-only: no cookie → 303."""
        client.cookies.clear()
        r = client.delete("/api/watchlist/US0378331005", headers=_bearer(), follow_redirects=False)
        assert r.status_code == 303


class TestWatchlistResolve:
    def test_resolve_updates_entry(self, client):
        _set_cookie(client)
        with patch("app.main.resolve_and_classify",
                   return_value={"symbol": "AAPL", "name": "Apple", "asset_type": "STOCK"}):
            client.post("/api/watchlist", json={"isin": "US0378331005"}, headers=_bearer())
        with patch("app.main.resolve_and_classify",
                   return_value={"symbol": "AAPL2", "name": "Apple Renamed", "asset_type": "STOCK"}):
            r = client.post("/api/watchlist/US0378331005/resolve", headers=_bearer())
        assert r.status_code == 200
        assert r.json()["item"]["symbol"] == "AAPL2"

    def test_resolve_unknown_isin_returns_404(self, client):
        _set_cookie(client)
        with patch("app.main.resolve_and_classify",
                   return_value={"symbol": "X", "name": "X", "asset_type": "STOCK"}):
            r = client.post("/api/watchlist/NOTONLIST00/resolve", headers=_bearer())
        assert r.status_code == 404

    def test_resolve_unresolvable_returns_400(self, client):
        _set_cookie(client)
        with patch("app.main.resolve_and_classify",
                   return_value={"symbol": "AAPL", "name": "Apple", "asset_type": "STOCK"}):
            client.post("/api/watchlist", json={"isin": "US0378331005"}, headers=_bearer())
        with patch("app.main.resolve_and_classify", side_effect=ValueError("Could not resolve")):
            r = client.post("/api/watchlist/US0378331005/resolve", headers=_bearer())
        assert r.status_code == 400
