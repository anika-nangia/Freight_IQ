/*
 * api-status.js - live model status panel.
 *
 * WHY THIS FILE EXISTS
 *   The app was previously 100% hard-coded: app.js contained no fetch(), no
 * XMLHttpRequest and no reference to /api, so nothing in the UI was ever driven by
 * the trained models. The backend and the models ran as a separate process that the
 * website never spoke to.
 *
 *   This adds a *live status panel* rather than rewriting the whole app. That is a
 *   deliberate scope choice: the existing hard-coded dashboards are left exactly as
 *   they are, and this panel reports, honestly, what the models currently say -
 *   including when they did not beat a baseline.
 *
 * DESIGN RULES
 *   1. Never break the page. Every failure path renders a visible "backend not
 *      reachable" note instead of throwing. The site must still work when opened
 *      straight off the filesystem with no server running.
 *   2. Never invent a number. If the API is up, show what it returns. If it is down,
 *      say so. Do not fall back to a plausible-looking figure.
 *   3. Show the honest verdicts, including the negative ones.
 */
(function () {
  "use strict";

  // Browsers block fetch() from file:// for cross-origin reasons, and a hard-coded
  // port would break the moment someone runs the API on another one. So: try the
  // port the page was served from first, then the documented dev default.
  function candidateBases() {
    var list = [];
    if (window.location && window.location.protocol === "http:") {
      list.push(window.location.origin);
    }
    list.push("http://127.0.0.1:8000");
    list.push("http://localhost:8000");
    return list;
  }

  function getJSON(path) {
    var bases = candidateBases();
    var i = 0;

    function attempt() {
      if (i >= bases.length) return Promise.reject(new Error("no backend reachable"));
      var base = bases[i++];
      var ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
      var timer = ctrl ? setTimeout(function () { ctrl.abort(); }, 3500) : null;

      return fetch(base + path, ctrl ? { signal: ctrl.signal } : undefined)
        .then(function (r) {
          if (timer) clearTimeout(timer);
          if (!r.ok) throw new Error("HTTP " + r.status);
          return r.json();
        })
        .catch(function (err) {
          if (timer) clearTimeout(timer);
          return attempt();
        });
    }
    return attempt();
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = String(text);
    return n;
  }

  function row(label, value, tone) {
    var d = el("div", "flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 py-2 border-b border-slate-100 last:border-0");
    d.appendChild(el("span", "text-sm text-slate-500", label));
    d.appendChild(el("span", "text-sm font-semibold " + (tone || "text-slate-800"), value));
    return d;
  }

  function renderOffline(host) {
    host.innerHTML = "";
    host.appendChild(el("div", "p-4 rounded-xl bg-amber-50 border border-amber-200 text-sm text-amber-900",
      "Backend not reachable. This page is showing its built-in demo data. " +
      "To see live model output, start the API and serve this page over HTTP " +
      "(see README.md)."));
  }

  function renderLoading(host) {
    host.innerHTML = "";
    host.appendChild(el("div", "p-4 text-sm text-slate-500", "Contacting the model API…"));
  }

  function renderReport(host, report, coverage) {
    host.innerHTML = "";

    var m2 = report["model_2_freight"] || {};
    var m1 = report["model_1_congestion"] || {};
    var c2 = (m2.candidates || {})[m2.deployed_model] || {};
    var c1 = (m1.candidates || {})[m1.deployed_model] || {};

    // ---- Model 2 -----------------------------------------------------------
    var f2 = el("div", "bg-white border border-slate-200 rounded-xl p-5");
    f2.appendChild(el("h3", "font-bold text-slate-800 mb-1", "Model 2 — Freight rate forecaster"));
    f2.appendChild(el("p", "text-xs text-slate-500 mb-3",
      m2.validation_scheme || "not trained"));
    f2.appendChild(row("Deployed model", m2.deployed_model || "n/a"));
    f2.appendChild(row("Walk-forward MAE", c2.mae_usd_mt != null ? c2.mae_usd_mt.toFixed(2) + " USD/MT" : "n/a"));
    f2.appendChild(row("Out-of-sample weeks", m2.out_of_sample_weeks != null ? m2.out_of_sample_weeks : "n/a"));
    var range = m2.regret_reduction_range_across_seeds_pct;
    f2.appendChild(row("Beats persistence by",
      Array.isArray(range) ? range[0].toFixed(1) + "% to " + range[1].toFixed(1) + "% (across seeds)" : "n/a",
      Array.isArray(range) ? "text-emerald-700" : "text-slate-800"));
    if (m2.significance_vs_persistence && m2.significance_vs_persistence.available) {
      f2.appendChild(row("Significance (95% CI)",
        m2.significance_vs_persistence.verdict,
        m2.significance_vs_persistence.significant_at_95 ? "text-emerald-700" : "text-amber-700"));
    }
    if (m2.headline_caveat) {
      f2.appendChild(el("p", "text-xs text-slate-500 mt-3 leading-relaxed", m2.headline_caveat));
    }

    // ---- Model 1 -----------------------------------------------------------
    var f1 = el("div", "bg-white border border-slate-200 rounded-xl p-5");
    f1.appendChild(el("h3", "font-bold text-slate-800 mb-1", "Model 1 — Port congestion"));
    f1.appendChild(el("p", "text-xs text-slate-500 mb-3",
      m1.target_warning ? "Predicts the port's own estimate, not a measured turnaround."
                        : (m1.validation_scheme || "not trained")));
    f1.appendChild(row("Deployed model", m1.deployed_model || "n/a",
      m1.deployed_is_baseline ? "text-amber-700" : "text-slate-800"));
    f1.appendChild(row("Held-out MAE", c1.mae_days != null ? c1.mae_days.toFixed(2) + " days" : "n/a"));
    f1.appendChild(row("Voyages / ports", (m1.n_voyages || "n/a") + " / " + (m1.n_ports || "n/a")));
    if (m1.deployed_rationale) {
      f1.appendChild(el("p", "text-xs text-amber-800 mt-3 leading-relaxed", m1.deployed_rationale));
    }

    var grid = el("div", "grid grid-cols-1 lg:grid-cols-2 gap-5");
    grid.appendChild(f2);
    grid.appendChild(f1);
    host.appendChild(grid);

    // ---- Data coverage -----------------------------------------------------
    if (coverage && coverage.datasets) {
      var c = el("div", "mt-5 bg-white border border-slate-200 rounded-xl p-5");
      c.appendChild(el("h3", "font-bold text-slate-800 mb-1", "Data coverage"));
      c.appendChild(el("p", "text-xs text-slate-500 mb-3",
        "Every dataset the system reads, and how far it can be trusted."));

      var order = { unverified: 0, unavailable: 1, estimated: 2, observed: 3 };
      var tiers = { unverified: ["bg-red-50 border-red-200 text-red-800", "Unverified"],
                    unavailable: ["bg-slate-50 border-slate-200 text-slate-600", "Unavailable"],
                    estimated: ["bg-amber-50 border-amber-200 text-amber-800", "Estimated"],
                    observed: ["bg-emerald-50 border-emerald-200 text-emerald-800", "Observed"] };

      coverage.datasets.slice().sort(function (a, b) {
        return (order[a.tier] === undefined ? 9 : order[a.tier]) -
               (order[b.tier] === undefined ? 9 : order[b.tier]);
      }).forEach(function (d) {
        var t = tiers[d.tier] || ["bg-slate-50 border-slate-200 text-slate-600", d.tier];
        var item = el("div", "flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2 py-3 border-b border-slate-100 last:border-0");
        var left = el("div");
        left.appendChild(el("div", "text-sm font-semibold text-slate-800", d.key));
        left.appendChild(el("div", "text-xs text-slate-500", d.description || ""));
        item.appendChild(left);
        item.appendChild(el("span", "shrink-0 text-xs font-bold px-2 py-1 rounded-lg border " + t[0], t[1]));
        c.appendChild(item);
      });
      host.appendChild(c);
    }
  }

  function init() {
    var host = document.getElementById("apiStatusBody");
    if (!host) return;
    renderLoading(host);

    Promise.all([getJSON("/api/model-report"), getJSON("/api/data-coverage")])
      .then(function (res) { renderReport(host, res[0], res[1]); })
      .catch(function () { renderOffline(host); });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.FreightIQApi = { getJSON: getJSON, refresh: init };
})();
