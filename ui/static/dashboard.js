const state = {
  sizes: "",
  stages: "",
  windows: "",
  geos: "",
};

const SIZE_LABELS = {
  smb: "Under $500k",
  mid: "$500k–$1.5M",
  enterprise: "$1.5M+",
};

let filtersReady = false;
let lastPayload = null;
let booted = false;

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function svgEl(tag, attrs) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs || {})) node.setAttribute(key, String(value));
  return node;
}

function healthColor(score) {
  const t = Math.max(0, Math.min(100, Number(score) || 0)) / 100;
  const hue = t < 0.5 ? 8 + (t / 0.5) * 40 : 48 + ((t - 0.5) / 0.5) * 94;
  const dark = document.documentElement.dataset.theme === "dark";
  return `hsl(${Math.round(hue)} 78% ${dark ? 58 : 40}%)`;
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
    refresh();
  });
}

function ensureFilters(payload) {
  const sizes = document.getElementById("filter-sizes");
  const stages = document.getElementById("filter-stages");
  const windows = document.getElementById("filter-windows");
  const geos = document.getElementById("filter-geos");
  if (!filtersReady) {
    fillSelect(sizes, payload.filters.sizes, "All sizes", state.sizes);
    fillSelect(stages, payload.filters.stages, "All stages", state.stages);
    fillSelect(windows, payload.filters.windows, "All windows", state.windows);
    fillSelect(geos, window.__geos || [], "All geos", state.geos);
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
  node.replaceChildren();
  for (const line of lines) node.append(el("p", "", line));
  node.hidden = false;
  const x = event.clientX;
  const y = event.clientY;
  node.style.left = `${x}px`;
  node.style.top = `${y}px`;
}

function hideTip() {
  const node = tip();
  if (node) node.hidden = true;
}

const RAIL_ORDER = ["tasks", "notes", "slack"];

function placeRailThumb(id) {
  const tabs = document.querySelector(".dash-rail-tabs");
  const thumb = document.getElementById("dash-rail-thumb");
  const tab = tabs?.querySelector(`[data-rail="${id}"]`);
  if (!tabs || !thumb || !tab) return;
  const parent = tabs.getBoundingClientRect();
  const rect = tab.getBoundingClientRect();
  thumb.style.width = `${rect.width}px`;
  thumb.style.height = `${rect.height}px`;
  thumb.style.transform = `translateX(${rect.left - parent.left}px)`;
}

function showRail(id) {
  const index = Math.max(0, RAIL_ORDER.indexOf(id));
  const rail = document.getElementById("dash-rail");
  rail?.style.setProperty("--rail-index", String(index));
  for (const tab of document.querySelectorAll(".dash-rail-tab")) {
    const on = tab.dataset.rail === id;
    tab.classList.toggle("is-on", on);
    tab.setAttribute("aria-selected", String(on));
  }
  for (const pane of document.querySelectorAll(".dash-rail-pane")) {
    const on = pane.dataset.pane === id;
    pane.classList.toggle("is-on", on);
    pane.toggleAttribute("aria-hidden", !on);
  }
  placeRailThumb(id);
}

function renderKpis(kpis) {
  const root = document.getElementById("dash-kpis");
  const cards = [
    {
      label: "Pipeline",
      value: money(kpis.pipeline),
      hint: "Click to clear size & stage",
      on: Boolean(state.sizes || state.stages),
      run: () => {
        state.sizes = "";
        state.stages = "";
        refresh();
      },
    },
    {
      label: "Open opps",
      value: String(kpis.open_opps),
      hint: "Jump to the book",
      on: false,
      run: () => document.getElementById("opp-table")?.scrollIntoView({ behavior: "smooth", block: "start" }),
    },
    {
      label: "Close this week",
      value: String(kpis.closing_week),
      hint: "Click to filter this week",
      on: state.windows === "this_week",
      run: () => setFilter("windows", "this_week"),
    },
    {
      label: "Work Slack",
      value: String(kpis.slack_work),
      hint: "Open the Slack feed",
      on: false,
      run: () => showRail("slack"),
    },
  ];
  root.replaceChildren();
  for (const item of cards) {
    const card = el("button", "dash-kpi");
    card.type = "button";
    if (item.on) card.classList.add("is-on");
    card.append(el("p", "dash-kpi-label", item.label));
    card.append(el("p", "dash-kpi-value", item.value));
    card.append(el("p", "dash-muted", item.hint));
    card.addEventListener("click", item.run);
    root.append(card);
  }
}

function renderStageChart(rows) {
  const root = document.getElementById("chart-stage");
  const max = Math.max(1, ...rows.map((row) => row.amount));
  const color = ink();
  const colors = ["#0033A1", "#0071CE", "#54C0E8", "#CC27B0"];
  root.replaceChildren();
  const svg = svgEl("svg", {
    viewBox: "0 0 420 180",
    role: "img",
    "aria-label": "Pipeline amount by SS stage. Click a bar to filter.",
  });
  rows.forEach((row, index) => {
    const x = 28 + index * 100;
    const height = Math.round((row.amount / max) * 120);
    const y = 148 - height;
    const active = state.stages === row.id;
    const dim = Boolean(state.stages) && !active;
    const bar = svgEl("rect", {
      x,
      y,
      width: 56,
      height: Math.max(height, 2),
      rx: 8,
      fill: colors[index] || "#0033A1",
      class: `dash-chart-hit${active ? " is-on" : ""}${dim ? " is-dim" : ""}`,
    });
    bar.style.cursor = "pointer";
    bar.addEventListener("pointerenter", (event) => {
      showTip(event, [`${row.id}`, `${row.count} opps`, money(row.amount)]);
    });
    bar.addEventListener("pointermove", (event) => showTip(event, [`${row.id}`, `${row.count} opps`, money(row.amount)]));
    bar.addEventListener("pointerleave", hideTip);
    bar.addEventListener("click", () => setFilter("stages", row.id));
    svg.append(bar);
    const label = svgEl("text", {
      x: x + 28,
      y: 168,
      "text-anchor": "middle",
      fill: color,
      "font-size": 12,
      "font-family": "Poppins, sans-serif",
    });
    label.textContent = `${row.id} · ${row.count}`;
    svg.append(label);
  });
  root.append(svg);
}

function polar(cx, cy, r, angle) {
  return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
}

function donutSlice(cx, cy, r0, r1, start, end) {
  const large = end - start > Math.PI ? 1 : 0;
  const [x1, y1] = polar(cx, cy, r1, start);
  const [x2, y2] = polar(cx, cy, r1, end);
  const [x3, y3] = polar(cx, cy, r0, end);
  const [x4, y4] = polar(cx, cy, r0, start);
  return `M ${x1} ${y1} A ${r1} ${r1} 0 ${large} 1 ${x2} ${y2} L ${x3} ${y3} A ${r0} ${r0} 0 ${large} 0 ${x4} ${y4} Z`;
}

function renderSizeChart(rows) {
  const root = document.getElementById("chart-size");
  const total = rows.reduce((sum, row) => sum + row.amount, 0) || 1;
  const colors = ["#54C0E8", "#0071CE", "#0033A1"];
  const wrap = el("div", "dash-donut");
  const svg = svgEl("svg", {
    viewBox: "0 0 180 180",
    role: "img",
    "aria-label": "Quoted amount by opportunity size. Click a slice to filter.",
  });
  let angle = -Math.PI / 2;
  rows.forEach((row, index) => {
    const slice = (row.amount / total) * Math.PI * 2;
    const next = angle + Math.max(slice, 0.0001);
    const active = state.sizes === row.id;
    const dim = Boolean(state.sizes) && !active;
    if (row.amount > 0) {
      const path = svgEl("path", {
        d: donutSlice(90, 90, 44, 72, angle, next),
        fill: colors[index] || "#0033A1",
        class: `dash-chart-hit${active ? " is-on" : ""}${dim ? " is-dim" : ""}`,
      });
      path.style.cursor = "pointer";
      const lines = [row.label, `${row.count} opps`, money(row.amount), `${Math.round((row.amount / total) * 100)}%`];
      path.addEventListener("pointerenter", (event) => showTip(event, lines));
      path.addEventListener("pointermove", (event) => showTip(event, lines));
      path.addEventListener("pointerleave", hideTip);
      path.addEventListener("click", () => setFilter("sizes", row.id));
      svg.append(path);
    }
    angle = next;
  });
  const hole = svgEl("circle", { cx: 90, cy: 90, r: 36, fill: surface() });
  svg.append(hole);
  const center = svgEl("text", {
    x: 90,
    y: 86,
    "text-anchor": "middle",
    fill: ink(),
    "font-size": 11,
    "font-family": "Poppins, sans-serif",
  });
  center.textContent = state.sizes ? SIZE_LABELS[state.sizes] || state.sizes : "All sizes";
  const centerAmt = svgEl("text", {
    x: 90,
    y: 106,
    "text-anchor": "middle",
    fill: ink(),
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
    swatch.style.background = colors[index] || "#0033A1";
    item.append(swatch);
    item.append(el("span", "", `${row.label} · ${row.count}`));
    item.addEventListener("click", () => setFilter("sizes", row.id));
    legend.append(item);
  });
  wrap.append(svg, legend);
  root.replaceChildren(wrap);
}

function renderOpps(opps) {
  const body = document.querySelector("#opp-table tbody");
  const count = document.getElementById("opp-count");
  count.textContent = `${opps.length} in view`;
  body.replaceChildren();
  if (!opps.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 7;
    cell.textContent = "No opportunities match these filters.";
    row.append(cell);
    body.append(row);
    return;
  }
  for (const opp of opps) {
    const row = document.createElement("tr");
    row.tabIndex = 0;
    row.title = `Open ${opp.account} in chat`;
    const cells = [
      opp.id,
      opp.account,
      opp.stage,
      SIZE_LABELS[opp.size] || opp.size,
      money(opp.amount),
      opp.close_date,
    ];
    cells.forEach((value, index) => {
      const td = el("td", index === 4 ? "num" : "", value);
      row.append(td);
    });
    const health = el("td");
    const badge = el("span", "dash-health", String(opp.health));
    const tone = healthColor(opp.health);
    badge.style.setProperty("--health", tone);
    badge.style.color = tone;
    health.append(badge);
    row.append(health);
    if (opp.backup) row.classList.add("is-backup");
    const open = () => {
      location.href = `/chat?scope=${encodeURIComponent(opp.account)}`;
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
}

function taskWhen(task) {
  const stamp = Date.parse(task?.due_at || "");
  if (!Number.isNaN(stamp)) return stamp;
  const label = String(task?.due || "").toLowerCase();
  if (label.startsWith("today")) return 0;
  if (label.startsWith("tomorrow")) return 1;
  return 10;
}

function renderTasks(tasks) {
  const root = document.getElementById("dash-tasks");
  root.replaceChildren();
  const rows = [...(tasks || [])].sort((a, b) => taskWhen(a) - taskWhen(b));
  for (const task of rows) {
    const card = el("a", "dash-task");
    card.href = `/chat?task=${encodeURIComponent(task.id)}&scope=${encodeURIComponent(task.scope)}`;
    card.append(el("strong", "dash-task-due", task.due));
    card.append(el("span", "dash-task-label", task.label));
    card.append(el("span", "dash-muted", task.scope));
    root.append(card);
  }
}

function renderFeed(rootId, items, kind) {
  const root = document.getElementById(rootId);
  root.replaceChildren();
  const list = (items || []).slice(0, 6);
  if (!list.length) {
    root.append(el("li", "dash-empty", "Nothing in this view."));
    return;
  }
  for (const item of list) {
    const row = el("li", "dash-feed-item");
    if (kind === "slack") {
      row.append(el("p", "dash-feed-meta", `${item.channel} · ${item.when}`));
      row.append(el("p", "", item.text));
    } else {
      row.append(el("p", "dash-feed-meta", item.due));
      row.append(el("p", "", item.title));
    }
    root.append(row);
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
  if (booted) flashLive();
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
  requestAnimationFrame(() => {
    document.getElementById("dash-live")?.classList.remove("is-updating");
  });
  booted = true;
}

document.getElementById("dash-clear").addEventListener("click", () => {
  state.sizes = "";
  state.stages = "";
  state.windows = "";
  state.geos = "";
  refresh();
});

document.querySelector(".dash-rail-tabs")?.addEventListener("click", (event) => {
  const tab = event.target.closest(".dash-rail-tab");
  if (tab) showRail(tab.dataset.rail);
});
window.addEventListener("resize", () => {
  const on = document.querySelector(".dash-rail-tab.is-on");
  if (on) placeRailThumb(on.dataset.rail);
});

document.addEventListener("bob-theme", () => {
  if (!lastPayload) return;
  renderStageChart(lastPayload.by_stage);
  renderSizeChart(lastPayload.by_size);
  renderOpps(lastPayload.opps);
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
  const workspace = await fetch("/api/workspace").then((res) => res.json());
  window.__geos = workspace.filters?.geos || [];
  await refresh();
  placeRailThumb("tasks");
}

boot();
