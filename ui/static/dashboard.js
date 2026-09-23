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

function closeCustomSelects(except) {
  for (const node of document.querySelectorAll(".gru-select.is-open")) {
    if (node === except) continue;
    node.classList.remove("is-open");
    const menu = node.querySelector(".gru-select-menu");
    const button = node.querySelector(".gru-select-btn");
    if (menu) menu.hidden = true;
    button?.setAttribute("aria-expanded", "false");
  }
}

function mountCustomSelect(select) {
  if (!select || select.dataset.custom === "1") return;
  select.dataset.custom = "1";
  select.tabIndex = -1;
  select.classList.add("gru-select-native");
  const wrap = el("div", "gru-select");
  select.parentNode.insertBefore(wrap, select);
  wrap.append(select);
  const button = el("button", "gru-select-btn");
  button.type = "button";
  button.setAttribute("aria-haspopup", "listbox");
  button.setAttribute("aria-expanded", "false");
  if (select.id) button.id = `${select.id}-btn`;
  const value = el("span", "gru-select-value");
  button.append(value);
  const menu = el("div", "gru-select-menu");
  menu.hidden = true;
  menu.setAttribute("role", "listbox");
  wrap.append(button, menu);

  function sync() {
    const chosen = select.selectedOptions[0];
    value.textContent = chosen ? chosen.textContent : "";
    menu.replaceChildren();
    for (const option of select.options) {
      const item = el("button", "gru-select-opt", option.textContent);
      item.type = "button";
      item.setAttribute("role", "option");
      item.setAttribute("aria-selected", String(option.selected));
      if (option.selected) item.classList.add("is-on");
      item.addEventListener("click", () => {
        if (select.value !== option.value) {
          select.value = option.value;
          select.dispatchEvent(new Event("change", { bubbles: true }));
        }
        sync();
        closeCustomSelects();
      });
      menu.append(item);
    }
  }

  button.addEventListener("click", () => {
    const open = menu.hidden;
    closeCustomSelects(wrap);
    menu.hidden = !open;
    wrap.classList.toggle("is-open", open);
    button.setAttribute("aria-expanded", String(open));
    if (open) menu.querySelector(".is-on")?.focus();
  });
  select.addEventListener("change", sync);
  new MutationObserver(sync).observe(select, { childList: true });
  select.closest("label")?.addEventListener("click", (event) => {
    if (event.target.closest(".gru-select-btn, .gru-select-opt")) return;
    event.preventDefault();
    button.click();
  });
  select._syncMenu = sync;
  sync();
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
    for (const select of [sizes, stages, windows, geosSelect]) mountCustomSelect(select);
    filtersReady = true;
    return;
  }
  sizes.value = state.sizes;
  stages.value = state.stages;
  windows.value = state.windows;
  geosSelect.value = state.geos;
  for (const select of [sizes, stages, windows, geosSelect]) select._syncMenu?.();
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

const VIZ_PALETTE = ["#0033A1", "#0071CE", "#54C0E8", "#CC27B0", "#93D500", "#415364"];
const VIZ_CATALOG = [
  { id: "stage", title: "Pipeline by stage", hint: "Amount by stage", x: "Stage", y: "Amount", span: 7, size: "lg" },
  { id: "size", title: "Mix by size", hint: "Share of amount", span: 5, size: "md" },
  { id: "calendar", title: "Close calendar", hint: "Amount by week", x: "Week", y: "Amount", span: 8, size: "lg" },
  { id: "scatter", title: "Health vs amount", hint: "Each dot is a deal", x: "Health", y: "Amount", span: 4, size: "md" },
  { id: "aging", title: "Days to close", hint: "Amount by timing", x: "Days to close", y: "Amount", span: 5, size: "sm" },
  { id: "geo", title: "Pipeline by geo", hint: "Amount by geo", x: "Amount", y: "Geo", span: 7, size: "md" },
  { id: "waterfall", title: "Working pipeline", hint: "Gross to working book", x: "Step", y: "Amount", span: 7, size: "md" },
  { id: "funnel", title: "Stage funnel", hint: "Amount through stages", x: "Stage", y: "Amount", span: 5, size: "sm" },
  { id: "topn", title: "Top accounts", hint: "Largest accounts", x: "Amount", y: "Account", span: 5, size: "md" },
  { id: "heat", title: "Stage × size", hint: "Amount in each cell", x: "Size", y: "Stage", span: 7, size: "md" },
  { id: "coverage", title: "Coverage vs plan", hint: "Pipeline against plan", needs: "quota", x: "Coverage", y: "Amount", span: 4, size: "sm" },
  { id: "quotes", title: "Quote errors", hint: "Errors by account", needs: "errors", x: "Errors", y: "Account", span: 4, size: "md" },
  { id: "verbal", title: "Verbal vs landing", hint: "Open book vs this week", needs: "verbal", x: "", y: "Amount", span: 4, size: "md" },
];
const DEFAULT_VIZ = {
  bob: VIZ_CATALOG.map((item) => item.id),
  james: ["stage", "size"],
  stuart: ["stage", "size"],
  henry: ["stage", "size"],
};

function vizKey() {
  return `gru-viz-${activeRole}`;
}

function readEnabledViz() {
  try {
    const raw = JSON.parse(localStorage.getItem(vizKey()) || "null");
    if (Array.isArray(raw)) return raw.filter((id) => VIZ_CATALOG.some((item) => item.id === id));
  } catch {
    /* private mode */
  }
  return [...(DEFAULT_VIZ[activeRole] || DEFAULT_VIZ.bob)];
}

let enabledViz = readEnabledViz();
let vizEditing = false;

function saveEnabledViz(ids) {
  enabledViz = ids;
  try {
    localStorage.setItem(vizKey(), JSON.stringify(ids));
  } catch {
    /* private mode */
  }
}

function vizOn(id) {
  return enabledViz.includes(id);
}

function vizAvailable(spec, payload) {
  const opps = payload?.opps || [];
  if (spec.needs === "quota") return Boolean(Number(payload?.kpis?.quota)) || activeRole === "bob";
  if (spec.needs === "errors") return opps.some((row) => (row.errors || []).length);
  if (spec.needs === "verbal") return payload?.kpis?.verbal != null || opps.some((row) => row.backup);
  if (spec.id === "geo") return opps.some((row) => row.geo);
  if (spec.id === "scatter") return opps.some((row) => Number(row.health) > 0);
  return true;
}

function asOfDay(payload) {
  const raw = payload?.as_of || new Date().toISOString().slice(0, 10);
  return new Date(`${raw}T00:00:00`);
}

function parseDay(value) {
  const raw = String(value || "").slice(0, 10);
  if (!raw) return null;
  const day = new Date(`${raw}T00:00:00`);
  return Number.isNaN(day.getTime()) ? null : day;
}

function startOfWeek(day) {
  const next = new Date(day);
  next.setDate(next.getDate() - ((next.getDay() + 6) % 7));
  next.setHours(0, 0, 0, 0);
  return next;
}

function addDays(day, count) {
  const next = new Date(day);
  next.setDate(next.getDate() + count);
  return next;
}

function dayKey(day) {
  return day.toISOString().slice(0, 10);
}

function weekSeries(opps, origin, count) {
  const start = startOfWeek(origin);
  const buckets = [];
  for (let i = 0; i < count; i += 1) {
    const from = addDays(start, i * 7);
    const to = addDays(from, 7);
    const rows = opps.filter((opp) => {
      const close = parseDay(opp.close_date);
      return close && close >= from && close < to;
    });
    buckets.push({
      id: dayKey(from),
      label: from.toLocaleDateString(undefined, { month: "short", day: "numeric" }),
      amount: rows.reduce((sum, row) => sum + (Number(row.amount) || 0), 0),
      count: rows.length,
    });
  }
  return buckets;
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

function mute() {
  return getComputedStyle(document.documentElement).getPropertyValue("--fg-muted").trim() || ink();
}

function axisText(svg, value, attrs) {
  const node = svgEl("text", {
    fill: mute(),
    "font-size": 11,
    "font-family": "Poppins, sans-serif",
    ...attrs,
  });
  node.textContent = value;
  return node;
}

function renderStageChart(rows) {
  const root = document.getElementById("chart-stage");
  if (!root) return;
  vBars(
    root,
    (rows || []).map((row) => ({
      ...row,
      tick: stageTick(row, 72),
      tip: [row.label || row.id, `${row.count} ${copy.unit || "opps"}`, money(row.amount)],
      on: state.stages === row.id,
      dim: Boolean(state.stages) && state.stages !== row.id,
    })),
    {
      aria: `${copy.stage_chart || "Amount by stage"}. Click a bar to filter.`,
      x: "Stage",
      y: "Amount",
      onClick: (row) => setFilter("stages", row.id),
    }
  );
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
  if (!root) return;
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

function bindTip(node, lines) {
  node.addEventListener("pointerenter", (event) => showTip(event, lines));
  node.addEventListener("pointermove", (event) => showTip(event, lines));
  node.addEventListener("pointerleave", hideTip);
}

function vBars(root, rows, { onClick, aria, colorFor, x = "Category", y = "Amount" }) {
  const list = rows || [];
  const max = Math.max(1, ...list.map((row) => row.amount || 0));
  const n = Math.max(list.length, 1);
  const width = 400;
  const padL = 58;
  const padR = 8;
  const padT = 26;
  const plotH = 72;
  const base = padT + plotH;
  const height = base + (x ? 36 : 16);
  const plotW = width - padL - padR;
  const slot = plotW / n;
  const barW = Math.min(n <= 3 ? 44 : 32, Math.max(12, slot * 0.58));
  const svg = svgEl("svg", { viewBox: `0 0 ${width} ${height}`, preserveAspectRatio: "xMidYMid meet", role: "img", "aria-label": aria || `${y} by ${x}` });
  svg.append(axisText(svg, y, { x: 2, y: 11, "text-anchor": "start" }));
  svg.append(axisText(svg, money(max), { x: padL - 8, y: padT - 4, "text-anchor": "end" }));
  svg.append(axisText(svg, "$0", { x: padL - 8, y: base - 2, "text-anchor": "end" }));
  svg.append(svgEl("line", { x1: padL, y1: padT, x2: padL, y2: base, stroke: mute(), "stroke-width": 1 }));
  svg.append(svgEl("line", { x1: padL, y1: base, x2: width - padR, y2: base, stroke: mute(), "stroke-width": 1 }));
  list.forEach((row, index) => {
    const cx = padL + slot * index + slot / 2;
    const barHeight = Math.max(2, Math.round(((row.amount || 0) / max) * (plotH - 2)));
    const bar = svgEl("rect", {
      x: cx - barW / 2,
      y: base - barHeight,
      width: barW,
      height: barHeight,
      rx: 4,
      fill: (colorFor && colorFor(row, index)) || VIZ_PALETTE[index % VIZ_PALETTE.length],
      class: `dash-chart-hit${row.on ? " is-on" : ""}${row.dim ? " is-dim" : ""}`,
    });
    if (onClick) {
      bar.style.cursor = "pointer";
      bar.addEventListener("click", () => onClick(row));
    }
    bindTip(bar, row.tip || [row.label, money(row.amount)]);
    svg.append(bar);
    svg.append(axisText(svg, row.tick || stageTick(row, slot), { x: cx, y: base + 13, "text-anchor": "middle" }));
  });
  if (x) svg.append(axisText(svg, x, { x: padL + plotW / 2, y: height - 4, "text-anchor": "middle" }));
  root.replaceChildren(svg);
}

function hBars(root, rows, { onClick, aria, x = "Amount" }) {
  const list = rows || [];
  const max = Math.max(1, ...list.map((row) => row.amount || 0));
  const wrap = el("div", "dash-hbar");
  wrap.setAttribute("role", "img");
  wrap.setAttribute("aria-label", aria || "Chart");
  list.forEach((row, index) => {
    const item = el(onClick ? "button" : "div", "dash-hbar-row");
    if (onClick) {
      item.type = "button";
      item.addEventListener("click", () => onClick(row));
    } else {
      item.disabled = true;
    }
    item.append(el("span", "dash-hbar-label", row.label));
    const track = el("span", "dash-hbar-track");
    const fill = el("span", "dash-hbar-fill");
    fill.style.width = `${Math.max(8, Math.round(((row.amount || 0) / max) * 100))}%`;
    fill.style.background = "#0033A1";
    track.append(fill);
    item.append(track);
    item.append(el("span", "dash-hbar-val", row.value || money(row.amount)));
    bindTip(item, row.tip || [row.label, x === "Errors" ? `${row.amount} errors` : money(row.amount)]);
    wrap.append(item);
  });
  root.replaceChildren(wrap);
}

function renderCalendar(root, payload) {
  const rows = weekSeries(payload.opps || [], asOfDay(payload), 6).map((row) => {
    const day = parseDay(row.id);
    const tick = day ? `${day.getMonth() + 1}/${day.getDate()}` : row.label;
    return {
      ...row,
      tick,
      tip: [row.label, `${row.count} ${copy.unit || "opps"}`, money(row.amount)],
    };
  });
  vBars(root, rows, { aria: "Amount by close week", x: "Week", y: "Amount" });
}

function renderScatter(root, payload) {
  const opps = payload.opps || [];
  const maxAmt = Math.max(1, ...opps.map((row) => Number(row.amount) || 0));
  const width = 320;
  const height = 132;
  const padL = 44;
  const padR = 10;
  const padT = 20;
  const padB = 30;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;
  const base = padT + plotH;
  const svg = svgEl("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": "Amount by health score" });
  svg.append(axisText(svg, "Amount", { x: 2, y: 11, "text-anchor": "start" }));
  svg.append(axisText(svg, money(maxAmt), { x: padL - 6, y: padT + 3, "text-anchor": "end" }));
  svg.append(axisText(svg, "$0", { x: padL - 6, y: base, "text-anchor": "end" }));
  svg.append(svgEl("line", { x1: padL, y1: padT, x2: padL, y2: base, stroke: mute(), "stroke-width": 1 }));
  svg.append(svgEl("line", { x1: padL, y1: base, x2: width - padR, y2: base, stroke: mute(), "stroke-width": 1 }));
  [0, 50, 100].forEach((mark) => {
    const x = padL + (mark / 100) * plotW;
    svg.append(axisText(svg, String(mark), { x, y: base + 13, "text-anchor": "middle" }));
  });
  svg.append(axisText(svg, "Health", { x: padL + plotW / 2, y: height - 3, "text-anchor": "middle" }));
  opps.forEach((opp) => {
    const health = Math.max(0, Math.min(100, Number(opp.health) || 0));
    const amount = Number(opp.amount) || 0;
    const cx = padL + (health / 100) * plotW;
    const cy = base - (amount / maxAmt) * (plotH - 6);
    const stages = payload.filters?.stages || [];
    const stageIndex = Math.max(0, stages.findIndex((item) => item.id === opp.stage));
    const dot = svgEl("circle", {
      cx,
      cy,
      r: 4.5,
      fill: VIZ_PALETTE[stageIndex % VIZ_PALETTE.length],
      class: "dash-chart-hit",
    });
    dot.style.cursor = "pointer";
    bindTip(dot, [opp.name || opp.account, opp.stage, `Health ${health}`, money(amount)]);
    dot.addEventListener("click", () => {
      location.href = chatHref({ scope: opp.name || opp.account });
    });
    svg.append(dot);
  });
  root.replaceChildren(svg);
}

function renderAging(root, payload) {
  const today = asOfDay(payload);
  const buckets = [
    { id: "overdue", label: "Overdue", amount: 0, count: 0 },
    { id: "w1", label: "0–7d", amount: 0, count: 0 },
    { id: "w4", label: "8–30d", amount: 0, count: 0 },
    { id: "q", label: "31–90d", amount: 0, count: 0 },
    { id: "later", label: "90d+", amount: 0, count: 0 },
  ];
  for (const opp of payload.opps || []) {
    const close = parseDay(opp.close_date);
    if (!close) continue;
    const days = Math.round((close - today) / 86400000);
    const bucket = days < 0 ? buckets[0] : days <= 7 ? buckets[1] : days <= 30 ? buckets[2] : days <= 90 ? buckets[3] : buckets[4];
    bucket.amount += Number(opp.amount) || 0;
    bucket.count += 1;
  }
  vBars(root, buckets.map((row) => ({ ...row, tick: row.label, tip: [row.label, `${row.count} ${copy.unit || "opps"}`, money(row.amount)] })), {
    aria: "Amount by days to close",
    x: "Days to close",
    y: "Amount",
  });
}

function renderGeo(root, payload) {
  const groups = new Map();
  for (const opp of payload.opps || []) {
    const id = opp.geo || "Unassigned";
    const row = groups.get(id) || { id, label: id, amount: 0, count: 0 };
    row.amount += Number(opp.amount) || 0;
    row.count += 1;
    groups.set(id, row);
  }
  const rows = [...groups.values()].sort((a, b) => b.amount - a.amount);
  hBars(root, rows.map((row) => ({
    ...row,
    label: row.label === "Unassigned" ? row.label : row.label.replace(/\b\w/g, (ch) => ch.toUpperCase()),
    tip: [row.label, `${row.count} ${copy.unit || "opps"}`, money(row.amount)],
  })), {
    aria: "Amount by geo",
    x: "Amount",
    onClick: (row) => setFilter("geos", row.id === "Unassigned" ? "" : row.id),
  });
}

function renderWaterfall(root, payload) {
  const opps = payload.opps || [];
  const today = asOfDay(payload);
  const gross = opps.reduce((sum, row) => sum + (Number(row.amount) || 0), 0);
  const backup = opps.filter((row) => row.backup).reduce((sum, row) => sum + (Number(row.amount) || 0), 0);
  const stale = opps
    .filter((row) => {
      const touched = parseDay(row.last_touch || row.close_date);
      return touched && (today - touched) / 86400000 >= 30;
    })
    .reduce((sum, row) => sum + (Number(row.amount) || 0), 0);
  const working = Math.max(0, gross - backup - stale);
  const rows = [
    { id: "gross", label: "Gross", amount: gross, tick: "Gross" },
    { id: "backup", label: "Backup", amount: backup, tick: "Backup" },
    { id: "stale", label: "Stale 30d+", amount: stale, tick: "Stale" },
    { id: "work", label: "Working", amount: working, tick: "Working" },
  ].map((row) => ({ ...row, tip: [row.label, money(row.amount)] }));
  vBars(root, rows, {
    aria: "Working pipeline from gross amount",
    x: "Step",
    y: "Amount",
    colorFor: (row, index) => (row.id === "work" ? "#0033A1" : row.id === "gross" ? "#0071CE" : VIZ_PALETTE[index % VIZ_PALETTE.length]),
  });
}

function renderFunnel(root, payload) {
  const rows = (payload.by_stage || []).filter((row) => row.count || row.amount);
  const max = Math.max(1, ...rows.map((row) => row.amount || 0));
  const wrap = el("div", "dash-funnel");
  rows.forEach((row, index) => {
    const step = el("button", "dash-funnel-step");
    step.type = "button";
    const width = 36 + Math.round((row.amount / max) * 64);
    step.style.width = `${width}%`;
    step.style.background = VIZ_PALETTE[index % VIZ_PALETTE.length];
    step.textContent = `${stageTick(row, 80)} · ${row.count} · ${money(row.amount)}`;
    bindTip(step, [row.label || row.id, `${row.count} ${copy.unit || "opps"}`, money(row.amount)]);
    step.addEventListener("click", () => setFilter("stages", row.id));
    wrap.append(step);
  });
  root.replaceChildren(wrap);
}

function renderTopN(root, payload) {
  const groups = new Map();
  for (const opp of payload.opps || []) {
    const id = opp.name || opp.account || opp.id;
    const row = groups.get(id) || { id, label: id, amount: 0, count: 0 };
    row.amount += Number(opp.amount) || 0;
    row.count += 1;
    groups.set(id, row);
  }
  const rows = [...groups.values()].sort((a, b) => b.amount - a.amount).slice(0, 8);
  hBars(root, rows.slice(0, 6), {
    aria: "Amount by account",
    x: "Amount",
    onClick: (row) => {
      location.href = chatHref({ scope: row.id });
    },
  });
}

function renderHeat(root, payload) {
  const stages = payload.filters?.stages || payload.by_stage || [];
  const sizes = payload.filters?.sizes || payload.by_size || [];
  const cells = new Map();
  let max = 1;
  for (const opp of payload.opps || []) {
    const key = `${opp.stage}|${opp.size}`;
    const amount = (cells.get(key) || 0) + (Number(opp.amount) || 0);
    cells.set(key, amount);
    if (amount > max) max = amount;
  }
  const grid = el("div", "dash-heat");
  grid.append(el("p", "dash-axis-note dash-axis-note-left", "Size →"));
  const head = el("div", "dash-heat-row");
  head.append(el("span", "dash-heat-lab", "Stage"));
  for (const size of sizes) {
    const label = sizeLabels[size.id] || size.label || size.id;
    const short = label.replace("Under ", "<").replace("$500k–$1.5M", "$0.5–1.5M");
    head.append(el("span", "dash-heat-lab", short));
  }
  grid.append(head);
  for (const stage of stages) {
    const row = el("div", "dash-heat-row");
    row.append(el("span", "dash-heat-lab", stageTick(stage, 80)));
    for (const size of sizes) {
      const amount = cells.get(`${stage.id}|${size.id}`) || 0;
      const cell = el("button", "dash-heat-cell");
      cell.type = "button";
      const t = amount / max;
      cell.style.background = `color-mix(in srgb, #0033A1 ${Math.round(t * 86)}%, var(--page))`;
      cell.style.color = t > 0.55 ? "#fff" : ink();
      cell.textContent = amount ? money(amount) : "—";
      bindTip(cell, [stage.label || stage.id, sizeLabels[size.id] || size.label, money(amount)]);
      cell.addEventListener("click", () => {
        state.stages = stage.id;
        state.sizes = size.id;
        refresh();
      });
      row.append(cell);
    }
    grid.append(row);
  }
  root.replaceChildren(grid);
}

function renderCoverage(root, payload) {
  const pipeline = Number(payload.kpis?.pipeline) || 0;
  const quota = Number(payload.kpis?.quota) || (activeRole === "bob" ? 4_500_000 : 0);
  const cover = quota ? pipeline / quota : 0;
  const max = Math.max(pipeline, quota * 3, 1);
  const svg = svgEl("svg", { viewBox: "0 0 320 92", role: "img", "aria-label": "Pipeline amount against plan" });
  svg.append(axisText(svg, "Amount", { x: 8, y: 14, "text-anchor": "start" }));
  svg.append(svgEl("rect", { x: 8, y: 28, width: 304, height: 16, rx: 8, fill: surface() }));
  svg.append(svgEl("rect", { x: 8, y: 28, width: Math.max(6, (pipeline / max) * 304), height: 16, rx: 8, fill: "#0033A1" }));
  const mark = 8 + (quota / max) * 304;
  svg.append(svgEl("rect", { x: mark - 1, y: 22, width: 2, height: 28, fill: "#CC27B0" }));
  svg.append(axisText(svg, "Plan", { x: Math.min(292, Math.max(24, mark)), y: 64, "text-anchor": "middle" }));
  svg.append(axisText(svg, `${cover.toFixed(1)}x · pipeline ${money(pipeline)} · plan ${money(quota)}`, { x: 8, y: 84, "text-anchor": "start" }));
  root.replaceChildren(svg);
}

function renderQuotes(root, payload) {
  const groups = new Map();
  for (const opp of payload.opps || []) {
    const errors = opp.errors || [];
    if (!errors.length) continue;
    const label = opp.account || opp.name || opp.id;
    const row = groups.get(label) || { id: label, label, amount: 0, errors: [] };
    row.amount += errors.length;
    row.errors.push(...errors);
    groups.set(label, row);
  }
  const rows = [...groups.values()]
    .sort((a, b) => b.amount - a.amount)
    .map((row) => ({
      id: row.id,
      label: row.label,
      amount: row.amount,
      value: String(row.amount),
      tip: [row.label, `${row.amount} quote errors`, ...row.errors.slice(0, 3)],
    }));
  if (!rows.length) {
    root.replaceChildren(el("p", "dash-muted", "No quote errors in this view."));
    return;
  }
  hBars(root, rows, {
    aria: "Quote errors by account",
    x: "Errors",
    onClick: (row) => {
      location.href = chatHref({ scope: row.label, task: "quote_errors" });
    },
  });
}

function renderVerbal(root, payload) {
  const verbal = Number(payload.kpis?.verbal);
  const landing = Number(payload.kpis?.landing);
  const inferredVerbal = (payload.opps || [])
    .filter((row) => !row.backup)
    .reduce((sum, row) => sum + (Number(row.amount) || 0), 0);
  const inferredLanding = (payload.opps || [])
    .filter((row) => {
      const close = parseDay(row.close_date);
      if (!close || row.backup) return false;
      const start = startOfWeek(asOfDay(payload));
      return close >= start && close < addDays(start, 7);
    })
    .reduce((sum, row) => sum + (Number(row.amount) || 0), 0);
  const rows = [
    { id: "verbal", label: "Verbal / open", amount: Number.isFinite(verbal) ? verbal : inferredVerbal, tick: "Verbal" },
    { id: "landing", label: "Landing this week", amount: Number.isFinite(landing) ? landing : inferredLanding, tick: "Landing" },
  ].map((row) => ({ ...row, tip: [row.label, money(row.amount)] }));
  vBars(root, rows, { aria: "Verbal call versus landing this week", x: "", y: "Amount" });
}

function vizTitle(spec) {
  if (spec.id === "stage") return copy.stage_chart || spec.title;
  if (spec.id === "size") return copy.size_chart || spec.title;
  if (spec.id === "geo") return `Pipeline by ${(copy.filter_geo || "geo").toLowerCase()}`;
  if (spec.id === "topn") return copy.table ? `Top ${copy.table.toLowerCase()}` : spec.title;
  return spec.title;
}

function setVizEnabled(id, on) {
  const next = VIZ_CATALOG.map((row) => row.id).filter((item) => (item === id ? on : enabledViz.includes(item)));
  saveEnabledViz(next);
}

function renderVizCard(spec, payload) {
  const card = el("article", "dash-card");
  card.dataset.span = String(spec.span || 6);
  card.dataset.size = spec.size || "md";
  card.dataset.viz = spec.id;
  if (!vizOn(spec.id)) card.classList.add("is-viz-off");
  const head = el("div", "dash-card-head");
  head.append(el("h2", "", vizTitle(spec)));
  const chart = el("div", spec.id === "size" ? "dash-chart dash-chart-size" : "dash-chart");
  chart.id = `chart-${spec.id}`;
  card.append(head, chart);
  if (vizEditing) {
    const title = vizTitle(spec);
    const toggle = el("button", "dash-viz-toggle", vizOn(spec.id) ? "−" : "+");
    toggle.type = "button";
    toggle.setAttribute("aria-label", vizOn(spec.id) ? `Hide ${title}` : `Show ${title}`);
    toggle.addEventListener("click", () => {
      const on = !vizOn(spec.id);
      setVizEnabled(spec.id, on);
      card.classList.toggle("is-viz-off", !on);
      toggle.textContent = on ? "−" : "+";
      toggle.setAttribute("aria-label", on ? `Hide ${title}` : `Show ${title}`);
    });
    card.append(toggle);
  }
  const draw = {
    stage: () => renderStageChart(payload.by_stage),
    size: () => renderSizeChart(payload.by_size),
    calendar: () => renderCalendar(chart, payload),
    scatter: () => renderScatter(chart, payload),
    aging: () => renderAging(chart, payload),
    geo: () => renderGeo(chart, payload),
    waterfall: () => renderWaterfall(chart, payload),
    funnel: () => renderFunnel(chart, payload),
    topn: () => renderTopN(chart, payload),
    heat: () => renderHeat(chart, payload),
    coverage: () => renderCoverage(chart, payload),
    quotes: () => renderQuotes(chart, payload),
    verbal: () => renderVerbal(chart, payload),
  };
  if (spec.id === "stage" || spec.id === "size") {
    // renderers look up nodes by id after the card is in the document
    card.dataset.draw = spec.id;
  } else if (draw[spec.id]) {
    card._draw = () => draw[spec.id]();
  }
  return card;
}

function renderVizGrid(payload) {
  const root = document.getElementById("dash-viz");
  if (!root) return;
  root.classList.toggle("is-editing", vizEditing);
  const specs = VIZ_CATALOG.filter(
    (spec) => spec.id !== "sparklines" && vizAvailable(spec, payload) && (vizEditing || vizOn(spec.id)),
  );
  root.replaceChildren();
  if (!specs.length) {
    root.append(el("p", "dash-viz-empty", "No charts selected. Open Edit visualizations to turn some on."));
    return;
  }
  for (const spec of specs) root.append(renderVizCard(spec, payload));
  if (document.getElementById("chart-stage")) renderStageChart(payload.by_stage);
  if (document.getElementById("chart-size")) renderSizeChart(payload.by_size);
  for (const spec of specs) {
    const chart = document.getElementById(`chart-${spec.id}`);
    if (!chart || spec.id === "stage" || spec.id === "size") continue;
    const card = chart.closest(".dash-card");
    if (card?._draw) card._draw();
  }
}

function fillVizPicker(payload) {
  const list = document.getElementById("viz-list");
  if (!list) return;
  list.replaceChildren();
  for (const spec of VIZ_CATALOG) {
    if (!vizAvailable(spec, payload || lastPayload || { opps: [], kpis: {} })) continue;
    const item = el("li");
    const label = el("label", "dash-viz-opt");
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = vizOn(spec.id);
    box.addEventListener("change", () => {
      const next = VIZ_CATALOG.map((row) => row.id).filter((id) => {
        if (id === spec.id) return box.checked;
        return enabledViz.includes(id);
      });
      saveEnabledViz(next);
      if (lastPayload) {
        renderKpis(lastPayload.kpis);
        renderVizGrid(lastPayload);
      }
    });
    label.append(box);
    const copyBlock = el("span");
    copyBlock.append(el("strong", "", vizTitle(spec)));
    copyBlock.append(el("span", "", spec.hint));
    label.append(copyBlock);
    item.append(label);
    list.append(item);
  }
}

function setVizEditing(on) {
  vizEditing = on;
  const button = document.getElementById("dash-edit-viz");
  button?.setAttribute("aria-expanded", String(on));
  if (button) button.textContent = on ? "Done" : "Edit visualizations";
  if (lastPayload) renderVizGrid(lastPayload);
}

function bootVizPicker() {
  document.getElementById("dash-edit-viz")?.addEventListener("click", () => {
    setVizEditing(!vizEditing);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && vizEditing) setVizEditing(false);
  });
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
  renderVizGrid(payload);
  renderKpis(payload.kpis);
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
  renderVizGrid(lastPayload);
  renderKpis(lastPayload.kpis);
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
  bootVizPicker();
  mountCustomSelect(document.getElementById("role-select"));
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".gru-select")) closeCustomSelects();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeCustomSelects();
  });
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
