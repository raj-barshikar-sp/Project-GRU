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

const ROLE_KEY = "gru-role";
const VALID_ROLES = new Set(["bob", "james", "stuart", "henry"]);
const ROLE_TITLES = {
  bob: "Bob the Back Office Minion",
  james: "James the Marketing Assistant",
  stuart: "Stuart the Sales Manager Assistant",
  henry: "Henry the DSR Minion",
};
const ROLE_AVATARS = {
  bob: "/static/assets/bob.png?v=2",
  james: "/static/assets/james.png",
  stuart: "/static/assets/stuart.png?v=3",
  henry: "/static/assets/henry.png",
};

function readRole() {
  try {
    const fromUrl = new URLSearchParams(location.search).get("role");
    if (VALID_ROLES.has(fromUrl)) return fromUrl;
    const saved = localStorage.getItem(ROLE_KEY);
    if (VALID_ROLES.has(saved)) return saved;
  } catch {
    /* private mode */
  }
  return "bob";
}

let activeRole = readRole();
let sizeLabels = { ...SIZE_LABELS };
let copy = {};
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
  params.set("role", activeRole);
  return `/api/dashboard?${params.toString()}`;
}

function chatHref(extra = {}) {
  const params = new URLSearchParams({ role: activeRole, ...extra });
  return `/chat?${params.toString()}`;
}

function applyAssistant() {
  const title = ROLE_TITLES[activeRole] || ROLE_TITLES.bob;
  const avatar = ROLE_AVATARS[activeRole] || ROLE_AVATARS.bob;
  const titleEl = document.getElementById("assistant-title");
  if (titleEl) titleEl.textContent = title;
  const avatarEl = document.getElementById("assistant-avatar");
  if (avatarEl) avatarEl.src = avatar;
  document.title = `${title.split(" ")[0]} — dashboard`;
  const pngIcon = document.querySelector('link[rel="icon"][type="image/png"]');
  if (pngIcon) pngIcon.href = avatar;
  const roleSelect = document.getElementById("role-select");
  if (roleSelect) roleSelect.value = activeRole;
  document.documentElement.dataset.role = activeRole;
  const chat = document.getElementById("nav-chat");
  const dash = document.getElementById("nav-dashboard");
  const library = document.getElementById("nav-library");
  if (chat) chat.href = chatHref();
  if (dash) dash.href = `/dashboard?role=${activeRole}`;
  if (library) library.href = chatHref({ view: "library" });
  try {
    localStorage.setItem(ROLE_KEY, activeRole);
  } catch {
    /* private mode */
  }
  const url = new URL(location.href);
  if (url.searchParams.get("role") !== activeRole) {
    url.searchParams.set("role", activeRole);
    history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  }
}

function applyCopy(payload) {
  copy = payload.copy || {};
  sizeLabels = {};
  for (const item of payload.filters?.sizes || []) sizeLabels[item.id] = item.label;
  const set = (id, value) => {
    const node = document.getElementById(id);
    if (node && value) node.textContent = value;
  };
  set("dash-kicker", copy.kicker);
  set("dash-title", copy.title);
  set("chart-stage-title", copy.stage_chart);
  set("chart-size-title", copy.size_chart);
  set("table-title", copy.table);
  set("filter-size-label", copy.filter_size);
  set("filter-stage-label", copy.filter_stage);
  set("filter-time-label", copy.filter_time);
  set("filter-geo-label", copy.filter_geo);
  set("col-id", copy.col_id);
  set("col-name", copy.col_name);
  set("col-stage", copy.col_stage);
  set("col-size", copy.col_size);
  set("col-amount", copy.col_amount);
  set("col-close", copy.col_close);
  set("col-health", copy.col_health);
  const timeField = document.getElementById("filter-time-field");
  if (timeField) timeField.hidden = !(payload.filters?.windows || []).length;
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
  const geosSelect = document.getElementById("filter-geos");
  const geos = payload.filters?.geos?.length ? payload.filters.geos : window.__geos || [];
  if (!filtersReady) {
    fillSelect(sizes, payload.filters.sizes, "All sizes", state.sizes);
    fillSelect(stages, payload.filters.stages, "All stages", state.stages);
    fillSelect(windows, payload.filters.windows, "All windows", state.windows);
    fillSelect(geosSelect, geos, copy.filter_geo ? `All ${copy.filter_geo.toLowerCase()}` : "All geos", state.geos);
    bindSelect(sizes, "sizes");
    bindSelect(stages, "stages");
    bindSelect(windows, "windows");
    bindSelect(geosSelect, "geos");
    filtersReady = true;
    return;
  }
  sizes.value = state.sizes;
  stages.value = state.stages;
  windows.value = state.windows;
  geosSelect.value = state.geos;
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
  const windows = lastPayload?.filters?.windows || [];
  const hasWindow = (id) => windows.some((item) => item.id === id);
  const weekId = [copy.kpi_week_filter, "this_week", "stale"].find((id) => id && hasWindow(id)) || "";
  const cards = [
    {
      label: copy.kpi_pipeline || "Pipeline",
      value: money(kpis.pipeline),
      hint: copy.kpi_pipeline_hint || "Click to clear size & stage",
      on: Boolean(state.sizes || state.stages),
      run: () => {
        state.sizes = "";
        state.stages = "";
        refresh();
      },
    },
    {
      label: copy.kpi_open || "Open opps",
      value: String(kpis.open_opps),
      hint: copy.kpi_open_hint || "Jump to the book",
      on: false,
      run: () => document.getElementById("opp-table")?.scrollIntoView({ behavior: "smooth", block: "start" }),
    },
    {
      label: copy.kpi_week || "Close this week",
      value: String(kpis.closing_week),
      hint: copy.kpi_week_hint || "Click to filter this week",
      on: Boolean(weekId) && state.windows === weekId,
      run: () => {
        if (weekId) setFilter("windows", weekId);
      },
    },
    {
      label: copy.kpi_slack || "Work Slack",
      value: String(kpis.slack_work),
      hint: copy.kpi_slack_hint || "Open the Slack feed",
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

function stageTick(row, slot) {
  const id = String(row.id || "").trim();
  const label = String(row.label || id).trim();
  const code = (id.match(/^ss\d{2,3}$/i) || label.match(/\bss\d{2,3}\b/i) || [])[0];
  if (code) return code.toUpperCase();
  const words = label.split(/\s+/).filter(Boolean);
  let tick = label;
  if (words.length > 1) {
    tick = words[0].toLowerCase() === "paid" ? words[words.length - 1] : words[0];
  }
  const aliases = {
    syndication: "Synd.",
    tradeshow: "Show",
    webinar: "Webinar",
    nurture: "Nurture",
    field: "Field",
    search: "Search",
    social: "Social",
  };
  const alias = aliases[tick.toLowerCase().replace(/\.$/, "")];
  if (alias) return alias;
  const budget = Math.max(6, Math.floor(slot / 7));
  return tick.length <= budget ? tick : `${tick.slice(0, Math.max(4, budget - 1))}…`;
}

function renderStageChart(rows) {
  const root = document.getElementById("chart-stage");
  const list = rows || [];
  const max = Math.max(1, ...list.map((row) => row.amount || 0));
  const color = ink();
  const colors = ["#0033A1", "#0071CE", "#54C0E8", "#CC27B0", "#93D500", "#415364"];
  const n = Math.max(list.length, 1);
  const width = 420;
  const slot = width / n;
  const barW = Math.min(56, Math.max(14, slot - 12));
  root.replaceChildren();
  const svg = svgEl("svg", {
    viewBox: `0 0 ${width} 180`,
    role: "img",
    "aria-label": `${copy.stage_chart || "Amount by stage"}. Click a bar to filter.`,
  });
  list.forEach((row, index) => {
    const x = slot * index + (slot - barW) / 2;
    const barHeight = Math.round((row.amount / max) * 120);
    const y = 148 - barHeight;
    const active = state.stages === row.id;
    const dim = Boolean(state.stages) && !active;
    const bar = svgEl("rect", {
      x,
      y,
      width: barW,
      height: Math.max(barHeight, 2),
      rx: 8,
      fill: colors[index % colors.length] || "#0033A1",
      class: `dash-chart-hit${active ? " is-on" : ""}${dim ? " is-dim" : ""}`,
    });
    bar.style.cursor = "pointer";
    const tipLines = [row.label || row.id, `${row.count} ${copy.unit || "opps"}`, money(row.amount)];
    bar.addEventListener("pointerenter", (event) => showTip(event, tipLines));
    bar.addEventListener("pointermove", (event) => showTip(event, tipLines));
    bar.addEventListener("pointerleave", hideTip);
    bar.addEventListener("click", () => setFilter("stages", row.id));
    svg.append(bar);
    const tick = svgEl("text", {
      x: x + barW / 2,
      y: 168,
      "text-anchor": "middle",
      fill: color,
      "font-size": n > 5 ? 10 : 12,
      "font-family": "Poppins, sans-serif",
    });
    tick.textContent = stageTick(row, slot);
    svg.append(tick);
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
      const lines = [row.label, `${row.count} ${copy.unit || "opps"}`, money(row.amount), `${Math.round((row.amount / total) * 100)}%`];
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
  center.textContent = state.sizes ? sizeLabels[state.sizes] || state.sizes : copy.filter_size || "All sizes";
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
    cell.textContent = copy.empty || "No opportunities match these filters.";
    row.append(cell);
    body.append(row);
    return;
  }
  for (const opp of opps) {
    const row = document.createElement("tr");
    row.tabIndex = 0;
    row.title = `Open ${opp.name || opp.account} in chat`;
    const cells = [
      opp.id,
      opp.name || opp.account,
      opp.stage,
      sizeLabels[opp.size] || opp.size,
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
      location.href = chatHref({ scope: opp.name || opp.account });
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
    card.href = chatHref({ task: task.id, scope: task.scope || "" });
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
  const payload = await fetch(query()).then((res) => {
    if (!res.ok) throw new Error("Dashboard is unavailable");
    return res.json();
  });
  lastPayload = payload;
  applyCopy(payload);
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
  applyAssistant();
  bootDashSidebar();
  document.getElementById("role-select")?.addEventListener("change", (event) => {
    const next = event.target.value;
    if (!VALID_ROLES.has(next) || next === activeRole) return;
    try {
      localStorage.setItem(ROLE_KEY, next);
    } catch {
      /* private mode */
    }
    location.href = `/dashboard?role=${next}`;
  });
  const workspace = await fetch(`/api/workspace?role=${activeRole}`).then((res) => res.json());
  window.__geos = workspace.filters?.geos || [];
  if (workspace?.assistant?.title) {
    const titleEl = document.getElementById("assistant-title");
    if (titleEl) titleEl.textContent = workspace.assistant.title;
    document.title = `${workspace.assistant.name || ROLE_TITLES[activeRole]} — dashboard`;
  }
  await refresh();
  placeRailThumb("tasks");
}

boot();
