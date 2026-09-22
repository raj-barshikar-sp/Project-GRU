const state = {
  sizes: "",
  stages: "",
  windows: "",
  geos: "",
};

const SIZE_LABELS = {
  smb: "Under $25k",
  mid: "$25k–$75k",
  enterprise: "$75k+",
};

let filtersReady = false;
let lastPayload = null;
let booted = false;
let defaultGeo = "";
let tableSort = { key: "", dir: -1 };

function motionOk() {
  return !window.JamesMotion?.reducedMotion?.();
}

function growNode(node) {
  if (!node) return;
  if (!motionOk()) {
    node.classList.add("is-in");
    return;
  }
  node.classList.remove("is-in");
  requestAnimationFrame(() => node.classList.add("is-in"));
}

function revealDash(nodes) {
  window.JamesMotion?.revealRows?.(nodes, { stagger: !booted });
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function dashScopeParams() {
  return {
    geo: state.geos || "",
    sizes: state.sizes || "",
    stages: state.stages || "",
    windows: state.windows || "",
  };
}

function chatHref(item) {
  const params = new URLSearchParams();
  const task = item.task || item.id;
  const dash = dashScopeParams();
  if (task) params.set("task", task);
  if (item.campaign) params.set("campaign", item.campaign);
  const geo = item.geo || dash.geo;
  if (geo) params.set("geo", geo);
  const type = item.type || dash.stages;
  if (type) params.set("type", type);
  if (item.account) params.set("account", item.account);
  if (item.event) params.set("event", item.event);
  if (dash.sizes) params.set("sizes", dash.sizes);
  if (dash.stages) params.set("stages", dash.stages);
  if (dash.windows) params.set("windows", dash.windows);
  const qs = params.toString();
  return qs ? `/chat?${qs}` : "/chat";
}

function stashLaunch(item) {
  const task = item.task || item.id;
  if (!task) return;
  try {
    sessionStorage.setItem(
      "james-launch",
      JSON.stringify({
        task,
        prompt: item.prompt || "",
        detail: item.detail || "",
        send: false,
      })
    );
  } catch {
    /* private mode / quota */
  }
}

function svgEl(tag, attrs) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs || {})) node.setAttribute(key, String(value));
  return node;
}

function money(amount) {
  const value = Number(amount) || 0;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${Math.round(value / 1_000)}k`;
  return `$${value.toLocaleString()}`;
}

function ink() {
  return getComputedStyle(document.documentElement).getPropertyValue("--fg").trim() || "#415364";
}

function surface() {
  return getComputedStyle(document.documentElement).getPropertyValue("--surface").trim() || "#ffffff";
}

function mutedInk() {
  return getComputedStyle(document.documentElement).getPropertyValue("--fg-muted").trim() || "#9aa7b6";
}

function query() {
  const params = new URLSearchParams();
  const map = { sizes: "sizes", stages: "stages", windows: "windows", geos: "geos" };
  for (const [key, param] of Object.entries(map)) {
    if (state[key]) params.set(param, state[key]);
  }
  const qs = params.toString();
  return qs ? `/api/dashboard?${qs}` : "/api/dashboard";
}

function setFilter(key, value) {
  state[key] = state[key] === value ? "" : value;
  syncDashUrl();
  refresh();
}

function clearDashFilters() {
  state.sizes = "";
  state.stages = "";
  state.windows = "";
  state.geos = defaultGeo || "";
  syncDashUrl();
  refresh();
}

function fillSelect(select, items, allLabel, current) {
  select.replaceChildren();
  const all = document.createElement("option");
  all.value = "";
  all.textContent = allLabel;
  select.append(all);
  for (const item of items || []) {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = item.label;
    select.append(option);
  }
  select.value = current || "";
}

function bindSelect(select, key) {
  select.addEventListener("change", () => {
    state[key] = select.value;
    syncDashUrl();
    refresh();
  });
}

function syncDashUrl() {
  const params = new URLSearchParams();
  for (const key of ["sizes", "stages", "windows", "geos"]) {
    if (state[key]) params.set(key, state[key]);
  }
  const qs = params.toString();
  const href = qs ? `/dashboard?${qs}` : "/dashboard";
  if (`${location.pathname}${location.search}` !== href) {
    history.replaceState(null, "", href);
  }
}

function chartColors() {
  const styles = getComputedStyle(document.documentElement);
  const read = (name, fallback) => styles.getPropertyValue(name).trim() || fallback;
  if (document.documentElement.dataset.theme === "dark") {
    return ["#3dd6ff", "#c8ff45", "#ff5ec8", "#ffd84d", "#7eb6ff", "#ffa8ec", "#4dffc8"];
  }
  return [
    read("--cobalt", "#0033A1"),
    read("--blue", "#0071CE"),
    read("--aqua", "#54C0E8"),
    read("--magenta", "#CC27B0"),
    read("--btn", "#0033A1"),
    read("--heading", "#0033A1"),
    read("--neon-green", "#93D500"),
  ];
}

function chartFill(colors, id, catalog) {
  const index = catalog.findIndex((item) => item.id === id);
  return colors[index] || colors[0] || "#0033A1";
}

function chartLabelFill() {
  if (document.documentElement.dataset.theme === "dark") return "#f4f7fb";
  return mutedInk();
}

function ensureFilters(payload) {
  const sizes = document.getElementById("filter-sizes");
  const stages = document.getElementById("filter-stages");
  const windows = document.getElementById("filter-windows");
  const geos = document.getElementById("filter-geos");
  if (!filtersReady) {
    fillSelect(sizes, payload.filters.sizes, "All spend", state.sizes);
    fillSelect(stages, payload.filters.stages, "All types", state.stages);
    fillSelect(windows, payload.filters.windows, "All windows", state.windows);
    fillSelect(geos, payload.filters.geos || window.__geos || [], "All geos", state.geos);
    bindSelect(sizes, "sizes");
    bindSelect(stages, "stages");
    bindSelect(windows, "windows");
    bindSelect(geos, "geos");
    filtersReady = true;
    return;
  }
  sizes.value = state.sizes;
  stages.value = state.stages;
  windows.value = state.windows;
  geos.value = state.geos;
}

function tip() {
  return document.getElementById("dash-tip");
}

function showTip(event, lines) {
  const node = tip();
  if (!node) return;
  const text = node.querySelector(".t-tt-text") || node;
  text.textContent = lines.join(" · ");
  node.hidden = false;
  node.dataset.show = "true";
  const x = event.clientX;
  const y = event.clientY;
  node.style.left = `${x}px`;
  node.style.top = `${y}px`;
}

function hideTip() {
  const node = tip();
  if (!node) return;
  node.dataset.show = "false";
  window.setTimeout(() => {
    if (node.dataset.show === "false") node.hidden = true;
  }, window.JamesMotion?.tokenMs("--tt-out-dur", 50) || 50);
}

function showRail(id) {
  const bar = document.querySelector(".dash-rail-tabs");
  let activeTab = null;
  for (const tab of document.querySelectorAll(".dash-rail-tab")) {
    const on = tab.dataset.rail === id;
    tab.classList.toggle("is-on", on);
    tab.setAttribute("aria-selected", String(on));
    if (on) activeTab = tab;
  }
  for (const pane of document.querySelectorAll(".dash-rail-pane")) {
    const on = pane.dataset.pane === id;
    pane.classList.toggle("is-on", on);
    pane.hidden = !on;
  }
  if (bar && activeTab) window.JamesMotion?.moveTabPill(bar, activeTab, true);
}

function copy() {
  return lastPayload?.copy || {};
}

function renderKpis(kpis) {
  const root = document.getElementById("dash-kpis");
  const text = copy();
  const cards = [
    {
      label: text.kpi_pipeline || "Spend",
      value: money(kpis.pipeline),
      hint: text.kpi_pipeline_hint || "Days left in the quarter",
      on: Boolean(state.sizes || state.stages),
      run: () => {
        stashLaunch({ task: "campaign_performance" });
        location.href = chatHref({
          task: "campaign_performance",
          geo: state.geos || defaultGeo,
        });
      },
    },
    {
      label: text.kpi_open || "Campaigns",
      value: String(kpis.open_opps),
      hint: text.kpi_open_hint || "Match these filters",
      on: false,
      run: () => document.getElementById("opp-table")?.scrollIntoView({ behavior: "smooth", block: "start" }),
    },
    {
      label: text.kpi_week || "Ending this week",
      value: String(kpis.closing_week),
      hint: text.kpi_week_hint || "Need a follow-up",
      on: state.windows === "this_week",
      run: () => setFilter("windows", "this_week"),
    },
    {
      label: text.kpi_slack || "Slack",
      value: String(kpis.slack_work),
      hint: text.kpi_slack_hint || "Open the feed",
      on: false,
      run: () => {
        showRail("slack");
        document.querySelector(".dash-aside")?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      },
    },
  ];
  root.replaceChildren();
  for (const item of cards) {
    const card = el("button", "dash-kpi");
    card.type = "button";
    if (item.on) card.classList.add("is-on");
    card.append(el("p", "dash-kpi-label", item.label));
    const value = el("p", "dash-kpi-value");
    const group = el("span", "t-digit-group");
    value.append(group);
    if (window.JamesMotion?.setDigits) window.JamesMotion.setDigits(group, item.value);
    else group.textContent = item.value;
    card.append(value);
    card.append(el("p", "dash-muted", item.hint));
    card.addEventListener("click", item.run);
    root.append(card);
  }
  revealDash(root.children);
}

function renderStageChart(rows) {
  const root = document.getElementById("chart-stage");
  const visible = rows.filter((row) => row.count > 0 || row.amount > 0);
  const series = visible.length ? visible : rows;
  const max = Math.max(1, ...series.map((row) => row.amount));
  const colors = chartColors();
  const axis = chartLabelFill();
  const label = document.documentElement.dataset.theme === "dark" ? "#f4f7fb" : ink();
  root.replaceChildren();
  const wrap = el("div", "dash-bars");
  const n = Math.max(series.length, 1);
  const left = 44;
  const plot = 380;
  const slot = plot / n;
  const width = Math.min(44, Math.max(24, slot - 14));
  const svg = svgEl("svg", {
    viewBox: "0 0 440 168",
    role: "img",
    "aria-label": "Campaign spend by type. Click a bar to filter.",
  });
  const maxLabel = svgEl("text", {
    x: 2,
    y: 28,
    fill: axis,
    "font-size": 11,
    "font-weight": 600,
    "font-family": "IBM Plex Mono, monospace",
  });
  maxLabel.textContent = money(max);
  const zeroLabel = svgEl("text", {
    x: 2,
    y: 150,
    fill: axis,
    "font-size": 11,
    "font-weight": 600,
    "font-family": "IBM Plex Mono, monospace",
  });
  zeroLabel.textContent = "$0";
  svg.append(maxLabel, zeroLabel);
  series.forEach((row, index) => {
    const x = left + index * slot + (slot - width) / 2;
    const height = Math.round((row.amount / max) * 110);
    const y = 148 - height;
    const active = state.stages === row.id;
    const dim = Boolean(state.stages) && !active;
    const caption = row.label || row.id;
    const bar = svgEl("rect", {
      x,
      y,
      width,
      height: Math.max(height, 2),
      rx: 8,
      fill: chartFill(colors, row.id, rows),
      stroke: document.documentElement.dataset.theme === "dark" ? "rgba(255,255,255,0.22)" : "none",
      "stroke-width": document.documentElement.dataset.theme === "dark" ? 1 : 0,
      class: `dash-chart-hit t-bar${active ? " is-on" : ""}${dim ? " is-dim" : ""}`,
    });
    bar.style.cursor = "pointer";
    const tipLines = [caption, `${row.count} campaigns`, money(row.amount)];
    bar.addEventListener("pointerenter", (event) => showTip(event, tipLines));
    bar.addEventListener("pointermove", (event) => showTip(event, tipLines));
    bar.addEventListener("pointerleave", hideTip);
    bar.addEventListener("click", () => setFilter("stages", row.id));
    const amt = svgEl("text", {
      x: x + width / 2,
      y: Math.max(14, y - 6),
      "text-anchor": "middle",
      fill: dim ? axis : label,
      "font-size": 11,
      "font-weight": 600,
      "font-family": "IBM Plex Mono, monospace",
    });
    amt.textContent = money(row.amount);
    amt.style.pointerEvents = "none";
    svg.append(bar, amt);
  });
  const legend = el("div", "dash-legend dash-legend-wrap");
  series.forEach((row, index) => {
    const item = el("button", "dash-legend-item");
    item.type = "button";
    if (state.stages === row.id) item.classList.add("is-on");
    const swatch = el("span", "dash-legend-swatch");
    swatch.style.background = chartFill(colors, row.id, rows);
    item.append(swatch);
    item.append(el("span", "", `${row.label || row.id} · ${row.count}`));
    item.addEventListener("click", () => setFilter("stages", row.id));
    legend.append(item);
  });
  wrap.append(svg, legend);
  root.append(wrap);
  requestAnimationFrame(() => {
    svg.querySelectorAll(".t-bar").forEach((bar) => growNode(bar));
  });
}

function polar(cx, cy, r, angle) {
  return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
}

function donutArc(cx, cy, r0, r1, start, end) {
  const large = end - start > Math.PI ? 1 : 0;
  const [x1, y1] = polar(cx, cy, r1, start);
  const [x2, y2] = polar(cx, cy, r1, end);
  const [x3, y3] = polar(cx, cy, r0, end);
  const [x4, y4] = polar(cx, cy, r0, start);
  return `M ${x1} ${y1} A ${r1} ${r1} 0 ${large} 1 ${x2} ${y2} L ${x3} ${y3} A ${r0} ${r0} 0 ${large} 0 ${x4} ${y4} Z`;
}

function donutSlice(cx, cy, r0, r1, start, end) {
  // A 360° SVG arc has the same start and end point, so the ring vanishes.
  // Split a full (or nearly full) band into two half-rings.
  const sweep = end - start;
  if (sweep >= Math.PI * 1.999) {
    const mid = start + Math.PI;
    return `${donutArc(cx, cy, r0, r1, start, mid)} ${donutArc(cx, cy, r0, r1, mid, start + Math.PI * 2)}`;
  }
  return donutArc(cx, cy, r0, r1, start, end);
}

function renderSizeChart(rows) {
  const root = document.getElementById("chart-size");
  const live = rows.filter((row) => Number(row.amount) > 0);
  const total = live.reduce((sum, row) => sum + Number(row.amount), 0) || 1;
  const colors = chartColors();
  const wrap = el("div", "dash-donut");
  const svg = svgEl("svg", {
    viewBox: "0 0 180 180",
    role: "img",
    "aria-label": "Campaign spend by spend band. Click a slice to filter.",
  });
  let angle = -Math.PI / 2;
  const slices = svgEl("g", { class: "dash-donut-slices" });
  live.forEach((row) => {
    const slice = (Number(row.amount) / total) * Math.PI * 2;
    const next = angle + slice;
    const active = state.sizes === row.id;
    const dim = Boolean(state.sizes) && !active;
    const path = svgEl("path", {
      d: donutSlice(90, 90, 44, 72, angle, next),
      fill: chartFill(colors, row.id, rows),
      stroke: document.documentElement.dataset.theme === "dark" ? "#1c222c" : "none",
      "stroke-width": document.documentElement.dataset.theme === "dark" ? 2 : 0,
      class: `dash-chart-hit${active ? " is-on" : ""}${dim ? " is-dim" : ""}`,
    });
    path.style.cursor = "pointer";
    const lines = [row.label, `${row.count} campaigns`, money(row.amount), `${Math.round((row.amount / total) * 100)}%`];
    path.addEventListener("pointerenter", (event) => showTip(event, lines));
    path.addEventListener("pointermove", (event) => showTip(event, lines));
    path.addEventListener("pointerleave", hideTip);
    path.addEventListener("click", () => setFilter("sizes", row.id));
    slices.append(path);
    angle = next;
  });
  svg.append(slices);
  const hole = svgEl("circle", { cx: 90, cy: 90, r: 36, fill: surface() });
  svg.append(hole);
  const labelFill = document.documentElement.dataset.theme === "dark" ? "#f4f7fb" : ink();
  const center = svgEl("text", {
    x: 90,
    y: 86,
    "text-anchor": "middle",
    fill: labelFill,
    "font-size": 11,
    "font-family": "Poppins, sans-serif",
  });
  center.textContent = state.sizes
    ? (rows.find((row) => row.id === state.sizes)?.label || SIZE_LABELS[state.sizes] || state.sizes)
    : "All spend";
  const centerAmt = svgEl("text", {
    x: 90,
    y: 106,
    "text-anchor": "middle",
    fill: labelFill,
    "font-size": 13,
    "font-weight": 600,
    "font-family": "IBM Plex Mono, monospace",
  });
  centerAmt.textContent = money(rows.reduce((sum, row) => sum + (state.sizes && row.id !== state.sizes ? 0 : row.amount), 0));
  svg.append(center, centerAmt);
  const legend = el("div", "dash-legend");
  rows.forEach((row, index) => {
    const item = el("button", "dash-legend-item");
    item.type = "button";
    if (state.sizes === row.id) item.classList.add("is-on");
    const swatch = el("span", "dash-legend-swatch");
    swatch.style.background = chartFill(colors, row.id, rows);
    item.append(swatch);
    item.append(el("span", "", `${row.label} · ${row.count}`));
    item.addEventListener("click", () => setFilter("sizes", row.id));
    legend.append(item);
  });
  wrap.append(svg, legend);
  root.replaceChildren(wrap);
}

function sortedOpps(opps) {
  if (!tableSort.key) return opps;
  const key = tableSort.key;
  const dir = tableSort.dir;
  return [...opps].sort((a, b) => {
    if (key === "close_date") {
      return dir * String(a.close_date || "").localeCompare(String(b.close_date || ""));
    }
    return dir * ((Number(a[key]) || 0) - (Number(b[key]) || 0));
  });
}

function syncSortHeaders() {
  for (const btn of document.querySelectorAll(".dash-sort")) {
    const on = btn.dataset.sort === tableSort.key;
    btn.classList.toggle("is-on", on);
    if (on) btn.dataset.dir = tableSort.dir > 0 ? "asc" : "desc";
    else btn.removeAttribute("data-dir");
  }
}

function setTableSort(key) {
  if (tableSort.key === key) tableSort.dir *= -1;
  else {
    tableSort.key = key;
    tableSort.dir = -1;
  }
  syncSortHeaders();
  if (lastPayload) renderOpps(lastPayload.opps);
}

function renderOpps(opps) {
  const body = document.querySelector("#opp-table tbody");
  const count = document.getElementById("opp-count");
  const text = copy();
  const rows = sortedOpps(opps);
  const nextCount = `${rows.length} in view`;
  if (window.JamesMotion?.swapText) window.JamesMotion.swapText(count, nextCount);
  else count.textContent = nextCount;
  body.replaceChildren();
  if (!rows.length) {
    const row = document.createElement("tr");
    row.className = "dash-empty-row";
    const cell = document.createElement("td");
    cell.colSpan = 7;
    cell.append(el("span", "", text.empty || "No campaigns match these filters."));
    const clear = el("button", "dash-clear", "Clear");
    clear.type = "button";
    clear.addEventListener("click", (event) => {
      event.stopPropagation();
      clearDashFilters();
    });
    cell.append(clear);
    row.append(cell);
    body.append(row);
    revealDash(body.querySelectorAll("tr"));
    return;
  }
  for (const opp of rows) {
    const row = document.createElement("tr");
    row.tabIndex = 0;
    row.title = `Open ${opp.name || opp.theme || opp.id} in chat`;
    const nameCell = el("td", "dash-camp");
    nameCell.append(el("span", "dash-camp-name", opp.name || opp.theme || opp.id));
    if (opp.id) nameCell.append(el("span", "dash-camp-id", opp.id));
    row.append(nameCell);
    row.append(el("td", "", opp.geo || opp.account));
    row.append(el("td", "", opp.stage));
    row.append(el("td", "num", money(opp.amount)));
    row.append(el("td", "num", String(opp.mqls ?? "—")));
    row.append(el("td", "", opp.close_date));
    const health = el("td");
    const score = Number(opp.health) || 0;
    const label = score >= 70 ? "On track" : score >= 45 ? "Watch" : "Off";
    const badge = el("span", "dash-health", `${label} ${score}`);
    badge.classList.add(score >= 70 ? "is-good" : score >= 45 ? "is-ok" : "is-thin");
    health.append(badge);
    row.append(health);
    if (opp.backup) row.classList.add("is-backup");
    const open = () => {
      stashLaunch({ task: "campaign_performance" });
      location.href = chatHref({
        task: "campaign_performance",
        campaign: opp.id,
        geo: opp.geo || opp.account,
        type: opp.stage,
      });
    };
    row.addEventListener("click", open);
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open();
      }
    });
    body.append(row);
  }
  revealDash(body.querySelectorAll("tr"));
}

function impactBadge(item) {
  if (!item.impact) return null;
  return el("span", `dash-impact is-${item.tone || "watch"}`, item.impact);
}

function lastJobRecord() {
  try {
    return JSON.parse(localStorage.getItem("gru-last-job") || "null");
  } catch {
    return null;
  }
}

function renderTasks(tasks) {
  const root = document.getElementById("dash-tasks");
  root.replaceChildren();
  const nextId = lastJobRecord()?.next || "";
  const list = [...(tasks || [])];
  if (nextId) {
    const idx = list.findIndex((item) => (item.task || item.id) === nextId);
    if (idx >= 0) {
      const item = { ...list[idx], due: "Continue" };
      list.splice(idx, 1);
      list.unshift(item);
    }
  }
  for (const task of list.slice(0, 6)) {
    const card = el("a", "dash-task");
    card.href = chatHref(task);
    if (task.due === "Continue") card.classList.add("is-continue");
    const head = el("div", "dash-task-head");
    head.append(el("span", "dash-task-due", task.due));
    const badge = impactBadge(task);
    if (badge) head.append(badge);
    card.append(head);
    card.append(el("strong", "", task.label));
    if (task.detail) card.append(el("p", "dash-detail", task.detail));
    card.append(el("span", "dash-muted", task.scope));
    card.addEventListener("click", () => stashLaunch(task));
    root.append(card);
  }
  revealDash(root.children);
}

function renderSlack(root, items) {
  const AVATAR = ["#0033A1", "#0071CE", "#54C0E8", "#CC27B0", "#2A9D8F"];
  let channel = "";
  for (const item of items) {
    if (item.channel && item.channel !== channel) {
      channel = item.channel;
      const divider = el("p", "dash-slack-channel", channel);
      root.append(divider);
    }
    const row = el("article", "dash-slack-msg");
    const avatar = el("span", "dash-slack-avatar", item.initials || "?");
    const hue = AVATAR[(item.initials || "?").charCodeAt(0) % AVATAR.length];
    avatar.style.background = hue;
    const body = el("div", "dash-slack-body");
    const head = el("div", "dash-slack-head");
    head.append(el("strong", "dash-slack-name", item.author || "Teammate"));
    head.append(el("span", "dash-slack-time", item.when || ""));
    body.append(head);
    body.append(el("p", "dash-slack-text", item.text || ""));
    row.append(avatar, body);
    root.append(row);
  }
}

function renderFeed(rootId, items, kind) {
  const root = document.getElementById(rootId);
  root.replaceChildren();
  const list = (items || []).slice(0, 6);
  if (!list.length) {
    root.append(el(kind === "slack" ? "p" : "li", "dash-empty", "Nothing in this view."));
    revealDash(root.children);
    return;
  }
  if (kind === "slack") {
    renderSlack(root, list);
    revealDash(root.children);
    return;
  }
  for (const item of list) {
    const row = el("li", "dash-feed-item");
    const badge = impactBadge(item);
    const head = el("div", "dash-task-head");
    head.append(el("p", "dash-feed-meta", item.due));
    if (badge) head.append(badge);
    row.append(head);
    row.append(el("p", "", item.title));
    if (item.detail) row.append(el("p", "dash-detail", item.detail));
    if (item.id || item.task) {
      row.classList.add("is-link");
      row.tabIndex = 0;
      const open = () => {
        stashLaunch(item);
        location.href = chatHref(item);
      };
      row.addEventListener("click", open);
      row.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          open();
        }
      });
    }
    root.append(row);
  }
  revealDash(root.children);
}

function renderRailCounts(payload) {
  for (const tab of document.querySelectorAll(".dash-rail-tab[data-label]")) {
    const label = tab.dataset.label;
    const count =
      tab.dataset.rail === "notes"
        ? payload.notifications?.length || 0
        : tab.dataset.rail === "slack"
          ? payload.slack?.length || 0
          : 0;
    tab.textContent = count ? `${label} ${count}` : label;
  }
}

function flashLive() {
  const pane = document.getElementById("dash-live");
  if (!pane) return;
  pane.classList.remove("is-updating");
  void pane.offsetWidth;
  pane.classList.add("is-updating");
}

async function refresh() {
  const skel = document.getElementById("dash-skel");
  if (booted) {
    flashLive();
    skel?.classList.remove("is-revealed");
    skel?.classList.add("is-updating");
  }
  hideTip();
  const payload = await fetch(query()).then((res) => res.json());
  lastPayload = payload;
  ensureFilters(payload);
  renderKpis(payload.kpis);
  renderStageChart(payload.by_stage);
  renderSizeChart(payload.by_size);
  renderOpps(payload.opps);
  renderTasks(payload.tasks);
  renderFeed("dash-notes", payload.notifications, "note");
  renderFeed("dash-slack", payload.slack, "slack");
  renderRailCounts(payload);
  requestAnimationFrame(() => {
    document.getElementById("dash-live")?.classList.remove("is-updating");
    skel?.classList.add("is-revealed");
    skel?.classList.remove("is-updating");
  });
  booted = true;
}

document.getElementById("dash-clear").addEventListener("click", () => {
  clearDashFilters();
});

document.querySelector(".dash-table thead")?.addEventListener("click", (event) => {
  const btn = event.target.closest(".dash-sort");
  if (btn?.dataset.sort) setTableSort(btn.dataset.sort);
});

document.querySelector(".dash-rail-tabs")?.addEventListener("click", (event) => {
  const tab = event.target.closest(".dash-rail-tab");
  if (tab) showRail(tab.dataset.rail);
});

document.addEventListener("james-theme", () => {
  if (!lastPayload) return;
  renderStageChart(lastPayload.by_stage);
  renderSizeChart(lastPayload.by_size);
});

function bootDashSidebar() {
  const shell = document.getElementById("dashboard");
  if (!shell) return;
  const sidebar = document.getElementById("sidebar");
  const toggle = document.getElementById("toggle-sidebar");
  const scrim = document.getElementById("sidebar-scrim");
  const narrow = () => window.matchMedia("(max-width: 860px)").matches;
  function setOpen(open) {
    shell.classList.toggle("sidebar-collapsed", !open);
    sidebar?.setAttribute("aria-hidden", open ? "false" : "true");
    toggle?.setAttribute("aria-expanded", String(open));
    toggle?.setAttribute("aria-label", open ? "Hide sidebar" : "Show sidebar");
    if (scrim) scrim.hidden = !(open && narrow());
  }
  setOpen(!narrow());
  toggle?.addEventListener("click", () => setOpen(shell.classList.contains("sidebar-collapsed")));
  scrim?.addEventListener("click", () => setOpen(false));
  window.matchMedia("(max-width: 860px)").addEventListener("change", (event) => setOpen(!event.matches));
}

async function boot() {
  bootDashSidebar();
  window.JamesMotion?.bindTabs(document.querySelector(".dash-rail-tabs.t-tabs"));
  const workspace = await fetch("/api/workspace").then((res) => res.json());
  window.__geos = workspace.filters?.geos || [];
  defaultGeo = workspace.assistant?.region || "";
  const params = new URLSearchParams(location.search);
  if (params.get("geos")) state.geos = params.get("geos");
  else if (defaultGeo) state.geos = defaultGeo;
  if (params.get("sizes")) state.sizes = params.get("sizes");
  if (params.get("stages")) state.stages = params.get("stages");
  if (params.get("windows")) state.windows = params.get("windows");
  syncDashUrl();
  await refresh();
}

boot();
