/* ═══════════════════════════════════════════════════════════════
   Brokr — Frontend Application
   ═══════════════════════════════════════════════════════════════ */

(function () {
  "use strict";

  // ─── State ───
  let portfolioData = null;
  let benchmarkData = null;
  let currentFilter = "all";
  let sortKey = "current_value_eur";
  let sortDir = -1; // -1 = descending
  let charts = {};

  // ─── Auth ───
  const AUTH_TOKEN = "dev-secret-change-in-production";
  const authHeaders = { "Authorization": `Bearer ${AUTH_TOKEN}` };

  // ─── API Helper ───
  async function apiFetch(url, options = {}) {
    return fetch(url, {
      ...options,
      headers: { ...authHeaders, ...(options.headers || {}) },
    });
  }

  // ─── DOM refs ───
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  const elDashboard = $("#dashboard");
  const elEmptyState = $("#empty-state");
  const elCredModal = $("#cred-modal");
  const elLoadingOverlay = $("#loading-overlay");
  const elCredForm = $("#cred-form");
  const elCredError = $("#cred-error");
  const elBtnConnect = $("#btn-connect");
  const elConnectText = $("#connect-text");
  const elConnectSpinner = $("#connect-spinner");
  const elBtnRefresh = $("#btn-refresh");
  const elBtnExport = $("#btn-export");
  const elBtnEmptyConnect = $("#btn-empty-connect");
  const elLastRefresh = $("#last-refresh");
  const elPositionsBody = $("#positions-body");

  // ─── Init ───
  document.addEventListener("DOMContentLoaded", () => {
    lucide.createIcons();
    bindEvents();
    // Try loading cached portfolio on page load (works even if session expired)
    loadPortfolioRaw();
  });

  function bindEvents() {
    elBtnRefresh.addEventListener("click", openModal);
    elBtnEmptyConnect.addEventListener("click", openModal);
    elBtnExport.addEventListener("click", exportHermesContext);
    $("#modal-close").addEventListener("click", closeModal);
    elCredModal.addEventListener("click", (e) => {
      if (e.target === elCredModal) closeModal();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeModal();
    });
    elCredForm.addEventListener("submit", handleAuth);
    $("#session-form").addEventListener("submit", handleSession);

    // Modal tabs
    $$(".modal-tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        const tabId = btn.dataset.tab;
        $$(".modal-tab").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        $$(".tab-panel").forEach((p) => p.classList.remove("active"));
        $("#" + tabId).classList.add("active");
      });
    });

    // Filter tabs
    $$(".filter-tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        $$(".filter-tab").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        currentFilter = btn.dataset.filter;
        renderPositions();
      });
    });

    // Sort headers
    $$("#positions-table th[data-sort]").forEach((th) => {
      th.addEventListener("click", () => {
        const key = th.dataset.sort;
        if (sortKey === key) {
          sortDir *= -1;
        } else {
          sortKey = key;
          sortDir = -1;
        }
        renderPositions();
      });
    });
  }

  // ─── Modal ───
  function openModal() {
    elCredModal.classList.remove("hidden");
    elCredError.classList.add("hidden");
    $("#session-error").classList.add("hidden");
    elCredForm.reset();
    $("#session-form").reset();
    // Reset to first tab
    $$(".modal-tab").forEach((b) => b.classList.remove("active"));
    $$(".tab-panel").forEach((p) => p.classList.remove("active"));
    $(".modal-tab[data-tab='creds-tab']").classList.add("active");
    $("#creds-tab").classList.add("active");
    $("#cred-user").focus();
  }

  function closeModal() {
    elCredModal.classList.add("hidden");
  }

  // ─── Auth ───
  async function handleAuth(e) {
    e.preventDefault();

    const username = $("#cred-user").value.trim();
    const password = $("#cred-pass").value;
    const otp = $("#cred-otp").value.trim() || null;

    if (!username || !password) return;

    elBtnConnect.disabled = true;
    elConnectText.classList.add("hidden");
    elConnectSpinner.classList.remove("hidden");
    elCredError.classList.add("hidden");

    try {
      const res = await apiFetch("/api/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password, otp }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Authentication failed");
      }

      closeModal();
      await loadPortfolioRaw();
    } catch (err) {
      elCredError.textContent = err.message;
      elCredError.classList.remove("hidden");
    } finally {
      elBtnConnect.disabled = false;
      elConnectText.classList.remove("hidden");
      elConnectSpinner.classList.add("hidden");
    }
  }

  // ─── Browser Session Auth ───
  async function handleSession(e) {
    e.preventDefault();

    const sessionId = $("#session-id").value.trim();
    const intAccountRaw = $("#int-account").value.trim();
    const intAccount = intAccountRaw ? parseInt(intAccountRaw, 10) : null;

    if (!sessionId) return;

    const btn = $("#btn-session-connect");
    const txt = $("#session-connect-text");
    const spin = $("#session-connect-spinner");
    const err = $("#session-error");

    btn.disabled = true;
    txt.classList.add("hidden");
    spin.classList.remove("hidden");
    err.classList.add("hidden");

    try {
      const res = await apiFetch("/api/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, int_account: intAccount }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Session authentication failed");
      }

      closeModal();
      await loadPortfolioRaw();
    } catch (err) {
      $("#session-error").textContent = err.message;
      $("#session-error").classList.remove("hidden");
    } finally {
      btn.disabled = false;
      txt.classList.remove("hidden");
      spin.classList.add("hidden");
    }
  }

  // ─── Load Portfolio ───
  async function loadPortfolio() {
    try {
      const res = await apiFetch("/api/portfolio");

      if (res.status === 401) {
        showEnriching(false);
        openModal();
        return;
      }

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to load portfolio");
      }

      portfolioData = await res.json();

      // Fetch benchmark data
      const bmData = await fetchBenchmarkData();
      if (bmData) {
        benchmarkData = bmData;
        renderBenchmark(bmData);
        renderAttribution(bmData);
      }

      renderDashboard();
      showEnriching(false);
    } catch (err) {
      showEnriching(false);
      console.error("Portfolio load error:", err);
      // Don't alert — raw data is already showing
    }
  }

  async function loadPortfolioRaw() {
    showLoading(true);
    try {
      const res = await apiFetch("/api/portfolio-raw");

      if (res.status === 401) {
        showLoading(false);
        openModal();
        return;
      }

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to load portfolio");
      }

      portfolioData = await res.json();
      renderDashboard();
      showLoading(false);

      // Now kick off full enrichment in background
      showEnriching(true);
      loadPortfolio();
    } catch (err) {
      showLoading(false);
      ToastManager.show("Error: " + err.message, "error");
    }
  }

  function showLoading(on) {
    if (on) {
      elLoadingOverlay.classList.remove("hidden");
    } else {
      elLoadingOverlay.classList.add("hidden");
    }
  }

  function showEnriching(on) {
    const banner = $("#enriching-banner");
    if (on) {
      banner.classList.remove("hidden");
    } else {
      banner.classList.add("hidden");
    }
  }

  // ─── Benchmark Data ───
  async function fetchBenchmarkData() {
    try {
      const res = await apiFetch("/api/benchmark");
      if (!res.ok) return null;
      return await res.json();
    } catch (err) {
      console.error("Benchmark fetch error:", err);
      return null;
    }
  }

  function renderBenchmark(data) {
    const container = $(".benchmark-section");
    if (!container) return;

    const snapshots = data?.snapshots || [];
    const benchmarkSeries = data?.benchmark_series || [];

    // No snapshots yet — show empty-state message
    if (snapshots.length === 0) {
      const chartWrap = $(".benchmark-chart-wrap");
      if (chartWrap) {
        chartWrap.classList.remove("hidden");
        chartWrap.innerHTML = '<div class="benchmark-empty">No snapshots yet. Refresh your portfolio to record a baseline.</div>';
      }
      const comparisonDiv = $("#benchmark-comparison-table");
      if (comparisonDiv) comparisonDiv.classList.add("hidden");
      return;
    }

    // D-18: If only one snapshot, show comparison table instead of chart
    if (snapshots.length === 1) {
      const snap = snapshots[0];
      const comparisonDiv = $("#benchmark-comparison-table");
      if (comparisonDiv) {
        comparisonDiv.classList.remove("hidden");
        const chartWrap = $(".benchmark-chart-wrap");
        if (chartWrap) chartWrap.classList.add("hidden");
        comparisonDiv.innerHTML = `
          <table class="comparison-table">
            <tr><th>Metric</th><th>Portfolio</th><th>S&P 500</th></tr>
            <tr><td>Value (Indexed)</td><td>100.00</td><td>${(snap.benchmark_value || 100).toFixed(2)}</td></tr>
            <tr><td>Return</td><td>—</td><td>${(snap.benchmark_return_pct || 0).toFixed(2)}%</td></tr>
          </table>
          <p class="benchmark-note">Only one snapshot recorded. Chart will appear after next portfolio refresh.</p>
        `;
      }
      return;
    }

    // Show chart (2+ snapshots)
    const chartWrap = $(".benchmark-chart-wrap");
    if (chartWrap) chartWrap.classList.remove("hidden");
    const comparisonDiv = $("#benchmark-comparison-table");
    if (comparisonDiv) comparisonDiv.classList.add("hidden");

    // Compute indexed portfolio values (all relative to first snapshot = 100)
    if (snapshots.length < 2) return;
    const baseValue = snapshots[0].total_value_eur;
    const indexedPortfolio = snapshots.map(s => ({
      date: s.date,
      value: baseValue > 0 ? (s.total_value_eur / baseValue) * 100 : 100
    }));

    // Build chart data — X-axis from snapshots, Y-axis indexed to 100
    charts.benchmark = new Chart($("#chart-benchmark"), {
      type: "line",
      data: {
        labels: indexedPortfolio.map(p => p.date),
        datasets: [
          {
            label: "Portfolio",
            data: indexedPortfolio.map(p => p.value),
            borderColor: "#01696f",
            backgroundColor: "transparent",
            tension: 0.1,
            spanGaps: true,  // D-17: allow gaps in data
          },
          {
            label: "S&P 500",
            data: benchmarkSeries.map(b => b.value),
            borderColor: "#d97706",
            backgroundColor: "transparent",
            tension: 0.1,
            spanGaps: true,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: true, labels: { color: "#888", font: { family: "Inter", size: 11 } } },
        },
        scales: {
          x: {
            ticks: { color: "#888", font: { family: "Inter", size: 10 } },
            grid: { color: "#2a2a2a" },
          },
          y: {
            ticks: { color: "#888", font: { family: "Inter", size: 10 }, callback: (v) => v.toFixed(0) },
            grid: { color: "#2a2a2a" },
            title: { display: true, text: "Indexed to 100", color: "#666" },
          },
        },
      },
    });
  }

  function renderAttribution(data) {
    const container = $("#attribution-table-wrap");
    if (!container) return;

    // Ensure section is visible
    const section = $(".attribution-section");
    if (section) section.classList.remove("hidden");

    const attribution = data?.attribution || [];

    if (attribution.length === 0) {
      container.innerHTML = '<p class="attribution-empty">No attribution data yet. Attribution requires portfolio snapshots and benchmark data.</p>';
      return;
    }

    // Sort by absolute_contribution descending
    const sorted = [...attribution].sort((a, b) => {
      const av = a.absolute_contribution || 0;
      const bv = b.absolute_contribution || 0;
      return bv - av;
    });

    const rows = sorted.map(a => {
      const absVal = a.absolute_contribution || 0;
      const relVal = a.relative_contribution || 0;
      const signClass = absVal >= 0 ? "positive" : "negative";
      return `
        <tr>
          <td class="col-name">${esc(a.name || "N/A")}</td>
          <td>${a.symbol || "—"}</td>
          <td class="${signClass}">${absVal >= 0 ? "+" : ""}${absVal.toFixed(4)}</td>
          <td class="${signClass}">${relVal >= 0 ? "+" : ""}${relVal.toFixed(4)}</td>
        </tr>
      `;
    }).join("");

    container.innerHTML = `
      <table class="attribution-table">
        <thead>
          <tr>
            <th class="col-name">Position</th>
            <th>Symbol</th>
            <th>Absolute Contribution</th>
            <th>Relative Contribution</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
      <p class="attribution-note">
        <strong>Absolute:</strong> position_return × weight |
        <strong>Relative:</strong> (position_return − benchmark_return) × weight × direction
      </p>
    `;
  }

  // ─── Render Dashboard ───
  function renderDashboard() {
    if (!portfolioData) return;

    elEmptyState.classList.add("hidden");
    elDashboard.classList.remove("hidden");
    elBtnExport.style.display = "";

    // Last refresh
    const dt = new Date(portfolioData.date);
    elLastRefresh.textContent = "Updated " + dt.toLocaleString();

    // Summary cards
    renderSummary();

    // Charts
    renderCharts();

    // Positions table
    renderPositions();

    // Buy Radar
    renderBuyRadar();

    // Winners / Losers
    renderWinnersLosers();

    // Health Alerts
    renderHealthAlerts();

    lucide.createIcons();
  }

  // ─── Summary ───
  function renderSummary() {
    const d = portfolioData;

    $("#total-value").textContent = fmtEur(d.total_value);

    const plEl = $("#total-pl");
    const plPctEl = $("#total-pl-pct");
    plEl.textContent = fmtEur(d.total_pl);
    plPctEl.textContent = fmtPct(d.total_pl_pct);
    setSignClass(plEl, d.total_pl);
    setSignClass(plPctEl, d.total_pl_pct);

    const dailyEl = $("#daily-change");
    if (d.daily_change_pct != null) {
      dailyEl.textContent = fmtPct(d.daily_change_pct);
      setSignClass(dailyEl, d.daily_change_pct);
    } else {
      dailyEl.textContent = "—";
    }

    // Allocation bar
    const etfPct = d.etf_allocation_pct || 0;
    const stockPct = d.stock_allocation_pct || 0;
    $("#etf-bar").style.width = etfPct + "%";
    $("#stock-bar").style.width = stockPct + "%";
    $("#etf-pct").innerHTML = `ETF <span>${etfPct.toFixed(1)}%</span>`;
    $("#stock-pct").innerHTML = `Stock <span>${stockPct.toFixed(1)}%</span>`;

    $("#cash-available").textContent = fmtEur(d.cash_available);
    $("#num-positions").textContent = d.num_positions;
  }

  // ─── Charts ───
  function renderCharts() {
    const d = portfolioData;
    const positions = d.positions || [];

    // Destroy existing charts
    Object.values(charts).forEach((c) => c.destroy());
    charts = {};

    // 1. ETF vs Stocks donut
    const etfVal = positions.filter((p) => p.asset_type === "ETF").reduce((s, p) => s + (p.current_value_eur || 0), 0);
    const stockVal = positions.filter((p) => p.asset_type === "STOCK").reduce((s, p) => s + (p.current_value_eur || 0), 0);

    charts.etfStock = new Chart($("#chart-etf-stock"), {
      type: "doughnut",
      data: {
        labels: ["ETFs", "Stocks"],
        datasets: [{
          data: [etfVal, stockVal],
          backgroundColor: ["#01696f", "#d97706"],
          borderColor: "#1a1a1a",
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "65%",
        plugins: {
          legend: { display: true, position: "bottom", labels: { color: "#888", font: { family: "Inter", size: 11 } } },
        },
      },
    });

    // 2. Top 10 by weight
    const top10 = [...positions].sort((a, b) => (b.weight || 0) - (a.weight || 0)).slice(0, 10);
    charts.topWeight = new Chart($("#chart-top-weight"), {
      type: "bar",
      data: {
        labels: top10.map((p) => truncate(p.name, 18)),
        datasets: [{
          data: top10.map((p) => p.weight || 0),
          backgroundColor: top10.map((p) => (p.asset_type === "ETF" ? "#01696f" : "#d97706")),
          borderRadius: 3,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: "y",
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: "#888", font: { family: "Inter", size: 10 } }, grid: { color: "#2a2a2a" } },
          y: { ticks: { color: "#888", font: { family: "Inter", size: 10 } }, grid: { display: false } },
        },
      },
    });

    // 3. Sector breakdown donut
    const sectorData = d.sector_breakdown || {};
    const sectorLabels = Object.keys(sectorData);
    const sectorValues = Object.values(sectorData);
    const sectorColors = generateColors(sectorLabels.length);

    charts.sector = new Chart($("#chart-sector"), {
      type: "doughnut",
      data: {
        labels: sectorLabels,
        datasets: [{
          data: sectorValues,
          backgroundColor: sectorColors,
          borderColor: "#1a1a1a",
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "55%",
        plugins: {
          legend: { display: true, position: "bottom", labels: { color: "#888", font: { family: "Inter", size: 10 }, boxWidth: 12 } },
        },
      },
    });
  }

  // ─── Positions Table ───
  function renderPositions() {
    if (!portfolioData) return;

    let positions = portfolioData.positions || [];

    // Filter
    if (currentFilter !== "all") {
      positions = positions.filter((p) => p.asset_type === currentFilter);
    }

    // Sort
    positions = [...positions].sort((a, b) => {
      const av = a[sortKey] ?? null;
      const bv = b[sortKey] ?? null;
      if (av === null && bv === null) return 0;
      if (av === null) return 1;
      if (bv === null) return -1;
      if (typeof av === "string") return sortDir * av.localeCompare(bv);
      return sortDir * (av - bv);
    });

    elPositionsBody.innerHTML = "";

    positions.forEach((p) => {
      const tr = document.createElement("tr");
      tr.dataset.id = p.product_id || p.name;

      const plClass = getPlClass(p.unrealized_pl_pct);

      tr.innerHTML = `
        <td class="col-name">${esc(p.name)}</td>
        <td>${p.asset_type || "—"}</td>
        <td>${fmtEur(p.current_value_eur)}</td>
        <td>${p.quantity ?? "—"}</td>
        <td>${p.avg_buy_price != null ? p.avg_buy_price.toFixed(2) : "—"}</td>
        <td>${p.current_price != null ? p.current_price.toFixed(2) : "—"}</td>
        <td class="${plClass}">${p.unrealized_pl_pct != null ? p.unrealized_pl_pct.toFixed(2) + "%" : "—"}</td>
        <td>${p.weight != null ? p.weight.toFixed(1) + "%" : "—"}</td>
        <td>${p.rsi != null ? p.rsi.toFixed(0) : "—"}</td>
        <td>${p.momentum_score != null ? p.momentum_score.toFixed(2) : "—"}</td>
        <td>${p.buy_priority_score != null ? p.buy_priority_score.toFixed(2) : "—"}</td>
      `;

      tr.addEventListener("click", () => toggleDetail(p));
      elPositionsBody.appendChild(tr);

      // Detail row
      const detailTr = document.createElement("tr");
      detailTr.className = "row-detail";
      detailTr.dataset.detailFor = p.product_id || p.name;
      detailTr.innerHTML = `
        <td colspan="11">
          <div class="detail-grid">
            <div class="detail-item"><label>ISIN</label><span>${esc(p.isin || "—")}</span></div>
            <div class="detail-item"><label>Currency</label><span>${esc(p.currency || "—")}</span></div>
            <div class="detail-item"><label>Sector</label><span>${esc(p.sector || "—")}</span></div>
            <div class="detail-item"><label>52w High</label><span>${p["52w_high"] != null ? p["52w_high"].toFixed(2) : "—"}</span></div>
            <div class="detail-item"><label>52w Low</label><span>${p["52w_low"] != null ? p["52w_low"].toFixed(2) : "—"}</span></div>
            <div class="detail-item"><label>Dist from 52w High</label><span>${p.distance_from_52w_high_pct != null ? p.distance_from_52w_high_pct.toFixed(1) + "%" : "—"}</span></div>
            <div class="detail-item"><label>30d Perf</label><span>${p.perf_30d != null ? p.perf_30d.toFixed(1) + "%" : "—"}</span></div>
            <div class="detail-item"><label>90d Perf</label><span>${p.perf_90d != null ? p.perf_90d.toFixed(1) + "%" : "—"}</span></div>
            <div class="detail-item"><label>YTD Perf</label><span>${p.perf_ytd != null ? p.perf_ytd.toFixed(1) + "%" : "—"}</span></div>
            <div class="detail-item"><label>P/E Ratio</label><span>${p.pe_ratio != null ? p.pe_ratio.toFixed(1) : "—"}</span></div>
            <div class="detail-item"><label>Value Score</label><span>${p.value_score != null ? p.value_score.toFixed(2) : "—"}</span></div>
          </div>
        </td>
      `;
      elPositionsBody.appendChild(detailTr);
    });
  }

  function toggleDetail(position) {
    const key = position.product_id || position.name;
    const row = elPositionsBody.querySelector(`tr[data-detail-for="${key}"]`);
    if (row) {
      row.classList.toggle("expanded");
    }
  }

  // ─── Buy Radar ───
  function renderBuyRadar() {
    const candidates = portfolioData.top_candidates || {};

    renderRadarPanel("radar-etfs", candidates.etfs || []);
    renderRadarPanel("radar-stocks", candidates.stocks || []);
  }

  function renderRadarPanel(containerId, items) {
    const container = $("#" + containerId);
    if (!container) return;

    if (!items.length) {
      container.innerHTML = '<div class="radar-item"><span class="radar-item-info"><span class="radar-item-name">No candidates available</span></span></div>';
      return;
    }

    container.innerHTML = items
      .map(
        (c) => `
      <div class="radar-item">
        <div class="radar-item-info">
          <div class="radar-item-name">${esc(c.name)} <span style="color:var(--text-muted);font-weight:400;font-size:0.75rem">${esc(c.symbol || "")}</span></div>
          <div class="radar-item-reason">${esc(c.reason)}</div>
        </div>
        <div class="radar-item-score">${c.buy_priority_score != null ? c.buy_priority_score.toFixed(2) : "—"}</div>
      </div>
    `
      )
      .join("");
  }

  // ─── Winners / Losers ───
  function renderWinnersLosers() {
    const winners = portfolioData.top_5_winners || [];
    const losers = portfolioData.top_5_losers || [];

    const winnersEl = $("#top-winners");
    const losersEl = $("#top-losers");

    winnersEl.innerHTML = winners
      .map(
        (w) => `
      <div class="wl-item">
        <span>${esc(w.name)}</span>
        <span class="wl-item-pl pl-positive">${w.pl_pct != null ? w.pl_pct.toFixed(2) + "%" : "—"}</span>
      </div>
    `
      )
      .join("");

    losersEl.innerHTML = losers
      .map(
        (l) => `
      <div class="wl-item">
        <span>${esc(l.name)}</span>
        <span class="wl-item-pl pl-negative">${l.pl_pct != null ? l.pl_pct.toFixed(2) + "%" : "—"}</span>
      </div>
    `
      )
      .join("");
  }

  // ─── Health Alerts ───
function renderHealthAlerts() {
    const alerts = portfolioData.health_alerts || [];
    const container = $("#health-alerts-list");
    if (!container) return;

    if (alerts.length === 0) {
        container.innerHTML = `
            <div class="alert-empty">
                <span class="alert-empty-icon">&#10003;</span>
                <span class="alert-empty-text">All systems healthy</span>
                <span class="alert-empty-sub">No health alerts detected. Your portfolio looks balanced.</span>
            </div>
        `;
        lucide.createIcons();
        return;
    }

    container.innerHTML = alerts
        .map((alert) => {
            const severity = (alert.severity || "warn").toLowerCase();
            const typeLabel = (alert.type || "unknown").toUpperCase().replace("_", " ");
            return `
                <div class="alert-card ${esc(severity)}">
                    <div class="alert-header">
                        <span class="alert-type-label">${esc(typeLabel)}</span>
                        <span class="alert-severity-badge">${severity === "critical" ? "Critical" : "Warning"}</span>
                    </div>
                    <div class="alert-message">${esc(alert.message)}</div>
                    ${alert.current_value != null && alert.threshold != null ?
                        `<div class="alert-detail">Current: ${alert.current_value.toFixed(1)}% | Threshold: ${alert.threshold.toFixed(1)}%</div>` :
                        ""}
                </div>
            `;
        })
        .join("");

    lucide.createIcons();
}

  // ─── Export Hermes Context ───
  async function exportHermesContext() {
    try {
      const res = await apiFetch("/api/hermes-context");

      if (res.status === 401) {
        openModal();
        return;
      }

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to export context");
      }

      const data = await res.json();
      const plaintext = data.plaintext;

      // Try clipboard API first
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(plaintext);
          ToastManager.show("Hermes context copied to clipboard!", "success");
          return;
        } catch {
          // Fall through to download
        }
      }

      // Fallback: download as .txt
      downloadText(plaintext, "brokr-hermes-context.txt");
    } catch (err) {
      ToastManager.show("Export failed: " + err.message, "error");
    }
  }

  function downloadText(text, filename) {
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // ─── Helpers ───
  function fmtEur(val) {
    if (val == null) return "—";
    return "€" + val.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function fmtPct(val) {
    if (val == null) return "—";
    return (val >= 0 ? "+" : "") + val.toFixed(2) + "%";
  }

  function setSignClass(el, val) {
    el.classList.remove("positive", "negative");
    if (val > 0) el.classList.add("positive");
    else if (val < 0) el.classList.add("negative");
  }

  function getPlClass(val) {
    if (val == null) return "";
    return val >= 0 ? "pl-positive" : "pl-negative";
  }

  function esc(str) {
    if (str == null) return "";
    const d = document.createElement("div");
    d.textContent = String(str);
    return d.innerHTML;
  }

  function truncate(str, max) {
    if (!str) return "";
    return str.length > max ? str.substring(0, max - 1) + "…" : str;
  }

  function generateColors(n) {
    const base = [
      "#01696f", "#d97706", "#7c3aed", "#ef4444", "#22c55e",
      "#3b82f6", "#ec4899", "#f59e0b", "#06b6d4", "#8b5cf6",
      "#14b8a6", "#f97316", "#6366f1", "#84cc16", "#e11d48",
    ];
    const colors = [];
    for (let i = 0; i < n; i++) {
      colors.push(base[i % base.length]);
    }
    return colors;
  }

  // ─── Toast Manager ───
  const ToastManager = (function () {
    const MAX_VISIBLE = 3;
    const AUTO_DISMISS_MS = 4000;
    const containerId = "toast-container";

    let queue = [];
    let visible = 0;

    function ensureContainer() {
      let c = document.getElementById(containerId);
      if (!c) {
        c = document.createElement("div");
        c.id = containerId;
        c.setAttribute("aria-live", "polite");
        c.style.cssText = [
          "position:fixed",
          "top:16px",
          "right:16px",
          "z-index:800",
          "display:flex",
          "flex-direction:column",
          "gap:8px",
          "pointer-events:none",
        ].join(";");
        document.body.appendChild(c);
      }
      return c;
    }

    function show(message, variant = "info") {
      const container = ensureContainer();

      // Dismiss oldest if at max
      if (visible >= MAX_VISIBLE) {
        dismiss(queue.shift());
      }

      const toast = document.createElement("div");
      toast.className = "toast toast-" + variant;
      toast.setAttribute("role", "alert");

      // Icon per variant
      var icons = {
        success: "check-circle",
        error: "alert-circle",
        info: "info",
      };

      toast.innerHTML = '<i data-lucide="' + icons[variant] + '" class="toast-icon"></i>' +
        '<span class="toast-message">' + esc(message) + '</span>' +
        '<button class="toast-close" aria-label="Dismiss">' +
        '<i data-lucide="x" class="icon-sm"></i></button>';

      // Dismiss on click
      toast.querySelector(".toast-close").addEventListener("click", function() { dismiss(toast); });

      container.appendChild(toast);
      lucide.createIcons({ nodes: [toast] });

      // Trigger enter animation
      requestAnimationFrame(function() { toast.classList.add("toast-enter"); });

      queue.push(toast);
      visible++;

      // Auto-dismiss
      var timer = setTimeout(function() { dismiss(toast); }, AUTO_DISMISS_MS);
      toast._dismissTimer = timer;

      return toast;
    }

    function dismiss(toast) {
      if (!toast || !toast.parentNode) return;
      clearTimeout(toast._dismissTimer);
      toast.classList.add("toast-exit");
      toast.addEventListener("animationend", function() {
        toast.remove();
        visible--;
        var idx = queue.indexOf(toast);
        if (idx > -1) queue.splice(idx, 1);
      }, { once: true });
    }

    return { show: show, dismiss: dismiss };
  })();
})();
