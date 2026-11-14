(function () {
  "use strict";

  const MANIFEST_URL = "./data/manifest.json";
  const COLOMBO = "Asia/Colombo";

  let manifest = null;
  let experiments = {};
  let chart = null;

  function $(sel) {
    return document.querySelector(sel);
  }

  function fmtNum(n, digits) {
    if (n === null || n === undefined || Number.isNaN(n)) return "—";
    return Number(n).toFixed(digits);
  }

  function showError(msg) {
    const el = $("#load-error");
    if (el) {
      el.textContent = msg;
      el.hidden = false;
    }
  }

  function setTabs() {
    const buttons = document.querySelectorAll(".tab-btn");
    const panels = document.querySelectorAll(".panel");
    buttons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-tab");
        buttons.forEach((b) => b.setAttribute("aria-selected", b === btn ? "true" : "false"));
        panels.forEach((p) => p.classList.toggle("active", p.id === "panel-" + id));
        if (id === "forecast" && chart) {
          chart.resize();
        }
      });
    });
  }

  function siteOptions() {
    const map = {};
    (manifest.sites || []).forEach((s) => {
      map[s.site_id] = s.name || s.site_id;
    });
    return map;
  }

  function fillSelect(el, options, getLabel) {
    el.innerHTML = "";
    options.forEach((val) => {
      const opt = document.createElement("option");
      opt.value = val;
      opt.textContent = getLabel(val);
      el.appendChild(opt);
    });
  }

  function renderOverview() {
    const o = manifest.overview || {};
    $("#ov-lgbm").textContent = fmtNum(o.test_mae_lightgbm_kw, 3) + " kW";
    $("#ov-base").textContent = fmtNum(o.test_mae_baseline_kw, 3) + " kW";
    $("#ov-data").textContent = manifest.data_label || "SIMULATED";
    $("#ov-files").textContent = String(o.forecast_csv_files ?? "—");
    const beats = o.lightgbm_beats_baseline_on_test_mae;
  $("#ov-verdict").textContent =
      beats === true
        ? "On the held-out test split, LightGBM beats the physics baseline on overall MAE."
        : beats === false
          ? "On the held-out test split, LightGBM does not beat the physics baseline on overall MAE."
          : "—";
    $("#ov-version").textContent = manifest.latest_model_version || "—";
  }

  function integrateEnergy(rows) {
    if (!rows.length) return { model_kwh: 0, baseline_kwh: 0, system_kwh: 0 };
    const sorted = rows
      .map((r) => ({ ...r, t: new Date(r.timestamp).getTime() }))
      .sort((a, b) => a.t - b.t);
    let model = 0;
    let baseline = 0;
    let system = 0;
    for (let i = 1; i < sorted.length; i++) {
      const dtH = (sorted[i].t - sorted[i - 1].t) / 3600000;
      if (dtH <= 0) continue;
      const mid = (sorted[i - 1].pv_kw + sorted[i].pv_kw) / 2;
      const bmid = (sorted[i - 1].baseline_kw + sorted[i].baseline_kw) / 2;
      const smid = (sorted[i - 1].system_kw + sorted[i].system_kw) / 2;
      model += mid * dtH;
      baseline += bmid * dtH;
      system += smid * dtH;
    }
    const res = sorted[0].resolution;
    if (sorted.length === 1) {
      const h = res === "15min" ? 0.25 : 1;
      return {
        model_kwh: sorted[0].pv_kw * h,
        baseline_kwh: sorted[0].baseline_kw * h,
        system_kwh: sorted[0].system_kw * h,
      };
    }
    return { model_kwh: model, baseline_kwh: baseline, system_kwh: system };
  }

  function formatLocalTime(iso) {
    try {
      return new Date(iso).toLocaleString("en-LK", {
        timeZone: COLOMBO,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      });
    } catch {
      return iso;
    }
  }

  async function loadForecast(version, siteId, day) {
    const url = `./data/forecasts/${encodeURIComponent(version)}/${encodeURIComponent(siteId)}/${day}.json`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("Forecast file missing");
    return res.json();
  }

  async function loadExperiment(version) {
    if (experiments[version]) return experiments[version];
    const url = `./data/experiments/${encodeURIComponent(version)}.json`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("Experiment JSON missing");
    const data = await res.json();
    experiments[version] = data;
    return data;
  }

  function updateChart(labels, pv, baseline, title) {
    const canvas = $("#forecast-chart");
    if (!canvas || typeof Chart === "undefined") return;
    if (chart) chart.destroy();
    chart = new Chart(canvas.getContext("2d"), {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "LightGBM pv_kw",
            data: pv,
            borderColor: "#f4a261",
            backgroundColor: "rgba(244, 162, 97, 0.1)",
            borderWidth: 2,
            tension: 0.15,
            pointRadius: 0,
          },
          {
            label: "Physics baseline_kw",
            data: baseline,
            borderColor: "#2a9d8f",
            backgroundColor: "rgba(42, 157, 143, 0.08)",
            borderWidth: 1.5,
            tension: 0.15,
            pointRadius: 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          title: { display: true, text: title, color: "#f1f3f5" },
          legend: { labels: { color: "#f1f3f5" } },
        },
        scales: {
          x: {
            ticks: { color: "#adb5bd", maxRotation: 45, autoSkip: true, maxTicksLimit: 12 },
            grid: { color: "rgba(255,255,255,0.06)" },
          },
          y: {
            title: { display: true, text: "AC power (kW)", color: "#adb5bd" },
            ticks: { color: "#adb5bd" },
            grid: { color: "rgba(255,255,255,0.06)" },
          },
        },
      },
    });
  }

  function renderForecastTable(rows) {
    const tbody = $("#forecast-table tbody");
    tbody.innerHTML = "";
    rows.forEach((r) => {
      const tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        formatLocalTime(r.timestamp) +
        "</td><td>" +
        fmtNum(r.pv_kw, 3) +
        "</td><td>" +
        fmtNum(r.baseline_kw, 3) +
        "</td><td>" +
        fmtNum(r.system_kw, 2) +
        "</td>";
      tbody.appendChild(tr);
    });
  }

  function wireForecast() {
    const selVersion = $("#fc-version");
    const selSite = $("#fc-site");
    const selDay = $("#fc-day");
    const names = siteOptions();
    const versions = manifest.model_versions || [];
    const index = manifest.forecast_days_by_version || {};

    fillSelect(selVersion, versions, (v) => v);
    if (!versions.length) return;

    function refreshSites() {
      const v = selVersion.value;
      const siteIds = Object.keys(index[v] || {});
      fillSelect(selSite, siteIds, (id) => names[id] || id);
      if (siteIds.length) refreshDays();
    }

    function refreshDays() {
      const v = selVersion.value;
      const sid = selSite.value;
      const days = (index[v] && index[v][sid]) || [];
      fillSelect(selDay, days, (d) => d + " (Colombo midnight)");
      if (days.length) loadCurrentForecast();
    }

    async function loadCurrentForecast() {
      const v = selVersion.value;
      const sid = selSite.value;
      const day = selDay.value;
      if (!v || !sid || !day) return;
      try {
        const rows = await loadForecast(v, sid, day);
        rows.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
        const labels = rows.map((r) => formatLocalTime(r.timestamp));
        const pv = rows.map((r) => r.pv_kw);
        const base = rows.map((r) => r.baseline_kw);
        const title = (names[sid] || sid) + " · issue " + day;
        updateChart(labels, pv, base, title);
        const en = integrateEnergy(rows);
        $("#en-model").textContent = fmtNum(en.model_kwh, 2) + " kWh";
        $("#en-base").textContent = fmtNum(en.baseline_kwh, 2) + " kWh";
        $("#en-sys").textContent = fmtNum(en.system_kwh, 2) + " kWh";
        renderForecastTable(rows);
      } catch (e) {
        showError("Could not load forecast: " + e.message);
      }
    }

    selVersion.addEventListener("change", refreshSites);
    selSite.addEventListener("change", refreshDays);
    selDay.addEventListener("change", loadCurrentForecast);
    refreshSites();
  }

  function metricsTable(exp) {
    const test = (exp.metrics && exp.metrics.test) || {};
    const tbody = $("#report-metrics tbody");
    tbody.innerHTML = "";
    Object.keys(test).forEach((slice) => {
      const block = test[slice];
      if (!block || typeof block !== "object") return;
      ["lightgbm", "baseline"].forEach((model) => {
        const m = block[model] || {};
        const tr = document.createElement("tr");
        tr.innerHTML =
          "<td>" +
          slice +
          "</td><td>" +
          model +
          "</td><td>" +
          (m.n ?? "—") +
          "</td><td>" +
          fmtNum(m.mae_kw, 4) +
          "</td><td>" +
          fmtNum(m.rmse_kw, 4) +
          "</td><td>" +
          fmtNum(m.nmae, 4) +
          "</td>";
        tbody.appendChild(tr);
      });
    });
  }

  function simpleMarkdown(md) {
    return md
      .replace(/^### (.*)$/gm, "<h3>$1</h3>")
      .replace(/^## (.*)$/gm, "<h2>$1</h2>")
      .replace(/^# (.*)$/gm, "<h2>$1</h2>")
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\n\n/g, "</p><p>")
      .replace(/^(.+)$/gm, (line) => (line.startsWith("<") ? line : line))
      .replace(/<p><h/g, "<h")
      .replace(/<\/h([23])><\/p>/g, "</h$1>");
  }

  function wireReport() {
    const sel = $("#report-version");
    fillSelect(sel, manifest.model_versions || [], (v) => v);

    async function refresh() {
      const v = sel.value;
      if (!v) return;
      try {
        const exp = await loadExperiment(v);
        $("#report-data-label").textContent = exp.data_label || "SIMULATED";
        $("#report-verdict").textContent = exp.verdict || "—";
        metricsTable(exp);
        const mdEl = $("#report-md");
        const hasMd = manifest.experiment_markdown_available && manifest.experiment_markdown_available[v];
        if (hasMd) {
          const mdRes = await fetch(`./data/experiments/${encodeURIComponent(v)}.md`);
          if (mdRes.ok) {
            const text = await mdRes.text();
            mdEl.innerHTML = "<div class='md-body'>" + simpleMarkdown(text) + "</div>";
          } else {
            mdEl.innerHTML = "";
          }
        } else {
          mdEl.innerHTML = "";
        }
      } catch (e) {
        showError("Could not load experiment: " + e.message);
      }
    }

    sel.addEventListener("change", refresh);
    refresh();
  }

  async function init() {
    setTabs();
    try {
      const res = await fetch(MANIFEST_URL);
      if (!res.ok) throw new Error("manifest.json not found — run scripts/export_github_pages.py");
      manifest = await res.json();
      renderOverview();
      wireForecast();
      wireReport();
    } catch (e) {
      showError(e.message);
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();