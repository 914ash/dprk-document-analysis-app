/* === DPRK SENTINEL — Application Logic === */
/* global Plotly */

(function () {
  "use strict";

  // ---- State ----
  let entityData = null;
  let networkData = null;
  let currentTab = "overview";
  let sidebarCollapsed = false;
  let chartInstances = {};
  let d3Simulation = null;
  let candidateStatuses = {};
  let guidedTourSteps = [];
  let guidedTourIndex = 0;

  // ---- Color Maps ----
  const TYPE_COLORS = {
    ORG: "#4f98a3",
    PERSON: "#5b8def",
    VESSEL: "#e8af34",
    LOCATION: "#6daa45",
  };

  const STATUS_COLORS = {
    approved: "#6daa45",
    pending: "#e8af34",
    rejected: "#dd6974",
  };

  const BADGE_CLASSES = {
    ORG: "badge-org",
    PERSON: "badge-person",
    VESSEL: "badge-vessel",
    LOCATION: "badge-location",
    approved: "badge-approved",
    pending: "badge-pending",
    rejected: "badge-rejected",
    final: "badge-final",
    midterm: "badge-midterm",
  };

  const SLICE_COLORS = {
    2020: "#4f98a3",
    2021: "#5b8def",
    2022: "#e8af34",
    2023: "#6daa45",
    2024: "#dd6974",
  };

  // ---- Initialization ----
  async function init() {
    setHeaderDate();
    setupNavigation();
    setupSidebarToggle();
    setupThemeToggle();

    try {
      const [erRes, ndRes] = await Promise.all([
        fetch("./data/entity_resolution.json"),
        fetch("./data/network_drift.json"),
      ]);
      entityData = await erRes.json();
      networkData = await ndRes.json();

      // Initialize candidate statuses from data
      entityData.candidate_pairs.forEach((cp) => {
        candidateStatuses[cp.candidate_id] = cp.status;
      });

      renderOverview();
      renderGuidanceRail();
      setupGuidedTour();
    } catch (err) {
      console.error("Failed to load data:", err);
    }
  }

  // ---- Header Date ----
  function setHeaderDate() {
    const now = new Date();
    const opts = {
      weekday: "short",
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      timeZoneName: "short",
    };
    document.getElementById("header-date").textContent =
      now.toLocaleDateString("en-US", opts);
  }

  // ---- Navigation ----
  function setupNavigation() {
    document.querySelectorAll(".nav-item").forEach((item) => {
      item.addEventListener("click", () => {
        const tab = item.dataset.tab;
        switchTab(tab);
      });
    });
  }

  function switchTab(tab) {
    if (tab === currentTab) return;
    currentTab = tab;

    // Update nav
    document.querySelectorAll(".nav-item").forEach((item) => {
      item.classList.toggle("active", item.dataset.tab === tab);
    });

    // Update panels
    document.querySelectorAll(".tab-panel").forEach((panel) => {
      const isActive = panel.id === "tab-" + tab;
      panel.classList.toggle("active", isActive);
    });

    // Render tab content
    switch (tab) {
      case "overview":
        renderOverview();
        break;
      case "entity-resolution":
        renderEntityResolution();
        break;
      case "network-drift":
        renderNetworkDrift();
        break;
      case "review-queue":
        renderReviewQueue();
        break;
      case "provenance":
        renderProvenance();
        break;
    }

    renderGuidanceRail();
  }

  // ---- Sidebar Toggle ----
  function setupSidebarToggle() {
    document
      .getElementById("sidebar-toggle-btn")
      .addEventListener("click", () => {
        sidebarCollapsed = !sidebarCollapsed;
        document
          .getElementById("app")
          .classList.toggle("sidebar-collapsed", sidebarCollapsed);
        const btn = document.getElementById("sidebar-toggle-btn");
        btn.querySelector("svg").style.transform = sidebarCollapsed
          ? "rotate(180deg)"
          : "";
      });
  }

  // ---- Theme Toggle ----
  function setupThemeToggle() {
    document.getElementById("theme-toggle").addEventListener("click", () => {
      const html = document.documentElement;
      const current = html.getAttribute("data-theme");
      const next = current === "dark" ? "light" : "dark";
      html.setAttribute("data-theme", next);

      const icon = document.getElementById("theme-icon-dark");
      if (next === "light") {
        icon.innerHTML =
          '<circle cx="8" cy="8" r="3" stroke="currentColor" stroke-width="1.5" fill="none"/><path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.05 3.05l1.41 1.41M11.54 11.54l1.41 1.41M3.05 12.95l1.41-1.41M11.54 4.46l1.41-1.41" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>';
      } else {
        icon.innerHTML =
          '<path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 12.5a5.5 5.5 0 010-11v11z" fill="currentColor"/>';
      }

      // Re-render active charts for theme
      if (currentTab === "network-drift" && networkData) {
        renderForceGraph(
          document.getElementById("graph-year-select").value
        );
        renderUMAP();
      }
    });
  }

  // ---- Animate Counter ----
  function animateValue(el, target, duration) {
    duration = duration || 800;
    const start = 0;
    const startTime = performance.now();

    function update(time) {
      const elapsed = time - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = Math.round(start + (target - start) * eased);
      el.textContent = current.toLocaleString();
      if (progress < 1) {
        requestAnimationFrame(update);
      }
    }
    requestAnimationFrame(update);
  }

  // ---- Badge HTML ----
  function badgeHTML(text, type) {
    const cls = BADGE_CLASSES[type] || BADGE_CLASSES[text.toLowerCase()] || "";
    return '<span class="badge ' + cls + '">' + escapeHTML(text) + "</span>";
  }

  function escapeHTML(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function getTabGuidance(tab) {
    const sources = [networkData, entityData];
    const guidance = {
      title: "",
      summary: "",
      howToRead: [],
      recommendedActions: [],
      glossary: [],
      tourText: "",
    };

    sources.forEach((source) => {
      if (!source) return;
      const methodology = source.methodology && source.methodology[tab];
      if (methodology) {
        if (!guidance.title && methodology.title) guidance.title = methodology.title;
        if (methodology.summary) {
          guidance.summary = guidance.summary
            ? guidance.summary + " " + methodology.summary
            : methodology.summary;
        }
        if (!guidance.tourText && methodology.tour_text) {
          guidance.tourText = methodology.tour_text;
        }
      }
      if (source.how_to_read && Array.isArray(source.how_to_read[tab])) {
        guidance.howToRead = guidance.howToRead.concat(source.how_to_read[tab]);
      }
      if (
        source.recommended_actions &&
        Array.isArray(source.recommended_actions[tab])
      ) {
        guidance.recommendedActions = guidance.recommendedActions.concat(
          source.recommended_actions[tab]
        );
      }
      if (Array.isArray(source.glossary)) {
        source.glossary.forEach((item) => {
          if (!item.tabs || item.tabs.indexOf(tab) !== -1) {
            guidance.glossary.push(item);
          }
        });
      }
    });

    return guidance;
  }

  function renderGuidanceRail() {
    const rail = document.querySelector(
      '.tab-panel.active .guidance-rail[data-guidance-for="' + currentTab + '"]'
    );
    if (!rail) return;

    const guidance = getTabGuidance(currentTab);
    const glossaryItems = guidance.glossary
      .slice(0, 3)
      .map(
        (item) =>
          '<div class="guidance-glossary-item">' +
          '<span class="guidance-glossary-term">' +
          escapeHTML(item.term) +
          "</span>" +
          '<span class="guidance-glossary-definition">' +
          escapeHTML(item.definition) +
          "</span>" +
          "</div>"
      )
      .join("");

    rail.innerHTML =
      '<div class="guidance-card guidance-card-primary">' +
      '<div class="guidance-kicker">How to work this view</div>' +
      '<div class="guidance-title">' +
      escapeHTML(guidance.title || "Analyst guidance") +
      "</div>" +
      '<p class="guidance-summary">' +
      escapeHTML(guidance.summary || "Use the guided tour to understand the metrics and recommended next actions.") +
      "</p>" +
      '<div class="guidance-actions">' +
      '<button class="guided-tour-inline" type="button" data-tour-tab="' +
      escapeHTML(currentTab) +
      '">Launch walkthrough</button>' +
      "</div>" +
      "</div>" +
      '<div class="guidance-card">' +
      '<div class="guidance-kicker">Read the signals</div>' +
      '<ul class="guidance-list">' +
      guidance.howToRead
        .slice(0, 4)
        .map((item) => "<li>" + escapeHTML(item) + "</li>")
        .join("") +
      "</ul>" +
      "</div>" +
      '<div class="guidance-card">' +
      '<div class="guidance-kicker">Recommended next actions</div>' +
      '<ul class="guidance-list">' +
      guidance.recommendedActions
        .slice(0, 4)
        .map((item) => "<li>" + escapeHTML(item) + "</li>")
        .join("") +
      "</ul>" +
      "</div>" +
      '<div class="guidance-card guidance-card-glossary">' +
      '<div class="guidance-kicker">Key terms</div>' +
      glossaryItems +
      "</div>";

    rail
      .querySelectorAll(".guided-tour-inline")
      .forEach((button) =>
        button.addEventListener("click", () => launchGuidedTour(button.dataset.tourTab))
      );
  }

  function buildGuidedTourSteps() {
    const tabs = [
      "overview",
      "entity-resolution",
      "network-drift",
      "review-queue",
      "provenance",
    ];
    guidedTourSteps = tabs.map((tab) => {
      const guidance = getTabGuidance(tab);
      return {
        tab: tab,
        title: guidance.title || tab,
        body:
          guidance.tourText ||
          guidance.summary ||
          "Review the signals, consult the glossary, and use the recommended actions to decide what to inspect next.",
      };
    });
  }

  function setupGuidedTour() {
    buildGuidedTourSteps();
    const launchButton = document.getElementById("guided-tour-start");
    const closeButton = document.getElementById("guided-tour-close");
    const prevButton = document.getElementById("guided-tour-prev");
    const nextButton = document.getElementById("guided-tour-next");

    launchButton.addEventListener("click", () => launchGuidedTour(currentTab));
    closeButton.addEventListener("click", closeGuidedTour);
    prevButton.addEventListener("click", () => moveGuidedTour(-1));
    nextButton.addEventListener("click", () => moveGuidedTour(1));

    if (!window.localStorage.getItem("dprk-guided-tour-seen")) {
      launchGuidedTour("overview");
    }
  }

  function launchGuidedTour(tab) {
    buildGuidedTourSteps();
    const startIndex = guidedTourSteps.findIndex((step) => step.tab === tab);
    guidedTourIndex = startIndex >= 0 ? startIndex : 0;
    document.getElementById("guided-tour").classList.add("visible");
    document.getElementById("guided-tour").setAttribute("aria-hidden", "false");
    renderGuidedTourStep();
  }

  function closeGuidedTour() {
    document.getElementById("guided-tour").classList.remove("visible");
    document.getElementById("guided-tour").setAttribute("aria-hidden", "true");
    window.localStorage.setItem("dprk-guided-tour-seen", "true");
  }

  function moveGuidedTour(direction) {
    const nextIndex = guidedTourIndex + direction;
    if (nextIndex < 0) return;
    if (nextIndex >= guidedTourSteps.length) {
      closeGuidedTour();
      return;
    }
    guidedTourIndex = nextIndex;
    renderGuidedTourStep();
  }

  function renderGuidedTourStep() {
    const step = guidedTourSteps[guidedTourIndex];
    if (!step) return;
    switchTab(step.tab);
    document.getElementById("guided-tour-title").textContent = step.title;
    document.getElementById("guided-tour-body").textContent = step.body;
    document.getElementById("guided-tour-progress").textContent =
      "Step " + (guidedTourIndex + 1) + " of " + guidedTourSteps.length;
    document.getElementById("guided-tour-prev").disabled = guidedTourIndex === 0;
    document.getElementById("guided-tour-next").textContent =
      guidedTourIndex === guidedTourSteps.length - 1 ? "Finish" : "Next";
  }

  // ============================================================
  //  TAB 1: OVERVIEW
  // ============================================================
  function renderOverview() {
    renderKPIs();
    renderEntityTypeChart();
    renderNetworkGrowthChart();
    renderTopDriftersTable();
  }

  function renderKPIs() {
    const erSummary = entityData.summary;
    const ndSummary = networkData.summary;

    const kpis = [
      {
        label: "Total Entities",
        value: ndSummary.total_entities,
        sub: "Tracked in network",
      },
      {
        label: "Total Mentions",
        value: erSummary.total_mentions,
        sub: "Extracted from reports",
      },
      {
        label: "Alias Candidates",
        value: erSummary.total_candidates,
        sub: "Pairs identified",
      },
      {
        label: "Pending Review",
        value: erSummary.pending,
        sub: "Awaiting analyst",
      },
      {
        label: "Reports Ingested",
        value: erSummary.total_reports,
        sub: "Source documents",
      },
      {
        label: "Network Slices",
        value: ndSummary.slices.length,
        sub: "Temporal snapshots",
      },
    ];

    const grid = document.getElementById("kpi-grid");
    grid.innerHTML = kpis
      .map(
        (k) =>
          '<div class="kpi-card">' +
          '<div class="kpi-label">' +
          escapeHTML(k.label) +
          "</div>" +
          '<div class="kpi-value" data-target="' +
          k.value +
          '">0</div>' +
          '<div class="kpi-sub">' +
          escapeHTML(k.sub) +
          "</div>" +
          "</div>"
      )
      .join("");

    // Animate numbers
    grid.querySelectorAll(".kpi-value").forEach((el) => {
      animateValue(el, parseInt(el.dataset.target, 10));
    });
  }

  function renderEntityTypeChart() {
    const types = networkData.summary.entity_types;
    const labels = Object.keys(types);
    const values = Object.values(types);
    const colors = labels.map((l) => TYPE_COLORS[l] || "#888");

    if (chartInstances.entityTypes) chartInstances.entityTypes.destroy();

    const ctx = document.getElementById("chart-entity-types").getContext("2d");
    chartInstances.entityTypes = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: labels,
        datasets: [
          {
            data: values,
            backgroundColor: colors,
            borderColor: "transparent",
            borderWidth: 0,
            hoverBorderColor: "#fff",
            hoverBorderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "65%",
        plugins: {
          legend: {
            position: "right",
            labels: {
              color: getComputedStyle(document.documentElement)
                .getPropertyValue("--text-secondary")
                .trim(),
              font: { family: "Inter", size: 11 },
              padding: 12,
              usePointStyle: true,
              pointStyleWidth: 10,
            },
          },
          tooltip: {
            backgroundColor: "#0f1117",
            titleColor: "#e8eaf0",
            bodyColor: "#a0a5b8",
            borderColor: "#2a2f40",
            borderWidth: 1,
            cornerRadius: 6,
            bodyFont: { family: "JetBrains Mono", size: 11 },
          },
        },
      },
    });
  }

  function renderNetworkGrowthChart() {
    const stats = networkData.slice_stats;
    const years = Object.keys(stats).sort();
    const edgeCounts = years.map((y) => stats[y].edges);

    if (chartInstances.networkGrowth) chartInstances.networkGrowth.destroy();

    const ctx = document
      .getElementById("chart-network-growth")
      .getContext("2d");
    chartInstances.networkGrowth = new Chart(ctx, {
      type: "line",
      data: {
        labels: years,
        datasets: [
          {
            label: "Edges",
            data: edgeCounts,
            borderColor: "#4f98a3",
            backgroundColor: "rgba(79, 152, 163, 0.1)",
            fill: true,
            tension: 0.3,
            pointRadius: 5,
            pointHoverRadius: 8,
            pointBackgroundColor: "#4f98a3",
            pointBorderColor: "#161922",
            pointBorderWidth: 2,
            borderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            grid: { color: "rgba(42, 47, 64, 0.5)" },
            ticks: {
              color: getComputedStyle(document.documentElement)
                .getPropertyValue("--text-muted")
                .trim(),
              font: { family: "JetBrains Mono", size: 10 },
            },
          },
          y: {
            beginAtZero: true,
            grid: { color: "rgba(42, 47, 64, 0.5)" },
            ticks: {
              color: getComputedStyle(document.documentElement)
                .getPropertyValue("--text-muted")
                .trim(),
              font: { family: "JetBrains Mono", size: 10 },
            },
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "#0f1117",
            titleColor: "#e8eaf0",
            bodyColor: "#a0a5b8",
            borderColor: "#2a2f40",
            borderWidth: 1,
            cornerRadius: 6,
            bodyFont: { family: "JetBrains Mono", size: 11 },
          },
        },
      },
    });
  }

  function renderTopDriftersTable() {
    const driftScores = networkData.drift_scores;
    const entityMap = {};
    networkData.entities.forEach((e) => {
      entityMap[e.entity_id] = e;
    });

    // Group by entity, find max composite_score
    const entityMaxDrift = {};
    driftScores.forEach((ds) => {
      const key = ds.entity_id;
      if (
        !entityMaxDrift[key] ||
        ds.composite_score > entityMaxDrift[key].composite_score
      ) {
        entityMaxDrift[key] = ds;
      }
    });

    // Build per-entity drift array for sparklines
    const transitions = [
      "2020->2021",
      "2021->2022",
      "2022->2023",
      "2023->2024",
    ];
    const entityDriftSeries = {};
    driftScores.forEach((ds) => {
      if (!entityDriftSeries[ds.entity_id]) {
        entityDriftSeries[ds.entity_id] = {};
      }
      const key = ds.slice_id_prev + "->" + ds.slice_id_curr;
      entityDriftSeries[ds.entity_id][key] = ds.composite_score;
    });

    const sorted = Object.entries(entityMaxDrift)
      .sort((a, b) => b[1].composite_score - a[1].composite_score)
      .slice(0, 10);

    const tbody = document
      .getElementById("table-top-drifters")
      .querySelector("tbody");
    tbody.innerHTML = sorted
      .map((entry, idx) => {
        const entityId = entry[0];
        const ds = entry[1];
        const ent = entityMap[entityId] || {
          entity_label: entityId,
          entity_type: "ORG",
        };
        const transition = ds.slice_id_prev + "→" + ds.slice_id_curr;

        // Build sparkline data
        const series = entityDriftSeries[entityId] || {};
        const sparkData = transitions.map((t) => series[t] || 0);
        const sparkSVG = buildSparkline(sparkData);

        return (
          "<tr>" +
          '<td class="mono">' +
          (idx + 1) +
          "</td>" +
          "<td>" +
          escapeHTML(ent.entity_label) +
          ' <span class="text-2xs text-muted mono">' +
          escapeHTML(entityId) +
          "</span>" +
          (ds.analyst_note
            ? '<div class="guidance-inline-note">' + escapeHTML(ds.analyst_note) + "</div>"
            : "") +
          "</td>" +
          "<td>" +
          badgeHTML(ent.entity_type, ent.entity_type) +
          "</td>" +
          '<td class="mono">' +
          ds.composite_score.toFixed(4) +
          "</td>" +
          '<td class="mono text-2xs">' +
          escapeHTML(transition) +
          "</td>" +
          '<td><span class="sparkline-container">' +
          sparkSVG +
          "</span></td>" +
          "</tr>"
        );
      })
      .join("");
  }

  function buildSparkline(data) {
    const w = 80;
    const h = 24;
    const padding = 2;
    const max = Math.max(...data, 0.01);
    const points = data.map((v, i) => {
      const x = padding + (i / (data.length - 1)) * (w - padding * 2);
      const y = h - padding - (v / max) * (h - padding * 2);
      return x + "," + y;
    });

    return (
      '<svg viewBox="0 0 ' +
      w +
      " " +
      h +
      '" preserveAspectRatio="none">' +
      '<polyline points="' +
      points.join(" ") +
      '" fill="none" stroke="#4f98a3" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>' +
      '<circle cx="' +
      points[points.length - 1].split(",")[0] +
      '" cy="' +
      points[points.length - 1].split(",")[1] +
      '" r="2" fill="#4f98a3"/>' +
      "</svg>"
    );
  }

  // ============================================================
  //  TAB 2: ENTITY RESOLUTION
  // ============================================================
  function renderEntityResolution() {
    renderMentionsTable();
    renderAliasStatusChart();
  }

  function renderMentionsTable() {
    const mentions = entityData.mentions;
    const tbody = document
      .getElementById("table-mentions")
      .querySelector("tbody");
    tbody.innerHTML = mentions
      .map(
        (m) =>
          '<tr data-mention-id="' +
          m.mention_id +
          '" style="cursor:pointer">' +
          "<td>" +
          escapeHTML(m.surface_form) +
          "</td>" +
          "<td>" +
          badgeHTML(m.entity_type, m.entity_type) +
          "</td>" +
          '<td class="mono text-2xs">' +
          escapeHTML(m.doc_id) +
          "</td>" +
          '<td class="mono">' +
          m.page +
          "</td>" +
          '<td class="text-2xs text-muted">' +
          escapeHTML(m.context_left) +
          " <strong>" +
          escapeHTML(m.surface_form) +
          "</strong> " +
          escapeHTML(m.context_right) +
          "</td>" +
          "</tr>"
      )
      .join("");

    // Click handler
    tbody.querySelectorAll("tr").forEach((row) => {
      row.addEventListener("click", () => {
        tbody
          .querySelectorAll("tr")
          .forEach((r) => r.classList.remove("selected"));
        row.classList.add("selected");
        showAliasesForMention(row.dataset.mentionId);
      });
    });
  }

  function showAliasesForMention(mentionId) {
    const panel = document.getElementById("alias-panel");
    const candidates = entityData.candidate_pairs.filter(
      (cp) =>
        cp.mention_id_a === mentionId || cp.mention_id_b === mentionId
    );

    if (candidates.length === 0) {
      panel.innerHTML =
        '<div class="panel-empty">' +
        '<svg width="32" height="32" viewBox="0 0 32 32" fill="none"><circle cx="16" cy="16" r="12" stroke="currentColor" stroke-width="1.5" opacity="0.3"/></svg>' +
        "<span>No alias candidates for this mention</span>" +
        "</div>";
      return;
    }

    panel.innerHTML = candidates
      .map((cp) => {
        const status = candidateStatuses[cp.candidate_id] || cp.status;
        return (
          '<div class="candidate-card">' +
          '<div class="candidate-header">' +
          '<span class="mono text-2xs text-muted">' +
          escapeHTML(cp.candidate_id) +
          "</span>" +
          badgeHTML(status, status) +
          "</div>" +
          '<div class="candidate-surfaces">' +
          "<span>" +
          escapeHTML(cp.surface_a) +
          "</span>" +
          '<span class="candidate-arrow">↔</span>' +
          "<span>" +
          escapeHTML(cp.surface_b) +
          "</span>" +
          "</div>" +
          '<div class="candidate-score">Score: ' +
          cp.score.toFixed(2) +
          "</div>" +
          (cp.analyst_note
            ? '<div class="guidance-inline-note">' +
              escapeHTML(cp.analyst_note) +
              "</div>"
            : "") +
          '<ul class="candidate-reasons">' +
          cp.reasons.map((r) => "<li>" + escapeHTML(r) + "</li>").join("") +
          "</ul>" +
          "</div>"
        );
      })
      .join("");
  }

  function renderAliasStatusChart() {
    const counts = { approved: 0, pending: 0, rejected: 0 };
    entityData.candidate_pairs.forEach((cp) => {
      const st = candidateStatuses[cp.candidate_id] || cp.status;
      if (counts[st] !== undefined) counts[st]++;
    });

    if (chartInstances.aliasStatus) chartInstances.aliasStatus.destroy();

    const ctx = document
      .getElementById("chart-alias-status")
      .getContext("2d");
    chartInstances.aliasStatus = new Chart(ctx, {
      type: "bar",
      data: {
        labels: ["Approved", "Pending", "Rejected"],
        datasets: [
          {
            data: [counts.approved, counts.pending, counts.rejected],
            backgroundColor: [
              STATUS_COLORS.approved,
              STATUS_COLORS.pending,
              STATUS_COLORS.rejected,
            ],
            borderRadius: 4,
            barThickness: 40,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: "y",
        scales: {
          x: {
            beginAtZero: true,
            grid: { color: "rgba(42, 47, 64, 0.5)" },
            ticks: {
              stepSize: 1,
              color: getComputedStyle(document.documentElement)
                .getPropertyValue("--text-muted")
                .trim(),
              font: { family: "JetBrains Mono", size: 10 },
            },
          },
          y: {
            grid: { display: false },
            ticks: {
              color: getComputedStyle(document.documentElement)
                .getPropertyValue("--text-secondary")
                .trim(),
              font: { family: "Inter", size: 11 },
            },
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "#0f1117",
            titleColor: "#e8eaf0",
            bodyColor: "#a0a5b8",
            borderColor: "#2a2f40",
            borderWidth: 1,
            cornerRadius: 6,
          },
        },
      },
    });
  }

  // ============================================================
  //  TAB 3: NETWORK DRIFT
  // ============================================================
  function renderNetworkDrift() {
    const year = document.getElementById("graph-year-select").value;
    renderForceGraph(year);
    renderUMAP();
    renderHeatmap();

    // Year change
    document.getElementById("graph-year-select").onchange = function () {
      renderForceGraph(this.value);
    };
  }

  function renderForceGraph(year) {
    const container = document.getElementById("network-graph");
    container.innerHTML = "";

    const width = container.clientWidth;
    const height = container.clientHeight || 500;

    // Filter edges for this year
    const yearEdges = networkData.edges.filter(
      (e) => e.report_date.startsWith(year)
    );

    // Get unique entity IDs in this year's edges
    const entityIds = new Set();
    yearEdges.forEach((e) => {
      entityIds.add(e.source_entity_id);
      entityIds.add(e.target_entity_id);
    });

    const entityMap = {};
    networkData.entities.forEach((e) => {
      entityMap[e.entity_id] = e;
    });

    // Build drift score map for this year
    const driftMap = {};
    networkData.drift_scores.forEach((ds) => {
      if (ds.slice_id_curr === year) {
        driftMap[ds.entity_id] = ds.composite_score;
      }
    });

    // Compute degree
    const degree = {};
    yearEdges.forEach((e) => {
      degree[e.source_entity_id] =
        (degree[e.source_entity_id] || 0) + 1;
      degree[e.target_entity_id] =
        (degree[e.target_entity_id] || 0) + 1;
    });

    const nodes = [...entityIds].map((id) => {
      const ent = entityMap[id] || {
        entity_id: id,
        entity_label: id,
        entity_type: "ORG",
      };
      return {
        id: id,
        label: ent.entity_label,
        type: ent.entity_type,
        degree: degree[id] || 1,
        drift: driftMap[id] || 0,
      };
    });

    const links = yearEdges.map((e) => ({
      source: e.source_entity_id,
      target: e.target_entity_id,
      type: e.relation_type,
    }));

    // Update stats
    document.getElementById("graph-stats").textContent =
      nodes.length + " nodes · " + links.length + " edges";

    const isDark =
      document.documentElement.getAttribute("data-theme") !== "light";

    const svg = d3
      .select(container)
      .append("svg")
      .attr("width", width)
      .attr("height", height)
      .attr("viewBox", [0, 0, width, height]);

    // Defs for glow filter
    const defs = svg.append("defs");
    const filter = defs
      .append("filter")
      .attr("id", "glow")
      .attr("x", "-50%")
      .attr("y", "-50%")
      .attr("width", "200%")
      .attr("height", "200%");
    filter
      .append("feGaussianBlur")
      .attr("stdDeviation", "4")
      .attr("result", "coloredBlur");
    const feMerge = filter.append("feMerge");
    feMerge.append("feMergeNode").attr("in", "coloredBlur");
    feMerge.append("feMergeNode").attr("in", "SourceGraphic");

    // Zoom
    const g = svg.append("g");
    svg.call(
      d3
        .zoom()
        .scaleExtent([0.3, 4])
        .on("zoom", (event) => {
          g.attr("transform", event.transform);
        })
    );

    // Simulation
    if (d3Simulation) d3Simulation.stop();
    d3Simulation = d3
      .forceSimulation(nodes)
      .force(
        "link",
        d3
          .forceLink(links)
          .id((d) => d.id)
          .distance(80)
      )
      .force("charge", d3.forceManyBody().strength(-200))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide().radius(20));

    // Links
    const link = g
      .selectAll("line.link")
      .data(links)
      .join("line")
      .attr("class", "link")
      .attr("stroke", isDark ? "#2a2f40" : "#d0d4de")
      .attr("stroke-width", 1)
      .attr("stroke-opacity", 0.6);

    // Nodes
    const maxDegree = Math.max(...nodes.map((n) => n.degree), 1);
    const node = g
      .selectAll("circle.node")
      .data(nodes)
      .join("circle")
      .attr("class", (d) => "node" + (d.drift > 0.15 ? " node-glow" : ""))
      .attr("r", (d) => 5 + (d.degree / maxDegree) * 12)
      .attr("fill", (d) => TYPE_COLORS[d.type] || "#888")
      .attr("stroke", isDark ? "#161922" : "#ffffff")
      .attr("stroke-width", 1.5)
      .attr("filter", (d) => (d.drift > 0.15 ? "url(#glow)" : null))
      .style("cursor", "pointer")
      .call(drag(d3Simulation));

    // Labels
    const label = g
      .selectAll("text.label")
      .data(nodes.filter((d) => d.degree >= 2))
      .join("text")
      .attr("class", "label")
      .text((d) => d.label.length > 18 ? d.label.slice(0, 16) + "…" : d.label)
      .attr("font-size", 9)
      .attr("font-family", "Inter, sans-serif")
      .attr("fill", isDark ? "#a0a5b8" : "#4a4f63")
      .attr("text-anchor", "middle")
      .attr("dy", (d) => -8 - (d.degree / maxDegree) * 12)
      .style("pointer-events", "none");

    // Tooltip
    const tooltip = document.getElementById("graph-tooltip");
    node
      .on("mouseenter", (event, d) => {
        tooltip.innerHTML =
          '<div class="fw-semibold">' +
          escapeHTML(d.label) +
          "</div>" +
          '<div class="text-2xs text-muted">' +
          escapeHTML(d.id) +
          " · " +
          escapeHTML(d.type) +
          "</div>" +
          '<div class="text-2xs mono" style="color:var(--accent-teal)">Drift: ' +
          d.drift.toFixed(4) +
          "</div>";
        tooltip.classList.add("visible");
      })
      .on("mousemove", (event) => {
        const rect = container.getBoundingClientRect();
        tooltip.style.left = event.clientX - rect.left + 12 + "px";
        tooltip.style.top = event.clientY - rect.top - 10 + "px";
      })
      .on("mouseleave", () => {
        tooltip.classList.remove("visible");
      });

    // Tick
    d3Simulation.on("tick", () => {
      link
        .attr("x1", (d) => d.source.x)
        .attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x)
        .attr("y2", (d) => d.target.y);
      node.attr("cx", (d) => d.x).attr("cy", (d) => d.y);
      label.attr("x", (d) => d.x).attr("y", (d) => d.y);
    });
  }

  function drag(simulation) {
    return d3
      .drag()
      .on("start", (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on("drag", (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on("end", (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      });
  }

  function renderUMAP() {
    const vizPoints = networkData.viz_points;
    const slices = Object.keys(vizPoints).sort();
    const isDark =
      document.documentElement.getAttribute("data-theme") !== "light";

    const traces = [];

    // Draw connecting lines for same entity across slices
    const entityTrails = {};
    slices.forEach((slice) => {
      vizPoints[slice].forEach((pt) => {
        if (!entityTrails[pt.entity_id]) {
          entityTrails[pt.entity_id] = { x: [], y: [], text: [] };
        }
        entityTrails[pt.entity_id].x.push(pt.x);
        entityTrails[pt.entity_id].y.push(pt.y);
        entityTrails[pt.entity_id].text.push(
          pt.entity_id + " (" + slice + ")"
        );
      });
    });

    // Trail lines (lighter)
    Object.entries(entityTrails).forEach(function (entry) {
      var trail = entry[1];
      traces.push({
        x: trail.x,
        y: trail.y,
        mode: "lines",
        line: { color: isDark ? "rgba(255,255,255,0.07)" : "rgba(0,0,0,0.07)", width: 1 },
        hoverinfo: "skip",
        showlegend: false,
      });
    });

    // Scatter points per slice
    slices.forEach((slice) => {
      const pts = vizPoints[slice];
      traces.push({
        x: pts.map((p) => p.x),
        y: pts.map((p) => p.y),
        text: pts.map(
          (p) =>
            p.entity_id +
            "<br>" +
            (p.label || p.entity_id) +
            "<br>Slice: " +
            slice +
            "<br>Drift: " +
            p.composite_score.toFixed(4)
        ),
        mode: "markers",
        marker: {
          size: pts.map((p) => 6 + p.composite_score * 20),
          color: SLICE_COLORS[slice] || "#888",
          opacity: 0.8,
          line: { width: 1, color: isDark ? "#161922" : "#ffffff" },
        },
        name: slice,
        hoverinfo: "text",
        type: "scatter",
      });
    });

    const layout = {
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: {
        family: "Inter, sans-serif",
        color: isDark ? "#a0a5b8" : "#4a4f63",
        size: 10,
      },
      xaxis: {
        showgrid: true,
        gridcolor: isDark ? "rgba(42,47,64,0.4)" : "rgba(200,200,210,0.4)",
        zeroline: false,
        title: { text: "UMAP-1", font: { size: 10 } },
      },
      yaxis: {
        showgrid: true,
        gridcolor: isDark ? "rgba(42,47,64,0.4)" : "rgba(200,200,210,0.4)",
        zeroline: false,
        title: { text: "UMAP-2", font: { size: 10 } },
      },
      legend: {
        orientation: "h",
        y: -0.15,
        font: { size: 10 },
      },
      margin: { l: 50, r: 20, t: 10, b: 60 },
      hovermode: "closest",
    };

    Plotly.newPlot("umap-scatter", traces, layout, {
      responsive: true,
      displayModeBar: true,
      modeBarButtonsToRemove: ["lasso2d", "select2d"],
    });
  }

  function renderHeatmap() {
    const transitions = [
      { key: "2020->2021", label: "2020→2021" },
      { key: "2021->2022", label: "2021→2022" },
      { key: "2022->2023", label: "2022→2023" },
      { key: "2023->2024", label: "2023→2024" },
    ];

    const entityMap = {};
    networkData.entities.forEach((e) => {
      entityMap[e.entity_id] = e;
    });

    // Build per-entity drift by transition
    const entityDrift = {};
    networkData.drift_scores.forEach((ds) => {
      if (!entityDrift[ds.entity_id]) entityDrift[ds.entity_id] = {};
      const key = ds.slice_id_prev + "->" + ds.slice_id_curr;
      entityDrift[ds.entity_id][key] = ds.composite_score;
    });

    // Sort by max composite score across all transitions
    const ranked = Object.entries(entityDrift)
      .map(function (entry) {
        var id = entry[0];
        var scores = entry[1];
        return {
          id: id,
          scores: scores,
          max: Math.max(...Object.values(scores)),
        };
      })
      .sort((a, b) => b.max - a.max)
      .slice(0, 15);

    const tbody = document
      .getElementById("table-heatmap")
      .querySelector("tbody");
    tbody.innerHTML = ranked
      .map((ent) => {
        const entity = entityMap[ent.id] || {
          entity_label: ent.id,
          entity_type: "ORG",
        };
        const cells = transitions
          .map((t) => {
            const score = ent.scores[t.key] || 0;
            const intensity = Math.min(score / 0.6, 1);
            const r = Math.round(30 + intensity * 191);
            const g = Math.round(30 + intensity * 75);
            const b = Math.round(40 + intensity * 76);
            const textColor = intensity > 0.3 ? "#fff" : "var(--text-muted)";
            return (
              "<td>" +
              '<span class="heatmap-cell" style="background:rgba(' +
              r +
              "," +
              g +
              "," +
              b +
              "," +
              (0.3 + intensity * 0.7) +
              ");color:" +
              textColor +
              '" title="' +
              escapeHTML(entity.entity_label) +
              " " +
              t.label +
              ": " +
              score.toFixed(4) +
              '">' +
              score.toFixed(3) +
              "</span></td>"
            );
          })
          .join("");

        return (
          "<tr>" +
          '<td class="entity-label">' +
          escapeHTML(entity.entity_label) +
          ' <span class="text-2xs text-muted">' +
          badgeHTML(entity.entity_type, entity.entity_type) +
          "</span></td>" +
          cells +
          "</tr>"
        );
      })
      .join("");
  }

  // ============================================================
  //  TAB 4: REVIEW QUEUE
  // ============================================================
  function renderReviewQueue() {
    renderPendingCards();
    renderDecisionsTable();
  }

  function renderPendingCards() {
    const pending = entityData.candidate_pairs.filter(
      (cp) => (candidateStatuses[cp.candidate_id] || cp.status) === "pending"
    );

    const mentionMap = {};
    entityData.mentions.forEach((m) => {
      mentionMap[m.mention_id] = m;
    });

    const grid = document.getElementById("review-grid");
    grid.innerHTML = pending
      .map((cp) => {
        const mA = mentionMap[cp.mention_id_a] || {};
        const mB = mentionMap[cp.mention_id_b] || {};

        return (
          '<div class="review-card" data-candidate-id="' +
          cp.candidate_id +
          '">' +
          '<div class="review-card-header">' +
          '<span class="review-card-id">' +
          escapeHTML(cp.candidate_id) +
          "</span>" +
          badgeHTML(
            candidateStatuses[cp.candidate_id] || cp.status,
            candidateStatuses[cp.candidate_id] || cp.status
          ) +
          "</div>" +
          '<div class="review-pair">' +
          '<div class="review-entity">' +
          '<div class="review-entity-name">' +
          escapeHTML(cp.surface_a) +
          "</div>" +
          '<div class="review-entity-context">"…' +
          escapeHTML(mA.context_left || "") +
          " " +
          escapeHTML(mA.surface_form || "") +
          " " +
          escapeHTML(mA.context_right || "") +
          '…"</div>' +
          '<div class="text-2xs mono mt-3">' +
          escapeHTML(mA.doc_id || "") +
          " p." +
          (mA.page || "") +
          "</div>" +
          "</div>" +
          '<div class="review-vs">VS</div>' +
          '<div class="review-entity">' +
          '<div class="review-entity-name">' +
          escapeHTML(cp.surface_b) +
          "</div>" +
          '<div class="review-entity-context">"…' +
          escapeHTML(mB.context_left || "") +
          " " +
          escapeHTML(mB.surface_form || "") +
          " " +
          escapeHTML(mB.context_right || "") +
          '…"</div>' +
          '<div class="text-2xs mono mt-3">' +
          escapeHTML(mB.doc_id || "") +
          " p." +
          (mB.page || "") +
          "</div>" +
          "</div>" +
          "</div>" +
          "<div>" +
          '<div class="review-score-bar"><div class="review-score-fill" style="width:' +
          cp.score * 100 +
          '%"></div></div>' +
          '<div class="review-score-label"><span>Match Score</span><span class="mono">' +
          cp.score.toFixed(2) +
          "</span></div>" +
          "</div>" +
          '<ul class="review-reasons">' +
          cp.reasons.map((r) => "<li>" + escapeHTML(r) + "</li>").join("") +
          "</ul>" +
          (cp.analyst_note
            ? '<div class="guidance-inline-note">' +
              escapeHTML(cp.analyst_note) +
              "</div>"
            : "") +
          '<div class="review-actions">' +
          '<button class="btn btn-approve" data-action="approved" data-cid="' +
          cp.candidate_id +
          '">Approve</button>' +
          '<button class="btn btn-reject" data-action="rejected" data-cid="' +
          cp.candidate_id +
          '">Reject</button>' +
          '<button class="btn btn-skip" data-action="pending" data-cid="' +
          cp.candidate_id +
          '">Skip</button>' +
          "</div>" +
          "</div>"
        );
      })
      .join("");

    if (pending.length === 0) {
      grid.innerHTML =
        '<div class="panel-empty" style="grid-column:1/-1;padding:3rem">' +
        '<svg width="48" height="48" viewBox="0 0 48 48" fill="none"><circle cx="24" cy="24" r="18" stroke="var(--status-approved)" stroke-width="2"/><path d="M16 24l5 5 11-11" stroke="var(--status-approved)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
        '<span class="text-sm" style="color:var(--status-approved)">All items reviewed</span>' +
        "</div>";
    }

    // Action buttons
    grid.querySelectorAll(".btn[data-action]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const cid = btn.dataset.cid;
        const action = btn.dataset.action;
        candidateStatuses[cid] = action;
        renderReviewQueue();
        // Also re-render entity resolution if it was loaded
      });
    });
  }

  function renderDecisionsTable() {
    const decisions = entityData.review_decisions;
    const tbody = document
      .getElementById("table-decisions")
      .querySelector("tbody");
    tbody.innerHTML = decisions
      .map(
        (d) =>
          "<tr>" +
          '<td class="mono">' +
          escapeHTML(d.decision_id) +
          "</td>" +
          '<td class="mono">' +
          escapeHTML(d.candidate_id) +
          "</td>" +
          "<td>" +
          escapeHTML(d.reviewer) +
          "</td>" +
          "<td>" +
          badgeHTML(d.decision, d.decision) +
          "</td>" +
          '<td class="text-2xs">' +
          escapeHTML(d.notes) +
          "</td>" +
          '<td class="mono text-2xs">' +
          formatDate(d.created_at) +
          "</td>" +
          "</tr>"
      )
      .join("");
  }

  function formatDate(dateStr) {
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (e) {
      return dateStr;
    }
  }

  // ============================================================
  //  TAB 5: PROVENANCE
  // ============================================================
  function renderProvenance() {
    renderManifestTable();
    renderTimeline();
    setupDocDetail();
  }

  function renderManifestTable() {
    const manifest = entityData.manifest;
    const tbody = document
      .getElementById("table-manifest")
      .querySelector("tbody");
    tbody.innerHTML = manifest
      .map(
        (doc) =>
          '<tr data-doc-id="' +
          doc.doc_id +
          '" style="cursor:pointer">' +
          '<td class="mono">' +
          escapeHTML(doc.doc_id) +
          "</td>" +
          "<td>" +
          escapeHTML(doc.title) +
          "</td>" +
          "<td>" +
          badgeHTML(doc.report_type, doc.report_type) +
          "</td>" +
          '<td class="mono text-2xs">' +
          escapeHTML(doc.report_date) +
          "</td>" +
          "<td>" +
          (doc.source_url
            ? '<a href="' +
              escapeHTML(doc.source_url) +
              '" target="_blank" rel="noopener noreferrer" class="mono text-2xs">View PDF ↗</a>'
            : '<span class="text-muted text-2xs">—</span>') +
          "</td>" +
          "</tr>"
      )
      .join("");

    // Click handler
    tbody.querySelectorAll("tr").forEach((row) => {
      row.addEventListener("click", () => {
        showDocMentions(row.dataset.docId);
      });
    });
  }

  function renderTimeline() {
    const manifest = entityData.manifest;
    const sorted = [...manifest].sort(
      (a, b) => new Date(a.report_date) - new Date(b.report_date)
    );

    const container = document.getElementById("timeline-items");
    container.innerHTML = sorted
      .map(
        (doc) =>
          '<div class="timeline-item" data-doc-id="' +
          doc.doc_id +
          '">' +
          '<div class="timeline-dot"></div>' +
          '<div class="timeline-label">' +
          escapeHTML(
            doc.title.length > 40
              ? doc.title.slice(0, 38) + "…"
              : doc.title
          ) +
          "</div>" +
          '<div class="timeline-date">' +
          escapeHTML(doc.report_date) +
          "</div>" +
          "</div>"
      )
      .join("");

    container.querySelectorAll(".timeline-item").forEach((item) => {
      item.addEventListener("click", () => {
        container
          .querySelectorAll(".timeline-item")
          .forEach((i) => i.classList.remove("active"));
        item.classList.add("active");
        showDocMentions(item.dataset.docId);
      });
    });
  }

  function setupDocDetail() {
    document
      .getElementById("doc-detail-close")
      .addEventListener("click", () => {
        document.getElementById("doc-detail").classList.remove("visible");
      });
  }

  function showDocMentions(docId) {
    const doc = entityData.manifest.find((d) => d.doc_id === docId);
    const mentions = entityData.mentions.filter((m) => m.doc_id === docId);

    const detail = document.getElementById("doc-detail");
    detail.classList.add("visible");

    document.getElementById("doc-detail-title").textContent = doc
      ? doc.title
      : docId;
    document.getElementById("doc-detail-meta").textContent = doc
      ? doc.report_type.toUpperCase() + " · " + doc.report_date
      : "";

    const tbody = document
      .getElementById("table-doc-mentions")
      .querySelector("tbody");

    if (mentions.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="4" class="text-muted" style="text-align:center;padding:2rem">No mentions extracted from this document</td></tr>';
    } else {
      tbody.innerHTML = mentions
        .map(
          (m) =>
            "<tr>" +
            "<td>" +
            escapeHTML(m.surface_form) +
            "</td>" +
            "<td>" +
            badgeHTML(m.entity_type, m.entity_type) +
            "</td>" +
            '<td class="mono">' +
            m.page +
            "</td>" +
            '<td class="text-2xs text-muted">' +
            escapeHTML(m.context_left) +
            " <strong>" +
            escapeHTML(m.surface_form) +
            "</strong> " +
            escapeHTML(m.context_right) +
            "</td>" +
            "</tr>"
        )
        .join("");
    }
  }

  // ---- Boot ----
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
