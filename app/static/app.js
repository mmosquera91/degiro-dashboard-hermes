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
  let lastSuccessfulRefresh = null;
  let privacyMode = false;

  // ─── Render caches (throttle/chrome) ───
  let _lastPositionsHash = null;
  let _lastTableHash = null;

  function positionsHash(positions) {
    return positions.map(p =>
      `${p.product_id}:${p.current_price}:${p.weight}`
    ).join('|');
  }

  // ─── Auth ───
  let _authToken = null;

  // When the session is gone (never logged in, or expired while this tab was
  // open), a protected endpoint answers with a 303 → /login that fetch follows
  // automatically — surfacing as res.redirected to the login page — or a 401.
  // Either way, send the user to the login screen rather than letting callers
  // choke on an HTML body with .json(). Returns true if a redirect was issued.
  function _bounceToLoginIfUnauthenticated(res) {
    if (res.status === 401 || (res.redirected && /\/login(\?|$)/.test(res.url))) {
      window.location.href = "/login";
      return true;
    }
    return false;
  }

  async function _ensureAuthToken() {
    if (_authToken !== null) return;
    try {
      // Bootstrap endpoint — authenticated by the session cookie, not a bearer.
      const res = await fetch("/api/session-token", { credentials: "same-origin" });
      if (_bounceToLoginIfUnauthenticated(res)) return;
      if (res.ok) {
        const data = await res.json();
        _authToken = data.token;
      }
    } catch (err) { console.warn("Auth token fetch failed:", err); }
  }

  async function apiFetch(url, options = {}) {
    await _ensureAuthToken();
    const res = await fetch(url, {
      ...options,
      headers: { "Authorization": `Bearer ${_authToken}`, ...(options.headers || {}) },
      credentials: "same-origin",
    });
    _bounceToLoginIfUnauthenticated(res);
    return res;
  }

  // ─── DOM refs ───
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  const elDashboard = $("#dashboard");
  const elEmptyState = $("#empty-state");
  const elCredModal = $("#cred-modal");
  const elLoadingOverlay = $("#loading-overlay");
  const elCredError = $("#cred-error");
  const elBtnConnect = $("#btn-connect");
  const elConnectText = $("#connect-text");
  const elConnectSpinner = $("#connect-spinner");
  const elBtnRefresh = $("#btn-refresh");
  const elBtnUpdatePrices = $("#btn-update-prices");
  const elBtnExport = $("#btn-export");
  const elBtnPrivacy = $("#btn-privacy");
  const elBtnEmptyConnect = $("#btn-empty-connect");
  const elLastRefresh = $("#last-refresh");
  const elPositionsBody = $("#positions-body");
  const elEnrichmentModal = $("#enrichment-modal");
  const elEnrichmentModalContent = $("#enrichment-modal-content");
  const elEnrichmentStatus = $("#enrichment-status");
  const elEnrichmentError = $("#enrichment-error");
  const elEnrichmentErrorMsg = $("#enrichment-error-msg");
  const elEnrichmentClose = $("#enrichment-close");

  // ─── Init ───
  document.addEventListener("DOMContentLoaded", () => {
    document.body.classList.add("view-degiro");
    lucide.createIcons();
    bindEvents();
    // Try loading cached portfolio on page load (works even if session expired)
    loadPortfolioRaw();
  });

  function bindEvents() {
    if (!elBtnRefresh && !elBtnUpdatePrices && !elBtnEmptyConnect && !elBtnExport && !elBtnPrivacy) {
      return; // No elements found, skip binding
    }
    if (elBtnRefresh) elBtnRefresh.addEventListener("click", () => { _lastTableHash = null; openModal(); });
    if (elBtnUpdatePrices) elBtnUpdatePrices.addEventListener("click", handleUpdatePrices);
    if (elBtnEmptyConnect) elBtnEmptyConnect.addEventListener("click", openModal);
    if (elBtnExport) elBtnExport.addEventListener("click", exportHermesContext);
    if (elBtnPrivacy) elBtnPrivacy.addEventListener("click", togglePrivacyMode);
    const modalClose = $("#modal-close");
    if (modalClose) modalClose.addEventListener("click", closeModal);
    if (elEnrichmentClose) elEnrichmentClose.addEventListener("click", closeEnrichmentModal);
    if (elCredModal) {
      elCredModal.addEventListener("click", (e) => {
        if (e.target === elCredModal) closeModal();
      });
    }
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeModal();
    });
    const sessionForm = $("#session-form");
    if (sessionForm) sessionForm.addEventListener("submit", handleSession);

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

    // Snapshot manager lazy-load
    const snapshotMgr = document.getElementById("snapshot-manager");
    if (snapshotMgr) {
      snapshotMgr.addEventListener("toggle", e => {
        if (e.target.open) renderSnapshotManager();
      });
    }

    // Tab switching
    const tabDegiroBtn = $("#tab-degiro");
    const tabIndexaBtn = $("#tab-indexa");
    if (tabDegiroBtn) tabDegiroBtn.addEventListener("click", () => switchView("degiro"));
    if (tabIndexaBtn) tabIndexaBtn.addEventListener("click", () => switchView("indexa"));

    const btnRefreshIndexa = $("#btn-refresh-indexa");
    if (btnRefreshIndexa) btnRefreshIndexa.addEventListener("click", () => {
      indexaLoaded = false;
      loadIndexaData(true);
    });

    const btnIndexaRetry = $("#btn-indexa-retry");
    if (btnIndexaRetry) btnIndexaRetry.addEventListener("click", () => {
      indexaLoaded = false;
      loadIndexaData(true);
    });

    // Manual snapshot save button
    const btnSaveSnapshot = document.getElementById("btn-save-snapshot");
    if (btnSaveSnapshot) {
      btnSaveSnapshot.addEventListener("click", async () => {
        const btn = document.getElementById("btn-save-snapshot");
        btn.disabled = true;
        btn.querySelector(".btn-label").textContent = "Saving...";
        try {
          const res = await apiFetch("/api/snapshots/save", { method: "POST" });
          if (res.ok) {
            ToastManager.show("Snapshot saved", "success");
            renderSnapshotManager();
          } else {
            ToastManager.show("Failed to save snapshot", "error");
          }
        } finally {
          btn.disabled = false;
          btn.querySelector(".btn-label").textContent = "Save Snapshot Now";
        }
      });
    }
  }

  // ─── Modal ───
  function openModal() {
    if (elCredModal) elCredModal.classList.remove("hidden");
    if (elCredError) elCredError.classList.add("hidden");
    const sessionError = $("#session-error");
    if (sessionError) sessionError.classList.add("hidden");
    const sessionForm = $("#session-form");
    if (sessionForm) sessionForm.reset();
    const sessionIdInput = $("#session-id");
    if (sessionIdInput) sessionIdInput.focus();
  }

  function closeModal() {
    if (elCredModal) elCredModal.classList.add("hidden");
  }

  // ─── Privacy Mode ───
  function togglePrivacyMode() {
    privacyMode = !privacyMode;
    document.body.classList.toggle("privacy-mode", privacyMode);
    if (elBtnPrivacy) {
      elBtnPrivacy.classList.toggle("active", privacyMode);
      const icon = elBtnPrivacy.querySelector("i");
      if (icon) {
        icon.setAttribute("data-lucide", privacyMode ? "eye-off" : "eye");
        lucide.createIcons({ nodes: [elBtnPrivacy] });
      }
    }
    // Re-render Indexa charts so Y-axis/tooltips reflect privacy state
    if (indexaLoaded) {
      renderIndexaAllocationChart();
      renderIndexaPerformanceChart();
    }
  }

  // ─── Browser Session Auth ───
  async function handleSession(e) {
    e.preventDefault();

    const sessionId = $("#session-id").value.trim();

    if (!sessionId) return;

    const btn = $("#btn-session-connect");
    const txt = $("#session-connect-text");
    const spin = $("#session-connect-spinner");
    const err = $("#session-error");

    if (btn) btn.disabled = true;
    if (txt) txt.classList.add("hidden");
    if (spin) spin.classList.remove("hidden");
    if (err) err.classList.add("hidden");

    try {
      const res = await apiFetch("/api/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Session authentication failed");
      }

      closeModal();
      await loadPortfolioRaw();
    } catch (err) {
      const errEl = $("#session-error");
      if (errEl) errEl.textContent = err.message;
      if (errEl) errEl.classList.remove("hidden");
    } finally {
      if (btn) btn.disabled = false;
      if (txt) txt.classList.remove("hidden");
      if (spin) spin.classList.add("hidden");
    }
  }

  // ─── Load Portfolio ───
  async function loadPortfolio() {
    try {
      const res = await apiFetch("/api/portfolio");

      if (res.status === 401) {
        showEnriching(false);
        openModal();
        setOperationActive(false);
        return;
      }

      if (res.status === 409) {
        const data = await res.json();
        showEnriching(false);
        ToastManager.show(data.detail || "Another operation is already running, please wait", "error");
        setOperationActive(false);
        return;
      }

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to load portfolio");
      }

      portfolioData = await res.json();

      renderDashboard();

      // Fetch benchmark data
      const bmData = await fetchBenchmarkData();
      if (bmData) {
        benchmarkData = bmData;
        renderBenchmark(bmData);
        renderAttribution(bmData);
      }

      showEnriching(false);
      setOperationActive(false);
    } catch (err) {
      showEnriching(false);
      console.error("Portfolio load error:", err);
      markDataStale();
      setOperationActive(false);
      if (ToastManager) ToastManager.show("Failed to refresh: " + err.message, "error");
      // Don't clear portfolioData — keep showing last valid data
    }
  }

  async function loadPortfolioRaw() {
    showLoading(true);
    setOperationActive(true);
    try {
      const res = await apiFetch("/api/portfolio-raw");

      if (res.status === 401) {
        showLoading(false);
        if (portfolioData) renderDashboard();
        openModal();
        setOperationActive(false);
        return;
      }

      if (res.status === 409) {
        const data = await res.json();
        showLoading(false);
        ToastManager.show(data.detail || "Another operation is already running, please wait", "error");
        setOperationActive(false);
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
      markDataStale();
      setOperationActive(false);
      if (portfolioData) { renderDashboard(); }
      ToastManager.show("Error: " + err.message, "error");
    }
  }

  
  // ─── Update Prices (non-blocking) ───
  async function handleUpdatePrices() {
    if (!portfolioData) return;
    if (operationActive) {
      ToastManager.show("Another operation is already running, please wait", "error");
      return;
    }
    const btn = elBtnUpdatePrices;
    btn.disabled = true;
    setOperationActive(true);
    const progressToast = ToastManager.showProgressToast("Updating prices…");
    const updateStart = Date.now();
    try {
      const res = await apiFetch("/api/refresh-prices", { method: "POST" });
      if (res.status === 409) {
        const data = await res.json();
        ToastManager.show(data.detail || "Another operation is already running, please wait", "error");
        ToastManager.dismiss(progressToast);
        setOperationActive(false);
        btn.disabled = false;
        return;
      }
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Price refresh failed");
      }
      const done = await waitForEnrichmentToast();
      if (done) {
        ToastManager.updateToast(progressToast, { message: "Prices updated", icon: "check-circle", variant: "success" });
        setTimeout(() => { ToastManager.dismiss(progressToast); setOperationActive(false); }, 2500);
        const elapsed = Date.now() - updateStart;
        setTimeout(() => { setOperationActive(false); btn.disabled = false; }, Math.max(3000 - elapsed, 500));
        return;
      } else {
        ToastManager.dismiss(progressToast);
      }
    } catch (e) {
      console.error("Update prices failed", e);
      ToastManager.updateToast(progressToast, { message: e.message, icon: "alert-circle", variant: "error" });
      setTimeout(function() { ToastManager.dismiss(progressToast); }, 3000);
      setOperationActive(false);
    }
    btn.disabled = false;
  }

  async function waitForEnrichmentToast() {
    const MAX_WAIT_MS = 5 * 60 * 1000;
    const POLL_MS = 2000;
    const started = Date.now();

    // Phase 1: wait until enriching flips to true (max 10s)
    while (Date.now() - started < 10000) {
      await new Promise(r => setTimeout(r, POLL_MS));
      try {
        const res1 = await apiFetch("/api/enrichment-status");
        const status1 = await res1.json();
        if (status1.enriching) break;
      } catch (err) { console.warn("Enrichment status poll failed:", err); }
    }

    // Phase 2: poll until enriching flips back to false
    while (Date.now() - started < MAX_WAIT_MS) {
      await new Promise(r => setTimeout(r, POLL_MS));
      try {
        const res2 = await apiFetch("/api/enrichment-status");
        const status2 = await res2.json();
        if (!status2.enriching) {
          const res = await apiFetch("/api/portfolio");
          portfolioData = await res.json();
          renderDashboard();
          const bmData = await fetchBenchmarkData();
          if (bmData) { benchmarkData = bmData; renderBenchmark(bmData); renderAttribution(bmData); }
          return true;
        }
      } catch (err) { console.warn("Enrichment status poll failed:", err); }
    }
    ToastManager.show("Timed out — refresh manually", "error");
    setOperationActive(false);
    return false;
  }

  // Track active operation state across all buttons
  let operationActive = false;

  function disableUpdatePrices() {
    if (elBtnUpdatePrices) elBtnUpdatePrices.disabled = true;
  }

  function enableUpdatePrices() {
    if (elBtnUpdatePrices) elBtnUpdatePrices.disabled = false;
  }

  function setOperationActive(active) {
    operationActive = active;
    if (active) {
      disableUpdatePrices();
      if (elBtnRefresh) elBtnRefresh.disabled = true;
    } else {
      // Re-enable only if we have portfolio data
      if (portfolioData) enableUpdatePrices();
      if (elBtnRefresh && portfolioData) elBtnRefresh.disabled = false;
    }
  }

  function showLoading(on) {
    if (!elLoadingOverlay) return;
    if (on) {
      elLoadingOverlay.classList.remove("hidden");
    } else {
      elLoadingOverlay.classList.add("hidden");
    }
  }

  function showEnrichmentModal(msg) {
    if (!elEnrichmentModal) return;
    if (elEnrichmentStatus) elEnrichmentStatus.textContent = msg;
    if (elEnrichmentModalContent) elEnrichmentModalContent.classList.remove("hidden");
    if (elEnrichmentError) elEnrichmentError.classList.add("hidden");
    elEnrichmentModal.classList.remove("hidden");
  }

  function closeEnrichmentModal() {
    if (!elEnrichmentModal) return;
    elEnrichmentModal.classList.add("hidden");
    if (elEnrichmentModalContent) elEnrichmentModalContent.classList.remove("hidden");
    if (elEnrichmentError) elEnrichmentError.classList.add("hidden");
  }

  function showEnriching(on) {
    if (on) {
      showEnrichmentModal("Enriching with market data…");
    } else {
      closeEnrichmentModal();
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
        chartWrap.innerHTML = '<div class="chart-empty"><span class="chart-empty-icon">📊</span><span class="chart-empty-text">No data available</span><span class="chart-empty-sub">Refresh portfolio to populate charts</span></div>';
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
            <tr><td>Return</td><td>${snap.total_invested > 0 ? ((snap.unrealized_pl_total || 0) / snap.total_invested * 100).toFixed(2) + '%' : '—'}</td><td>${(snap.benchmark_return_pct || 0).toFixed(2)}%</td></tr>
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

    // Compute indexed portfolio values using TWR chain (Time-Weighted Return).
    // TWR is immune to deposits/withdrawals:
    //   cash_flow = invested_end - invested_start (≈ new money in)
    //   period_return = value_end / (value_start + cash_flow) - 1
    //   TWR = (1+r1)(1+r2)...(1+rn) - 1, indexed to 100
    // Falls back to total_value-based indexing for old snapshots without P&L data.
    if (snapshots.length < 2) return;
    const hasPLData = snapshots.some(s => s.total_invested != null && s.total_invested > 0);
    let indexedPortfolio;
    if (hasPLData) {
      // Build TWR chain
      let cumulative = 1.0; // starts at 1.0, multiplied by (1 + period_return) each step
      indexedPortfolio = [{ date: snapshots[0].date, raw: snapshots[0].total_value_eur, value: 100.0 }];
      for (let i = 1; i < snapshots.length; i++) {
        const prev = snapshots[i - 1];
        const curr = snapshots[i];
        const valueStart = prev.total_value_eur || 0;
        const valueEnd = curr.total_value_eur || 0;
        const investedStart = prev.total_invested || 0;
        const investedEnd = curr.total_invested || 0;
        const cashFlow = investedEnd - investedStart; // positive = deposit
        // Period return adjusted for cash flows
        const denominator = valueStart + cashFlow;
        const periodReturn = denominator > 0 ? (valueEnd / denominator) - 1 : 0;
        cumulative *= (1 + periodReturn);
        indexedPortfolio.push({
          date: curr.date,
          raw: curr.total_value_eur,
          value: cumulative * 100,
        });
      }
    } else {
      // Fallback: old snapshots without total_invested
      const baseValue = snapshots[0].total_value_eur;
      indexedPortfolio = snapshots.map(s => ({
        date: s.date,
        raw: s.total_value_eur,
        value: baseValue > 0 ? (s.total_value_eur / baseValue) * 100 : 100,
      }));
    }

    if (benchmarkSeries.length === 0) {
      if (chartWrap) {
        chartWrap.innerHTML = '<div class="chart-empty"><span class="chart-empty-icon">📊</span><span class="chart-empty-text">No data available</span><span class="chart-empty-sub">Refresh portfolio to populate charts</span></div>';
      }
      return;
    }

    // Filter benchmark series to start at first snapshot date
    const normDate = d => (d || '').slice(0, 10);   // keep YYYY-MM-DD only
    const firstSnapDate = normDate(indexedPortfolio[0].date);
    // Find nearest benchmark date <= firstSnapDate (handles weekend/holiday portfolio starts).
    // If none exists (very new portfolio), fall back to all available benchmark data.
    const beforeOrOn = benchmarkSeries.filter(b => b.date <= firstSnapDate);
    const anchorDate = beforeOrOn.length > 0
        ? beforeOrOn[beforeOrOn.length - 1].date
        : (benchmarkSeries[0]?.date ?? firstSnapDate);
    const filteredBenchmark = benchmarkSeries.filter(b => b.date >= anchorDate);

    // Merge both series by date so the x-axis covers all daily dates.
    // Portfolio gets null on dates it doesn't cover (keeps benchmark continuous).
    const allDates = [...new Set([
      ...indexedPortfolio.map(p => normDate(p.date)),
      ...filteredBenchmark.map(b => normDate(b.date))
    ])].sort();

    const portfolioByDate = new Map(indexedPortfolio.map(p => [normDate(p.date), p]));
    const benchmarkByDate = new Map(filteredBenchmark.map(b => [normDate(b.date), b]));

    const mergedPortfolio = allDates.map(d => portfolioByDate.get(d) || null);
    const mergedBenchmark = allDates.map(d => benchmarkByDate.get(d) || null);

    // Build chart data — X-axis from merged daily dates, Y-axis indexed to 100
    if (charts.benchmark) { charts.benchmark.destroy(); charts.benchmark = null; }
    charts.benchmark = new Chart($("#chart-benchmark"), {
      type: "line",
      data: {
        labels: allDates,
        datasets: [
          {
            label: "Portfolio",
            data: mergedPortfolio.map(p => p?.value ?? null),
            borderColor: "#01696f",
            backgroundColor: "rgba(1,105,111,0.08)",
            fill: true,
            tension: 0.3,
            pointRadius: 3,
            borderWidth: 2,
            spanGaps: true,
          },
          {
            label: "S&P 500",
            data: mergedBenchmark.map(b => b?.value ?? null),
            borderColor: "#d97706",
            backgroundColor: "transparent",
            fill: false,
            tension: 0.3,
            pointRadius: 3,
            borderWidth: 2,
            borderDash: [4, 3],
            spanGaps: true,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: true, position: "bottom", labels: { color: "#888", font: { family: "Inter", size: 10 } } },
          tooltip: { enabled: true },
        },
        scales: {
          x: {
            ticks: { color: "#888", font: { family: "Inter", size: 10 } },
            grid: { color: "#2a2a2a" },
          },
          y: {
            ticks: { color: "#888", font: { family: "Inter", size: 10 }, callback: (v) => Math.round(v) },
            grid: { color: "#2a2a2a" },
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

  // ─── Snapshot Manager ───
  async function renderSnapshotManager() {
    const wrap = $("#snapshot-table-wrap");
    if (!wrap) return;
    try {
      const res = await apiFetch("/api/snapshots");
      const snapshots = await res.json();
      if (!snapshots.length) {
        wrap.innerHTML = "<p style='color:var(--text-dim)'>No snapshots found.</p>";
        return;
      }
      const rows = snapshots.slice().reverse().map(s => `
        <tr>
          <td>${s.date}</td>
          <td>${s.total_value_eur != null ? "€" + s.total_value_eur.toLocaleString("nl-NL", {minimumFractionDigits:2}) : "—"}</td>
          <td>${s.benchmark_return_pct != null ? (s.benchmark_return_pct >= 0 ? "+" : "") + s.benchmark_return_pct.toFixed(2) + "%" : "—"}</td>
          <td>${s.has_portfolio_data ? "✓" : "—"}</td>
          <td>
            <button class="btn btn-danger-sm" data-delete="${s.date}">Delete</button>
          </td>
        </tr>
      `).join("");
      wrap.innerHTML = `
        <table class="positions-table">
          <thead><tr>
            <th>Date</th><th>Portfolio Value</th>
            <th>Benchmark Return</th><th>Has Data</th><th></th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>`;
      wrap.querySelectorAll("[data-delete]").forEach(btn => {
        btn.addEventListener("click", async () => {
          const date = btn.dataset.delete;
          if (!confirm("Delete snapshot " + date + "?")) return;
          const r = await apiFetch("/api/snapshots/" + date, { method: "DELETE" });
          if (r.ok) renderSnapshotManager();
          else ToastManager.show("Failed to delete snapshot", "error");
        });
      });
    } catch (e) {
      wrap.innerHTML = "<p>Failed to load snapshots.</p>";
    }
  }

  // ─── Render Dashboard ───
  function renderDashboard() {
    if (!portfolioData) return;

    elEmptyState.classList.add("hidden");
    elDashboard.classList.remove("hidden");
    if (elBtnExport) elBtnExport.style.display = "";

    // Last refresh
    const dt = new Date(portfolioData.date);
    elLastRefresh.textContent = "Updated " + dt.toLocaleString();

    // Clear stale badge when fresh data is loaded
    clearStaleIndicator();

    // Summary cards
    renderSummary();

    // Concentration metrics
    renderConcentration();

    // Charts — only re-render if positions actually changed
    const hash = positionsHash(portfolioData.positions || []);
    if (hash !== _lastPositionsHash) {
      _lastPositionsHash = hash;
      renderCharts();
    }

    // Positions table
    renderPositions();

    // Buy Radar
    renderBuyRadar();

    // Winners / Losers
    renderWinnersLosers();

    // Health Alerts
    renderHealthAlerts();

    lastSuccessfulRefresh = Date.now();
    lucide.createIcons();
    enableUpdatePrices();

    // Re-apply privacy mode if active
    if (privacyMode) document.body.classList.add("privacy-mode");
  }

  // ─── Summary ───
  function renderSummary() {
    const d = portfolioData;
    const positions = d.positions || [];
    const cash = d.cash_available || 0;
    const totalValue = d.total_value || 0;
    const portfolioTotal = totalValue + cash;

    // Card 1 — Portfolio (incl. cash)
    const portfolioEl = $("#kpi-portfolio");
    portfolioEl.textContent = fmtEur(portfolioTotal);
    const dailyBadge = $("#kpi-portfolio-sub");
    if (d.daily_change_pct != null) {
      const sign = d.daily_change_pct >= 0 ? "▲" : "▼";
      dailyBadge.innerHTML = `<span class="badge ${d.daily_change_pct >= 0 ? "badge-positive" : "badge-negative"}">${sign} ${fmtEur(d.daily_change_eur)} (${fmtPct(d.daily_change_pct)}) today</span>`;
    } else {
      dailyBadge.textContent = "—";
    }

    // Card 1 — Portfolio P&L line (true_total_pl)
    const plEl = $("#kpi-portfolio-pl");
    if (d.true_total_pl != null) {
      plEl.textContent = `Total P&L: ${fmtEur(d.true_total_pl)} (${fmtPct(d.true_total_pl_pct)})`;
      setSignClass(plEl, d.true_total_pl);
    } else {
      plEl.textContent = "—";
    }

    // Card 2 — Invested (excl. cash)
    const investedEl = $("#kpi-invested");
    investedEl.textContent = fmtEur(totalValue);
    $("#kpi-invested-sub").textContent = `${d.num_positions || 0} positions`;

    // Card 3 — Cash
    const cashEl = $("#kpi-cash");
    cashEl.textContent = fmtEur(cash);
    const cashPct = portfolioTotal > 0 ? (cash / portfolioTotal * 100) : 0;
    $("#kpi-cash-sub").textContent = `${cashPct.toFixed(1)}% of portfolio`;
    const cashCard = $("#kpi-cash").closest(".kpi-card");
    if (cashPct < 1) {
      cashCard.style.borderTopColor = "var(--gold)";
      cashCard.style.background = "rgba(217,119,6,0.05)";
      $("#kpi-cash-sub").style.color = "var(--gold)";
    } else {
      cashCard.style.borderTopColor = "";
      cashCard.style.background = "";
      $("#kpi-cash-sub").style.color = "";
    }

    // Card 4 — Unrealized P&L
    const unrealEl = $("#kpi-unrealized");
    unrealEl.textContent = fmtEur(d.unrealized_pl_total);
    setSignClass(unrealEl, d.unrealized_pl_total);
    const unrealSub = $("#kpi-unrealized-sub");
    if (d.unrealized_pl_total_pct != null) {
      const sign = d.unrealized_pl_total >= 0 ? "▲" : "▼";
      unrealSub.innerHTML = `<span class="badge ${d.unrealized_pl_total >= 0 ? "badge-positive" : "badge-negative"}">${sign} ${fmtPct(d.unrealized_pl_total_pct)} vs cost basis</span>`;
    } else {
      unrealSub.textContent = "—";
    }

    // Card 5 — Realized P&L (derived: true_total_pl - unrealized_pl_total)
    const realizedEl = $("#kpi-realized");
    const realizedSub = $("#kpi-realized-sub");
    if (d.true_total_pl != null && d.unrealized_pl_total != null) {
      const realizedPl = d.true_total_pl - d.unrealized_pl_total;
      realizedEl.textContent = fmtEur(realizedPl);
      setSignClass(realizedEl, realizedPl);
      realizedSub.textContent = "closed trades";
    } else {
      realizedEl.textContent = "—";
      realizedSub.textContent = "no deposit data";
    }

    // Card 6 — Positions
    const etfCount = positions.filter(p => p.asset_type === "ETF").length;
    const stockCount = positions.filter(p => p.asset_type === "STOCK").length;
    $("#kpi-positions").textContent = d.num_positions || 0;
    $("#kpi-positions-sub").textContent = `${etfCount} ETFs · ${stockCount} stocks`;

    // Allocation bar row
    const etfPct = d.etf_allocation_pct || 0;
    const stockPct = d.stock_allocation_pct || 0;
    const etfValue = totalValue * (etfPct / 100);
    const stockValue = totalValue * (stockPct / 100);

    $("#alloc-stocks-label").innerHTML = `<strong>${fmtEur(stockValue)}</strong> · <span class="alloc-pct">${stockPct.toFixed(1)}%</span>`;
    $("#alloc-etfs-label").innerHTML = `<strong>${fmtEur(etfValue)}</strong> · <span class="alloc-pct">${etfPct.toFixed(1)}%</span>`;

    // Bar: stocks on left (orange), etfs on right (teal)
    $("#alloc-stocks-bar").style.width = stockPct + "%";
    $("#alloc-etfs-bar").style.width = etfPct + "%";
  }

  // ─── Charts ───
  function renderCharts() {
    const d = portfolioData;
    const positions = d.positions || [];

    // Destroy existing charts
    Object.values(charts).forEach((c) => c.destroy());
    charts = {};

    // 1. Top 10 by weight
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

    if (sectorLabels.length === 0) {
      const sectorWrap = $("#chart-sector")?.parentElement;
      if (sectorWrap) {
        sectorWrap.innerHTML = '<div class="chart-empty"><span class="chart-empty-icon">📊</span><span class="chart-empty-text">No data available</span><span class="chart-empty-sub">Refresh portfolio to populate charts</span></div>';
      }
    } else {
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
            tooltip: {
              callbacks: {
                label: function(context) {
                  const total = context.dataset.data.reduce((a, b) => a + b, 0);
                  const pct = total > 0
                    ? ((context.parsed / total) * 100).toFixed(1) + '%'
                    : '0%';
                  if (document.body.classList.contains('privacy-mode')) {
                    return context.label + ': ' + pct;
                  }
                  const eur = context.parsed.toLocaleString('de-DE', {
                    style: 'currency', currency: 'EUR',
                    minimumFractionDigits: 0, maximumFractionDigits: 0
                  });
                  return context.label + ': ' + eur + ' (' + pct + ')';
                }
              }
            },
            legend: {
              display: true,
              position: "bottom",
              labels: {
                color: "#888",
                font: { family: "Inter", size: 10 },
                boxWidth: 12,
                generateLabels: function(chart) {
                  const defaults = Chart.overrides.doughnut.plugins.legend.labels.generateLabels(chart);
                  defaults.forEach(lbl => {
                    if (lbl.text && lbl.text.length > 24) {
                      lbl.text = lbl.text.substring(0, 22) + "…";
                    }
                  });
                  return defaults;
                }
              }
            },
          },
        },
      });
    }

    // 4. Geographic breakdown
    const geoMap = {};
    positions.forEach(p => {
      const key = p.country || 'Other';
      geoMap[key] = (geoMap[key] || 0) + (p.current_value_eur || 0);
    });
    const geoLabels = Object.keys(geoMap);
    const geoValues = Object.values(geoMap);
    charts.geo = new Chart(document.getElementById('chart-geo'), {
      type: 'doughnut',
      data: {
        labels: geoLabels,
        datasets: [{ data: geoValues, backgroundColor: generateColors(geoLabels.length),
                     borderColor: '#1a1a1a', borderWidth: 2 }]
      },
      options: {
        responsive: true, maintainAspectRatio: false, cutout: '55%',
        plugins: {
          tooltip: {
            callbacks: {
              label: function(context) {
                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                const pct = total > 0
                  ? ((context.parsed / total) * 100).toFixed(1) + '%'
                  : '0%';
                if (document.body.classList.contains('privacy-mode')) {
                  return context.label + ': ' + pct;
                }
                const eur = context.parsed.toLocaleString('de-DE', {
                  style: 'currency', currency: 'EUR',
                  minimumFractionDigits: 0, maximumFractionDigits: 0
                });
                return context.label + ': ' + eur + ' (' + pct + ')';
              }
            }
          },
          legend: { display: true, position: 'bottom',
                    labels: { color: '#888', font: { family: 'Inter', size: 10 },
                              boxWidth: 12,
                              generateLabels: function(chart) {
                                const d = Chart.overrides.doughnut.plugins.legend
                                            .labels.generateLabels(chart);
                                d.forEach(l => { if (l.text && l.text.length > 24)
                                  l.text = l.text.substring(0, 22) + '…'; });
                                return d;
                              }}}
        }
      }
    });
  }

  // ─── Positions Table ───
  function renderPositions() {
    const tableHash = (currentFilter + sortKey + sortDir) +
      positionsHash(portfolioData.positions || []);
    if (tableHash === _lastTableHash) return;
    _lastTableHash = tableHash;

    if (!portfolioData || !portfolioData.positions) {
      elPositionsBody.innerHTML = '<tr><td colspan="11"><div class="positions-error"><i data-lucide="alert-circle" class="icon-sm"></i><span>Failed to load positions</span><button class="btn btn-outline btn-sm" onclick="loadPortfolioRaw()">Retry</button></div></td></tr>';
      lucide.createIcons();
      return;
    }

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
        <td class="private-value">${fmtEur(p.current_value_eur)}</td>
        <td class="${plClass}">${p.unrealized_pl_pct != null ? p.unrealized_pl_pct.toFixed(2) + "%" : "—"}</td>
        <td>${p.current_price != null ? p.current_price.toFixed(2) : "—"}</td>
        <td><span class="private-value">${p.quantity ?? "—"}</span></td>
        <td>${p.weight != null ? p.weight.toFixed(1) + "%" : "—"}</td>
        <td>${p.asset_type || "—"}</td>
        <td>${p.avg_buy_price != null ? p.avg_buy_price.toFixed(2) : "—"}</td>
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
            <div class="detail-item"><label>52w High</label><span class="private-value">${p["52w_high"] != null ? p["52w_high"].toFixed(2) : "—"}</span></div>
            <div class="detail-item"><label>52w Low</label><span class="private-value">${p["52w_low"] != null ? p["52w_low"].toFixed(2) : "—"}</span></div>
            <div class="detail-item"><label>Dist from 52w High</label><span>${p.distance_from_52w_high_pct != null ? p.distance_from_52w_high_pct.toFixed(1) + "%" : "—"}</span></div>
            <div class="detail-item"><label>30d Perf</label><span>${p.perf_30d != null ? p.perf_30d.toFixed(1) + "%" : "—"}</span></div>
            <div class="detail-item"><label>90d Perf</label><span>${p.perf_90d != null ? p.perf_90d.toFixed(1) + "%" : "—"}</span></div>
            <div class="detail-item"><label>YTD Perf</label><span>${p.perf_ytd != null ? p.perf_ytd.toFixed(1) + "%" : "—"}</span></div>
            <div class="detail-item"><label>1Y Perf</label><span>${p.perf_1y != null ? p.perf_1y.toFixed(1) + "%" : "—"}</span></div>
            <div class="detail-item"><label>P/E Ratio</label><span>${p.pe_ratio != null && isFinite(p.pe_ratio) ? Number(p.pe_ratio).toFixed(1) : "—"}</span></div>
            <div class="detail-item"><label>Value Score</label><span>${p.value_score != null ? p.value_score.toFixed(2) : "—"}</span></div>
            ${p.buy_priority_blocked_reason ? `<div class="detail-item reason"><label>Blocked</label><span>${esc(p.buy_priority_blocked_reason)}</span></div>` : ""}
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
    const positions = portfolioData.positions || [];

    // Build a symbol->position lookup for deriving unrealized_pl_eur
    const posBySymbol = {};
    positions.forEach(p => { if (p.symbol) posBySymbol[p.symbol] = p; });

    function deriveEurPl(item) {
      const pos = posBySymbol[item.symbol];
      if (pos && pos.current_price != null && pos.avg_buy_price != null && pos.quantity != null) {
        return (pos.current_price - pos.avg_buy_price) * pos.quantity;
      }
      return null;
    }

    const winnersEl = $("#top-winners");
    const losersEl = $("#top-losers");

    winnersEl.innerHTML = winners
      .map(
        (w) => {
          const pl_pct = w.pl_pct != null ? w.pl_pct.toFixed(2) + "%" : "—";
          const pl_eur = deriveEurPl(w);
          return `
      <div class="wl-item">
        <span>${esc(w.name)} (${esc(w.symbol || "")})</span>
        <div style="text-align:right">
          <span class="wl-item-pl pl-positive">${pl_pct}</span>
          <span class="private-value" style="display:block;font-size:0.68rem;color:var(--text-dim)">${fmtEur(pl_eur)}</span>
        </div>
      </div>
    `;
        }
      )
      .join("");

    losersEl.innerHTML = losers
      .map(
        (l) => {
          const pl_pct = l.pl_pct != null ? l.pl_pct.toFixed(2) + "%" : "—";
          const pl_eur = deriveEurPl(l);
          return `
      <div class="wl-item">
        <span>${esc(l.name)} (${esc(l.symbol || "")})</span>
        <div style="text-align:right">
          <span class="wl-item-pl pl-negative">${pl_pct}</span>
          <span class="private-value" style="display:block;font-size:0.68rem;color:var(--text-dim)">${fmtEur(pl_eur)}</span>
        </div>
      </div>
    `;
        }
      )
      .join("");
  }

  // ─── Concentration Metrics ───
  function renderConcentration() {
    if (!portfolioData?.positions) return;
    const positions = portfolioData.positions;

    if (!positions || positions.length === 0) {
      const topEl = document.getElementById('card-top-holding');
      if (topEl) {
        topEl.querySelector('.card-value').textContent = '—';
        topEl.querySelector('.card-sub').textContent = 'No positions';
      }
      const top5El = document.getElementById('card-top5-weight');
      if (top5El) top5El.querySelector('.card-value').textContent = '—';
      const hhiEl = document.getElementById('card-hhi');
      if (hhiEl) {
        hhiEl.querySelector('.card-value').textContent = '—';
        const pill = hhiEl.querySelector('.hhi-pill');
        if (pill) { pill.className = 'card-sub hhi-pill'; pill.textContent = 'No data'; }
      }
      return;
    }

    // Top holding
    const top = positions.reduce((a, b) =>
      (b.weight||0) > (a.weight||0) ? b : a, positions[0]);
    const topEl = document.getElementById('card-top-holding');
    if (topEl) {
      topEl.querySelector('.card-value').textContent =
        (top.weight||0).toFixed(1) + '%';
      topEl.querySelector('.card-sub').textContent =
        (top.name || '').substring(0, 22);
    }

    // Top 5
    const top5 = [...positions].sort((a,b) => (b.weight||0)-(a.weight||0))
      .slice(0,5).reduce((s,p) => s+(p.weight||0), 0);
    const top5El = document.getElementById('card-top5-weight');
    if (top5El) {
      const val = top5El.querySelector('.card-value');
      val.textContent = top5.toFixed(1) + '%';
      val.style.color = ''; // neutral — no colour
      const top5Sub = top5El.querySelector('#kpi-top5-sub');
      if (top5Sub) {
        const sorted = [...positions].sort((a,b) => (b.weight||0)-(a.weight||0)).slice(0,5);
        top5Sub.textContent = sorted.map(p => p.symbol || p.name || '').join(' · ');
      }
    }

    // HHI
    const hhi = Math.round(positions.reduce((s,p) =>
      s + Math.pow((p.weight||0)/100, 2), 0) * 10000);
    const hhiEl = document.getElementById('card-hhi');
    if (hhiEl) {
      const val = hhiEl.querySelector('.card-value');
      const pill = hhiEl.querySelector('.hhi-pill');
      val.textContent = hhi.toLocaleString();
      val.style.color = '';
      if (hhi < 1000) {
        pill.className = 'card-sub hhi-pill diversified';
        pill.textContent = 'Diversified';
      } else if (hhi <= 1800) {
        pill.className = 'card-sub hhi-pill concentrated';
        pill.textContent = 'Concentrated';
      } else {
        pill.className = 'card-sub hhi-pill high-risk';
        pill.textContent = 'High Risk';
      }
    }
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

  // ─── Indexa Capital ───
  let indexaLoaded = false;
  let indexaLoading = false;
  let indexaPortfolio = null;
  let indexaPerformance = null;
  let indexaTransactions = null;
  let indexaUserInfo = null;
  let indexaChartRange = "all";

  function switchView(view) {
    const isIndexa = view === "indexa";
    document.body.classList.toggle("view-indexa", isIndexa);
    document.body.classList.toggle("view-degiro", !isIndexa);

    const degiroView = document.getElementById("degiro-view");
    const indexaView = document.getElementById("indexa-view");
    if (degiroView) degiroView.classList.toggle("hidden", isIndexa);
    if (indexaView) indexaView.classList.toggle("hidden", !isIndexa);

    const tabDe = document.getElementById("tab-degiro");
    const tabIn = document.getElementById("tab-indexa");
    if (tabDe) {
      tabDe.classList.toggle("active", !isIndexa);
      tabDe.setAttribute("aria-selected", String(!isIndexa));
    }
    if (tabIn) {
      tabIn.classList.toggle("active", isIndexa);
      tabIn.setAttribute("aria-selected", String(isIndexa));
    }

    const refreshIndexaBtn = document.getElementById("btn-refresh-indexa");
    if (refreshIndexaBtn) refreshIndexaBtn.classList.toggle("hidden", !isIndexa);

    if (isIndexa && !indexaLoaded && !indexaLoading) {
      loadIndexaData();
    }
  }

  async function loadIndexaData() {
    if (indexaLoading) return;
    indexaLoading = true;
    showIndexaEmpty("Loading Indexa portfolio…", "", false);
    try {
      const [pRes, perfRes, txRes, userRes] = await Promise.all([
        apiFetch("/api/indexa/portfolio"),
        apiFetch("/api/indexa/performance"),
        apiFetch("/api/indexa/transactions"),
        apiFetch("/api/indexa/user-info"),
      ]);

      if (!pRes.ok || !perfRes.ok) {
        const failing = pRes.ok ? perfRes : pRes;
        let detail = "";
        try { const j = await failing.json(); detail = j.detail || ""; } catch (e) { /* ignore */ }
        const status = failing.status;
        if (status === 503) {
          showIndexaEmpty("Indexa Capital not configured", detail || "Set INDEXA_API_TOKEN to enable this view.", true);
        } else if (status === 401) {
          showIndexaEmpty("Authentication required", "Reload the page and log back in.", true);
        } else {
          showIndexaEmpty("Indexa unavailable", detail || ("Upstream returned " + status + "."), true);
        }
        return;
      }

      indexaPortfolio = await pRes.json();
      indexaPerformance = await perfRes.json();
      if (txRes.ok) {
        const txData = await txRes.json();
        indexaTransactions = txData.transactions || [];
      }
      if (userRes.ok) {
        indexaUserInfo = await userRes.json();
      }
      indexaLoaded = true;
      renderIndexa();
    } catch (err) {
      console.error("Indexa load error:", err);
      showIndexaEmpty("Indexa unavailable", err.message || "Network error", true);
    } finally {
      indexaLoading = false;
    }
  }

  function showIndexaEmpty(title, msg, showRetry) {
    const empty = $("#indexa-empty");
    const dash = $("#indexa-dashboard");
    if (!empty || !dash) return;
    empty.classList.remove("hidden");
    dash.classList.add("hidden");
    const t = $("#indexa-empty-title");
    const m = $("#indexa-empty-msg");
    const retry = $("#btn-indexa-retry");
    if (t) t.textContent = title;
    if (m) m.textContent = msg || "";
    if (retry) retry.classList.toggle("hidden", !showRetry);
    lucide.createIcons();
  }

  function renderIndexa() {
    if (!indexaPortfolio) return;
    const empty = $("#indexa-empty");
    const dash = $("#indexa-dashboard");
    if (empty) empty.classList.add("hidden");
    if (dash) dash.classList.remove("hidden");
    renderIndexaKPIs();
    renderIndexaAllocationChart();
    renderIndexaPerformanceChart();
    renderIndexaFunds();
    if (privacyMode) document.body.classList.add("privacy-mode");
    lucide.createIcons();

    document.querySelectorAll(".range-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        indexaChartRange = btn.dataset.range;
        document.querySelectorAll(".range-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        renderIndexaPerformanceChart();
      });
    });
  }

  function indexaInvestedTotal() {
    const pf = indexaPortfolio || {};
    const perf = indexaPerformance || {};
    const pr = perf.raw || {};
    const raw = pf.raw || {};
    const candidates = [
      pf.total_invested,
      perf.investment,
      pr.return && pr.return.investment,
      pr.return && pr.return.total_invested,
      pr.return && pr.return.invested_amount,
      raw.total_invested,
      raw.invested_amount,
    ];
    for (const c of candidates) if (c != null && isFinite(c)) return c;
    return null;
  }

  function indexaReturnEur() {
    const perf = indexaPerformance || {};
    const pr = perf.raw || {};
    const candidates = [
      perf.pl,
      pr.return && pr.return.pl,
      pr.return && pr.return.return_currency,
      pr.return && pr.return.return_amount,
      pr.return_currency,
      pr.return_amount,
    ];
    for (const c of candidates) if (c != null && isFinite(c)) return c;
    const v = indexaPortfolio && indexaPortfolio.total_value;
    const inv = indexaInvestedTotal();
    if (v != null && inv != null) return v - inv;
    return null;
  }

  function indexaReturnPct() {
    const perf = indexaPerformance || {};
    const pr = perf.raw || {};
    // Indexa returns fractional (0.527 = 52.7%); convert to percent.
    if (perf.time_return != null && isFinite(perf.time_return)) return perf.time_return * 100;
    if (pr.return && pr.return.time_return != null && isFinite(pr.return.time_return)) {
      return pr.return.time_return * 100;
    }
    const candidates = [
      pr.return && pr.return.return_percentage,
      pr.return && pr.return.twror_percentage,
      pr.return_percentage,
    ];
    for (const c of candidates) if (c != null && isFinite(c)) return c;
    const r = indexaReturnEur();
    const inv = indexaInvestedTotal();
    if (r != null && inv != null && inv > 0) return (r / inv) * 100;
    return null;
  }

  function indexaLastContribution() {
    const arr = Array.isArray(indexaTransactions) ? indexaTransactions : [];
    const deposits = arr.filter(t => t.amount != null && t.amount > 0);
    if (!deposits.length) return null;
    deposits.sort((a, b) => String(b.date || "").localeCompare(String(a.date || "")));
    const last = deposits[0];
    return { amount: last.amount, date: last.date };
  }

  function renderIndexaKPIs() {
    const pf = indexaPortfolio || {};
    const value = pf.total_value;
    const invested = indexaInvestedTotal();
    const retEur = indexaReturnEur();
    const retPct = indexaReturnPct();
    const last = indexaLastContribution();
    const numFunds = (pf.positions || []).length;

    $("#indexa-kpi-value").textContent = fmtEur(value);
    $("#indexa-kpi-value-sub").textContent = numFunds + (numFunds === 1 ? " fund" : " funds");

    $("#indexa-kpi-invested").textContent = fmtEur(invested);
    $("#indexa-kpi-invested-sub").textContent = invested != null ? "principal" : "not reported";

    const retEurEl = $("#indexa-kpi-return-eur");
    retEurEl.textContent = fmtEur(retEur);
    setSignClass(retEurEl, retEur);
    $("#indexa-kpi-return-eur-sub").textContent = "since inception";

    const retPctEl = $("#indexa-kpi-return-pct");
    retPctEl.textContent = retPct != null ? fmtPct(retPct) : "—";
    setSignClass(retPctEl, retPct);
    // Period returns in sub-text
    const perf = indexaPerformance || {};
    const periods = [];
    if (perf.time_return_last_year != null) periods.push("1Y: " + fmtPct(perf.time_return_last_year * 100));
    if (perf.time_return_last_month != null) periods.push("1M: " + fmtPct(perf.time_return_last_month * 100));
    if (perf.time_return_last_week != null) periods.push("1W: " + fmtPct(perf.time_return_last_week * 100));
    $("#indexa-kpi-return-pct-sub").textContent = periods.length ? periods.join(" · ") : "since inception";

    if (last) {
      $("#indexa-kpi-last-contrib").textContent = fmtEur(last.amount);
      $("#indexa-kpi-last-contrib-sub").textContent = last.date ? new Date(last.date).toLocaleDateString() : "—";
    } else {
      $("#indexa-kpi-last-contrib").textContent = "—";
      $("#indexa-kpi-last-contrib-sub").textContent = "no data";
    }

    let annualEl = $("#indexa-kpi-annual-return");
    const annual = perf.time_return_annual != null ? perf.time_return_annual * 100 : null;
    annualEl.textContent = annual != null ? fmtPct(annual) : "—";
    setSignClass(annualEl, annual);

    const volEl = $("#indexa-kpi-volatility");
    const vol = perf.volatility != null ? perf.volatility * 100 : null;
    volEl.textContent = vol != null ? vol.toFixed(2) + "%" : "—";

    const sharpeEl = $("#indexa-kpi-sharpe");
    const sharpe = perf.sharpe_ratio;
    sharpeEl.textContent = sharpe != null ? sharpe.toFixed(2) : "—";
    setSignClass(sharpeEl, sharpe);

    // Max Drawdown
    const ddEl = $("#indexa-kpi-drawdown");
    const dd = perf.max_drawdown;
    ddEl.textContent = dd != null ? fmtPct(dd * 100) : "—";
    setSignClass(ddEl, dd);
    // Drawdown EUR + period dates
    const ddSub = [];
    if (perf.max_drawdown_EUR != null) ddSub.push(fmtEur(perf.max_drawdown_EUR));
    if (perf.max_drawdown_start && perf.max_drawdown_end) {
      const fmtD = s => {
        const c = String(s).replace(/-/g, '');
        const d = new Date(c.slice(0,4) + '-' + c.slice(4,6) + '-' + c.slice(6,8));
        return d.toLocaleDateString("en", { month: "short", year: "2-digit" });
      };
      ddSub.push(fmtD(perf.max_drawdown_start) + " → " + fmtD(perf.max_drawdown_end));
    }
    const ddSubEl = $("#indexa-kpi-drawdown-sub");
    if (ddSubEl) ddSubEl.textContent = ddSub.join(" · ");

    // Risk Profile
    const riskEl = $("#indexa-kpi-risk");
    const riskSubEl = $("#indexa-kpi-risk-sub");
    const ui = indexaUserInfo || {};
    const riskTotal = ui.risk_total;
    if (riskTotal != null) {
      riskEl.textContent = riskTotal + "/10";
      riskSubEl.textContent = (ui.pbc_risk || "") + (ui.expected_return != null ? " · " + (ui.expected_return * 100).toFixed(1) + "% exp." : "");
    } else {
      riskEl.textContent = "—";
      riskSubEl.textContent = "not available";
    }
  }

  function indexaFundEntries() {
    const positions = (indexaPortfolio && indexaPortfolio.positions) || [];
    return positions.map(p => {
      const instr = p.instrument || {};
      const name = p.name || instr.name || p.instrument_name || "Unknown";
      const isin = p.isin || instr.isin || p.isin_code || instr.isin_code || "";
      const amount = (p.amount != null ? p.amount
                    : p.value != null ? p.value
                    : p.amount_eur != null ? p.amount_eur
                    : p.market_value != null ? p.market_value
                    : null);
      const costAmount = p.cost_amount != null ? p.cost_amount : null;
      const percentage = p.percentage != null ? p.percentage : (p.weight != null ? p.weight : null);
      const assetClass = p.asset_class || instr.asset_class || null;
      return { name, isin, amount, costAmount, percentage, assetClass };
    });
  }

  function renderIndexaAllocationChart() {
    const canvas = $("#chart-indexa-allocation");
    if (!canvas) return;
    if (charts.indexaAllocation) { charts.indexaAllocation.destroy(); charts.indexaAllocation = null; }
    const entries = indexaFundEntries().filter(e => e.amount != null && e.amount > 0);
    if (!entries.length) {
      const wrap = canvas.parentElement;
      if (wrap) wrap.innerHTML = '<div class="chart-empty"><span class="chart-empty-icon">📊</span><span class="chart-empty-text">No allocation data</span></div>';
      return;
    }
    const labels = entries.map(e => truncate(e.name, 30));
    const values = entries.map(e => e.amount);
    const colors = generateColors(entries.length);
    charts.indexaAllocation = new Chart(canvas, {
      type: "doughnut",
      data: { labels: labels, datasets: [{ data: values, backgroundColor: colors, borderColor: "#1a1a1a", borderWidth: 2 }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "55%",
        plugins: {
          tooltip: {
            callbacks: {
              label: function(ctx) {
                const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                const pct = total > 0 ? ((ctx.parsed / total) * 100).toFixed(1) + "%" : "0%";
                if (document.body.classList.contains("privacy-mode")) {
                  return ctx.label + ": " + pct;
                }
                const eur = ctx.parsed.toLocaleString("de-DE", {
                  style: "currency", currency: "EUR",
                  minimumFractionDigits: 0, maximumFractionDigits: 0,
                });
                return ctx.label + ": " + eur + " (" + pct + ")";
              },
            },
          },
          legend: {
            display: true,
            position: "bottom",
            labels: {
              color: "#888",
              font: { family: "Inter", size: 10 },
              boxWidth: 12,
              generateLabels: function(chart) {
                const d = Chart.overrides.doughnut.plugins.legend.labels.generateLabels(chart);
                d.forEach(l => { if (l.text && l.text.length > 24) l.text = l.text.substring(0, 22) + "…"; });
                return d;
              },
            },
          },
        },
      },
    });
  }

  function indexaPerformanceSeries() {
    const perf = indexaPerformance || {};
    const raw = perf.raw || {};
    const candidates = [
      Array.isArray(perf.series) && perf.series.length ? perf.series : null,
      raw.return && raw.return.time_series,
      raw.return && raw.return.returns,
      raw.time_series,
      Array.isArray(raw.performance) ? raw.performance : null,
    ];
    for (const c of candidates) {
      if (Array.isArray(c) && c.length) return c;
    }
    return [];
  }

  function renderIndexaPerformanceChart() {
    const canvas = $("#chart-indexa-performance");
    if (!canvas) return;
    if (charts.indexaPerformance) { charts.indexaPerformance.destroy(); charts.indexaPerformance = null; }
    const series = indexaPerformanceSeries();
    let entries = series.map(s => {
      const date = s.date || s.value_date || s.day;
      const value = (s.value != null ? s.value
                  : s.amount != null ? s.amount
                  : s.total_amount != null ? s.total_amount
                  : s.return_amount != null ? s.return_amount
                  : null);
      const invested = (s.invested != null ? s.invested
                     : s.total_invested != null ? s.total_invested
                     : s.cash_amount != null ? s.cash_amount
                     : null);
      return { date: date, value: value, invested: invested };
    }).filter(e => e.date != null && e.value != null);
    entries.sort((a, b) => String(a.date).localeCompare(String(b.date)));

    if (entries.length && indexaChartRange !== "all") {
      const dayMap = { "1m": 30, "6m": 180, "1y": 365, "5y": 1825 };
      const days = dayMap[indexaChartRange];
      if (days) {
        // Parse YYYYMMDD or YYYY-MM-DD safely
        function parseDate(s) {
          const c = String(s).replace(/-/g, '');
          return new Date(c.slice(0,4) + '-' + c.slice(4,6) + '-' + c.slice(6,8));
        }
        const lastDate = parseDate(entries[entries.length - 1].date);
        const cutoff = new Date(lastDate.getTime() - days * 86400000);
        entries = entries.filter(e => parseDate(e.date) >= cutoff);
      }
    }

    if (!entries.length) {
      const wrap = canvas.parentElement;
      if (wrap) wrap.innerHTML = '<div class="chart-empty"><span class="chart-empty-icon">📈</span><span class="chart-empty-text">No performance data yet</span></div>';
      return;
    }

    const isPrivacy = document.body.classList.contains("privacy-mode");
    const labels = entries.map(e => e.date);
    const values = entries.map(e => e.value);
    const datasets = [{
      label: "Portfolio",
      data: values,
      borderColor: "#01696f",
      backgroundColor: "rgba(1,105,111,0.08)",
      fill: true,
      tension: 0.3,
      pointRadius: 0,
      borderWidth: 2,
    }];
    if (entries.some(e => e.invested != null)) {
      datasets.push({
        label: "Invested",
        data: entries.map(e => e.invested != null ? e.invested : null),
        borderColor: "#d97706",
        backgroundColor: "transparent",
        fill: false,
        tension: 0,
        pointRadius: 0,
        borderWidth: 2,
        borderDash: [4, 3],
        spanGaps: true,
      });
    }

    charts.indexaPerformance = new Chart(canvas, {
      type: "line",
      data: { labels: labels, datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: true, position: "bottom", labels: { color: "#888", font: { family: "Inter", size: 10 } } },
          tooltip: {
            enabled: true,
            callbacks: {
              label: function(ctx) {
                if (document.body.classList.contains("privacy-mode")) return ctx.dataset.label + ": ***";
                const v = ctx.parsed.y;
                if (Math.abs(v) >= 1000) return ctx.dataset.label + ": €" + (v / 1000).toFixed(1) + "k";
                return ctx.dataset.label + ": €" + v.toFixed(0);
              },
            },
          },
        },
        scales: {
          x: {
            ticks: {
              color: "#888",
              font: { family: "Inter", size: 10 },
              maxTicksLimit: 8,
              callback: function(val, idx) {
                const raw = String(this.getLabelForValue(val));
                const c = raw.replace(/-/g, '');
                if (c.length < 8) return raw;
                const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
                const m = parseInt(c.slice(4, 6), 10) - 1;
                const y = c.slice(2, 4);
                return m >= 0 && m < 12 ? months[m] + " '" + y : raw;
              },
            },
            grid: { color: "#2a2a2a" },
          },
          y: {
            ticks: {
              color: "#888",
              font: { family: "Inter", size: 10 },
              callback: function(v) {
                if (document.body.classList.contains("privacy-mode")) return "***";
                if (Math.abs(v) >= 1000) return "€" + (v / 1000).toFixed(0) + "k";
                return "€" + v.toFixed(0);
              },
            },
            grid: { color: "#2a2a2a" },
          },
        },
      },
    });
  }

  function fmtAssetClass(ac) {
    if (!ac) return "—";
    return ac.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
  }

  function renderIndexaFunds() {
    const body = $("#indexa-funds-body");
    if (!body) return;
    const entries = indexaFundEntries();
    if (!entries.length) {
      body.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-dim);padding:24px;">No funds found</td></tr>';
      return;
    }
    entries.sort((a, b) => (b.amount || 0) - (a.amount || 0));
    body.innerHTML = entries.map(e => {
      const gl = (e.amount != null && e.costAmount != null) ? e.amount - e.costAmount : null;
      const glClass = gl != null ? (gl >= 0 ? "positive" : "negative") : "";
      const glText = gl != null ? (gl >= 0 ? "+" : "") + fmtEur(gl) : "—";
      return `
      <tr>
        <td class="col-name">${esc(e.name)}</td>
        <td>${esc(e.isin || "—")}</td>
        <td><span style="font-size:0.72rem;color:var(--text-dim)">${esc(fmtAssetClass(e.assetClass))}</span></td>
        <td class="private-value">${fmtEur(e.amount)}</td>
        <td class="private-value">${fmtEur(e.costAmount)}</td>
        <td class="private-value ${glClass}">${glText}</td>
        <td>${e.percentage != null ? e.percentage.toFixed(1) + "%" : "—"}</td>
      </tr>
    `;
    }).join("");
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

  // ─── Stale Data Indicator ───
  function isDataStale() {
    if (!portfolioData || portfolioData.last_enriched_at == null) return true;
    return new Date(portfolioData.last_enriched_at).toDateString() !== new Date().toDateString();
  }

  function markDataStale() {
    var badge = document.getElementById("stale-badge");
    if (badge) {
      badge.classList.remove("hidden");
      var elapsed = lastSuccessfulRefresh ? formatTimeSince(lastSuccessfulRefresh) : "unknown";
      badge.querySelector(".stale-text").textContent = "Data may be stale (updated " + elapsed + ")";
    }
  }

  function clearStaleIndicator() {
    var badge = document.getElementById("stale-badge");
    if (badge) {
      if (isDataStale()) {
        badge.classList.remove("hidden");
      } else {
        badge.classList.add("hidden");
      }
    }
  }

  function formatTimeSince(timestamp) {
    var secs = Math.floor((Date.now() - timestamp) / 1000);
    if (secs < 60) return "just now";
    if (secs < 3600) return Math.floor(secs / 60) + "m ago";
    return Math.floor(secs / 3600) + "h ago";
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

    function showProgressToast(message) {
      const toast = document.createElement("div");
      toast.className = "toast toast-top-center toast-info";
      toast.setAttribute("role", "alert");
      toast.innerHTML =
        '<div class="enrichment-spinner"></div>' +
        '<span class="toast-message">' + esc(message) + '</span>';
      document.body.appendChild(toast);
      requestAnimationFrame(function() { toast.classList.add("toast-enter"); });
      return toast;
    }

    function updateToast(toast, opts) {
      if (!toast || !toast.parentNode) return;
      if (opts.message !== undefined) {
        var msgEl = toast.querySelector(".toast-message");
        if (msgEl) msgEl.textContent = opts.message;
      }
      if (opts.icon !== undefined || opts.variant !== undefined) {
        var iconName = opts.icon || "info";
        var variantClass = "toast-" + (opts.variant || "info");
        toast.className = "toast toast-top-center " + variantClass;
        var iconEl = toast.querySelector(".toast-icon");
        if (iconEl) {
          iconEl.setAttribute("data-lucide", iconName);
        } else {
          var spinner = toast.querySelector(".enrichment-spinner");
          if (spinner) {
            spinner.remove();
            toast.innerHTML = '<i data-lucide="' + iconName + '" class="toast-icon"></i>' +
              '<span class="toast-message">' + (toast.querySelector(".toast-message") || {}).textContent + '</span>' +
              '<button class="toast-close" aria-label="Dismiss">' +
              '<i data-lucide="x" class="icon-sm"></i></button>';
            toast.querySelector(".toast-close").addEventListener("click", function() { dismiss(toast); });
          }
        }
        lucide.createIcons({ nodes: [toast] });
      }
    }

    return { show: show, dismiss: dismiss, showProgressToast: showProgressToast, updateToast: updateToast };
  })();
})();
