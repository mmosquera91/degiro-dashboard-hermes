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
    els.panel.addEventListener("toggle", function () {
      if (els.panel.open && !els.tbody.children.length) load();
    });
  });
})();
