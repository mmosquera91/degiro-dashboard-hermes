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


class TestPortfolioCandidateMerge:
    def test_watchlist_candidates_tagged_in_portfolio(self, client):
        _set_cookie(client)
        # Add a watchlist name to the store so merge has something to merge.
        with patch("app.main.resolve_and_classify",
                   return_value={"symbol": "NVDA", "name": "NVIDIA", "asset_type": "STOCK"}):
            client.post("/api/watchlist", json={"isin": "US67066G1040"}, headers=_bearer())

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

    def test_merge_with_empty_watchlist_is_noop(self, client):
        import app.main as m
        original = {"etfs": [{"isin": "E1"}], "stocks": [{"isin": "S1"}]}
        # No entries in the store → merge returns top_candidates unchanged.
        out = m.merge_watchlist_candidates([], original, n=3)
        assert out == original


class TestRebalanceWatchlistDisplay:
    def test_build_display_ranks_and_tags(self):
        import app.main as m
        fake_scored = [
            {"isin": "US67066G1040", "symbol": "NVDA", "name": "NVIDIA",
             "asset_type": "STOCK", "owned": False, "buy_priority_score": 0.8,
             "rsi": 40, "distance_from_52w_high_pct": -10, "momentum_score": 5, "weight": 0},
            {"isin": "LOW", "symbol": "LOW", "name": "Low", "asset_type": "ETF",
             "owned": False, "buy_priority_score": 0.3, "rsi": 50,
             "distance_from_52w_high_pct": -5, "momentum_score": 1, "weight": 0},
            {"isin": "NOSCORE", "symbol": "NS", "name": "NS", "asset_type": "STOCK",
             "owned": False, "buy_priority_score": None},
        ]
        out = m.build_watchlist_candidate_display(
            [{"isin": "X", "asset_type": "STOCK", "owned": True}], scored=fake_scored, n=5)
        # Ranked by buy_priority desc, None scores excluded, tagged owned=False
        assert [c["isin"] for c in out] == ["US67066G1040", "LOW"]
        assert all(c["owned"] is False for c in out)

    def test_build_display_trims_to_n(self):
        import app.main as m
        scored = [{"isin": f"S{i}", "symbol": f"S{i}", "name": f"S{i}", "asset_type": "STOCK",
                   "owned": False, "buy_priority_score": i / 10.0,
                   "rsi": None, "distance_from_52w_high_pct": None} for i in range(10)]
        out = m.build_watchlist_candidate_display([], scored=scored, n=3)
        assert len(out) == 3
        assert out[0]["buy_priority_score"] == 0.9  # highest first

    def test_rebalance_plan_includes_watchlist_field(self, client):
        _set_cookie(client)
        # No portfolio loaded → early-return path; field must still default to [].
        r = client.get("/api/rebalance-plan?amount=1000", headers=_bearer())
        assert r.status_code == 200
        assert "watchlist_candidates" in r.json()
