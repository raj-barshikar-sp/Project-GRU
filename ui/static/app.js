const taskMenu = document.getElementById("task-menu");
const chatHistory = document.getElementById("chat-history");
const canvas = document.getElementById("canvas");
const chatContent = document.getElementById("chat-content");
const scrollBottomBtn = document.getElementById("scroll-bottom");
let stickToBottom = true;
let pinningReasoning = false;
const form = document.getElementById("composer");
const prompt = document.getElementById("prompt");
const send = document.getElementById("send");
const stop = document.getElementById("stop");
const newChat = document.getElementById("new-chat");
const attachInput = document.getElementById("attach");
const attachBtn = document.getElementById("attach-btn");
const attachChips = document.getElementById("attach-chips");
const filterOrg = document.getElementById("filter-org");
const filterOpps = document.getElementById("filter-opps");
const filterReports = document.getElementById("filter-reports");
const filterSizes = document.getElementById("filter-sizes");
const filterStages = document.getElementById("filter-stages");
const filterWindows = document.getElementById("filter-windows");
const workspaceEl = document.getElementById("workspace");
const toggleSidebarBtn = document.getElementById("toggle-sidebar");
const queryNav = document.getElementById("query-nav");
const composerDrop = document.getElementById("composer-drop");
const composerDropOverlay = document.getElementById("composer-drop-overlay");
const sidebarEl = document.getElementById("sidebar");
const sidebarScrim = document.getElementById("sidebar-scrim");
const dialogScrim = document.getElementById("dialog-scrim");
const tasksDialog = document.getElementById("tasks-dialog");
const taskItemsDialog = document.getElementById("task-items-dialog");
const taskItemsNav = document.getElementById("task-items");
const taskItemsTitle = document.getElementById("task-items-dialog-title");
const filtersDialog = document.getElementById("filters-dialog");
const deleteDialog = document.getElementById("delete-dialog");
const deleteDialogCopy = document.getElementById("delete-dialog-copy");
const confirmDeleteChat = document.getElementById("confirm-delete-chat");
const roleSelect = document.getElementById("role-select");
let pendingDeleteChatId = "";
let pendingRenameChatId = "";
let chatsSort = "recent";
let recentsSelected = new Set();
let chatsCollapsed = false;

const ALLOWED_ATTACH = new Set([".pdf", ".csv", ".txt", ".xlsx", ".xls", ".docx", ".doc"]);
const MAX_ATTACH = 5;
const MAX_ATTACH_BYTES = 8 * 1024 * 1024;

let sessionId = "";
let workspace = null;
let activeTask = "";
let abortController = null;
let requestGen = 0;
let chats = [];
let activeChatId = "";
let attachments = [];
let showReasoning = false;
const ROLE_KEY = "gru-role";
const VALID_ROLES = new Set(["bob", "james", "stuart", "henry"]);
let activeRole = localStorage.getItem(ROLE_KEY) || "bob";
if (!VALID_ROLES.has(activeRole)) activeRole = "bob";
const ROLE_NAMES = { bob: "Bob", james: "James", stuart: "Stuart", henry: "Henry" };
let assistantName = ROLE_NAMES[activeRole];
const CHATS_KEY = `gru-chats-${activeRole}`;
const CHATS_LIMIT = 40;
if (activeRole === "bob" && !localStorage.getItem(CHATS_KEY)) {
  const legacyChats = localStorage.getItem("gru-chats");
  if (legacyChats) localStorage.setItem(CHATS_KEY, legacyChats);
}

function apiUrl(path) {
  const url = new URL(path, location.origin);
  url.searchParams.set("role", activeRole);
  return `${url.pathname}${url.search}`;
}

function applyAssistant() {
  assistantName = workspace?.assistant?.name || assistantName;
  const title = workspace?.assistant?.title || assistantName;
  const titleEl = document.getElementById("assistant-title");
  if (titleEl) titleEl.textContent = title;
  document.title = `${assistantName} — workspace`;
  const dashboardLink = document.getElementById("nav-dashboard");
  if (dashboardLink) dashboardLink.hidden = activeRole !== "bob";
  prompt?.setAttribute("aria-label", `Ask ${assistantName}`);
  roleSelect.value = activeRole;
  document.documentElement.dataset.role = activeRole;
  window.BobArtifacts?.setRole(activeRole);
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function selectedValues(name) {
  const select = document.querySelector(`#filters-dialog select[name="${name}"]:not(:disabled)`);
  if (select) return select.value ? [select.value] : [];
  return [...document.querySelectorAll(`input[name="${name}"]:checked:not(:disabled)`)].map(
    (node) => node.value
  );
}

function currentFilters() {
  return {
    geos: selectedValues("geo"),
    boats: selectedValues("boat"),
    opps: selectedValues("opp"),
    report_types: selectedValues("report"),
    sizes: selectedValues("size"),
    stages: selectedValues("stage"),
    windows: selectedValues("time"),
  };
}

function allowedFilterNames(task) {
  const extra = ["size", "stage", "time"];
  if (!task) return new Set(["geo", "boat", "opp", "report", ...extra]);
  return new Set(
    task.filters?.length ? [...task.filters, ...extra] : ["geo", "boat", "opp", "report", ...extra]
  );
}

function allowedReportIds(task) {
  return task?.report_ids?.length ? new Set(task.report_ids) : null;
}

function syncFilterAvailability() {
  const task = activeTask ? findTask(activeTask) : null;
  const names = allowedFilterNames(task);
  const reportIds = allowedReportIds(task);
  const restrict = Boolean(task);
  for (const input of document.querySelectorAll("#filters-dialog .checks input, #filters-dialog select")) {
    let on = !restrict || names.has(input.name);
    if (on && input.name === "report" && reportIds) on = reportIds.has(input.value);
    input.disabled = !on;
  }
  for (const block of document.querySelectorAll(".filter-block")) {
    const checks = [...block.querySelectorAll(".check")];
    const inputs = checks.map((row) => row.querySelector("input")).filter(Boolean);
    const select = block.querySelector("select");
    const allOff =
      (inputs.length > 0 && inputs.every((node) => node.disabled)) ||
      Boolean(select?.disabled && !inputs.length);
    block.classList.toggle("is-collapsed", allOff);
    block.toggleAttribute("aria-disabled", allOff);
    for (const row of checks) {
      const input = row.querySelector("input");
      row.classList.toggle("is-collapsed", Boolean(restrict && input?.disabled && !allOff));
    }
  }
}

function findTask(taskId) {
  for (const group of workspace?.tasks || []) {
    const hit = group.items?.find((item) => item.id === taskId);
    if (hit) return hit;
  }
  return null;
}

function composeDraft(taskId) {
  const task = findTask(taskId);
  if (!task) return "";
  const filters = currentFilters();
  const opps = workspace?.filters?.opps || [];
  const oppMap = Object.fromEntries(opps.map((item) => [item.id, item]));
  let account = "";
  for (const id of filters.opps) {
    if (oppMap[id]) {
      account = oppMap[id].account;
      break;
    }
  }
  if (!account) {
    for (const geo of filters.geos) {
      const hit = opps.find((item) => item.territory === geo);
      if (hit) {
        account = hit.account;
        break;
      }
    }
  }
  if (!account) {
    for (const boat of filters.boats) {
      const hit = opps.find((item) => item.owner === boat);
      if (hit) {
        account = hit.account;
        break;
      }
    }
  }
  let territory = filters.geos[0] || "";
  if (!territory && account) {
    territory = opps.find((item) => item.account === account)?.territory || "";
  }
  territory = territory || (workspace?.filters?.geos || [])[0]?.id || "";
  let text = task.default_prompt || "";
  if (account && task.scoped_prompt) {
    text = task.scoped_prompt.replaceAll("{account}", account).replaceAll("{territory}", territory);
  } else if (filters.geos.length && task.scoped_prompt) {
    text = task.scoped_prompt.replaceAll("{account}", account || territory).replaceAll("{territory}", territory);
  }
  const notes = [];
  if (filters.geos.length) notes.push("Geos: " + filters.geos.join(", "));
  if (filters.boats.length) notes.push("Boats: " + filters.boats.join(", "));
  if (filters.opps.length) {
    const labels = filters.opps.map((id) => oppMap[id]?.label).filter(Boolean);
    if (labels.length) notes.push("Rep opps: " + labels.join("; "));
  }
  if (filters.report_types.length) {
    const labels = (workspace?.filters?.report_types || [])
      .filter((item) => filters.report_types.includes(item.id))
      .map((item) => item.label);
    if (labels.length) notes.push("Reporting types: " + labels.join(", "));
  }
  if (filters.sizes.length) {
    const labels = (workspace?.filters?.sizes || [])
      .filter((item) => filters.sizes.includes(item.id))
      .map((item) => item.label);
    notes.push("Opp size: " + (labels.join(", ") || filters.sizes.join(", ")));
  }
  if (filters.stages.length) notes.push("SS stage: " + filters.stages.join(", "));
  if (filters.windows.length) {
    const labels = (workspace?.filters?.windows || [])
      .filter((item) => filters.windows.includes(item.id))
      .map((item) => item.label);
    notes.push("Time: " + (labels.join(", ") || filters.windows.join(", ")));
  }
  if (notes.length) text += "\n\nWorking filters:\n" + notes.map((note) => `- ${note}`).join("\n");
  return text;
}

function syncTaskButtons() {
  for (const node of document.querySelectorAll("#task-items .task")) {
    node.classList.toggle("active", Boolean(activeTask) && node.dataset.taskId === activeTask);
  }
}

function taskGroupLabel(taskId) {
  for (const group of workspace?.tasks || []) {
    if (group.items?.some((item) => item.id === taskId)) return group.label;
  }
  return "";
}

function makeSelectionChip(label, onClear) {
  const chip = el("button", "selection-chip");
  chip.type = "button";
  chip.setAttribute("aria-label", `Remove ${label}`);
  chip.title = `Remove ${label}`;
  chip.append(el("span", "selection-chip-text", label));
  chip.append(el("span", "selection-chip-x", "×"));
  chip.addEventListener("click", (event) => {
    event.stopPropagation();
    onClear();
  });
  return chip;
}

function renderSelection() {
  const panel = document.getElementById("sidebar-selected");
  const root = document.getElementById("selected-chips");
  if (!panel || !root) return;
  root.replaceChildren();
  const task = activeTask ? findTask(activeTask) : null;
  if (task) {
    const group = taskGroupLabel(activeTask);
    const label = group ? `${group} · ${task.label}` : task.label;
    root.append(
      makeSelectionChip(label, () => {
        clearTaskSelection();
        prompt.value = "";
        resizePrompt();
        prompt.focus();
      })
    );
  }
  for (const input of document.querySelectorAll(
    '#filters-dialog .checks input:checked:not(:disabled)'
  )) {
    const row = input.closest(".check");
    const label = (row?.textContent || input.value).replace(/\s+/g, " ").trim();
    root.append(
      makeSelectionChip(label, () => {
        input.checked = false;
        input.dispatchEvent(new Event("change", { bubbles: true }));
      })
    );
  }
  for (const select of document.querySelectorAll("#filters-dialog select:not(:disabled)")) {
    if (!select.value) continue;
    const chosen = select.selectedOptions[0];
    const label = (chosen?.textContent || select.value).trim();
    root.append(
      makeSelectionChip(label, () => {
        select.value = "";
        select.dispatchEvent(new Event("change", { bubbles: true }));
      })
    );
  }
  panel.hidden = root.childElementCount === 0;
}

function clearTaskSelection() {
  activeTask = "";
  syncTaskButtons();
  syncFilterAvailability();
  renderSelection();
}

function fillComposer(taskId) {
  activeTask = taskId;
  prompt.value = composeDraft(taskId);
  resizePrompt();
  prompt.focus();
}

const CLIPBOARD_ICON =
  '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="2"></rect><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"></path></svg>';
const CHECK_ICON =
  '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5 9.5 17 19 7.5"></path></svg>';

function addCopy(parent, text, label, inline) {
  const button = el("button", inline ? "copy inline" : "copy");
  button.type = "button";
  button.dataset.copy = text;
  button.setAttribute("aria-label", label || "Copy");
  button.title = label || "Copy";
  button.innerHTML = CLIPBOARD_ICON;
  parent.append(button);
}

function setReasoningOpen(box, open) {
  if (!box) return;
  const label = box.querySelector(".reasoning-trigger-label");
  if (label && box.dataset.streaming !== "true") {
    label.textContent = open ? "Hide reasoning" : "Show reasoning";
  }
  if (box.classList.contains("is-open") === open) {
    box.dataset.open = open ? "true" : "false";
    return;
  }
  pinningReasoning = true;
  stickToBottom = false;
  box.classList.toggle("is-open", open);
  box.dataset.open = open ? "true" : "false";
  let finished = false;
  const done = () => {
    if (finished) return;
    finished = true;
    pinningReasoning = false;
    syncScrollButton();
  };
  const shell = box.querySelector(".reasoning-shell");
  if (shell) {
    shell.addEventListener(
      "transitionend",
      (event) => {
        if (event.propertyName && event.propertyName !== "max-height") return;
        done();
      },
      { once: true }
    );
  }
  window.setTimeout(done, 420);
}

canvas.addEventListener("click", async (event) => {
  const trigger = event.target.closest(".reasoning-trigger");
  if (trigger && canvas.contains(trigger)) {
    event.preventDefault();
    const box = trigger.closest(".reasoning");
    setReasoningOpen(box, !box?.classList.contains("is-open"));
    return;
  }
  const button = event.target.closest("button.copy");
  if (!button || !canvas.contains(button)) return;
  await navigator.clipboard.writeText(button.dataset.copy || "");
  button.innerHTML = CHECK_ICON;
  const prior = button.getAttribute("aria-label");
  button.setAttribute("aria-label", "Copied");
  clearTimeout(button._copyTimer);
  button._copyTimer = setTimeout(() => {
    button.innerHTML = CLIPBOARD_ICON;
    button.setAttribute("aria-label", prior || "Copy");
  }, 1200);
});

function briefingText(payload) {
  const chunks = [];
  if (payload.summary) chunks.push("Summary", payload.summary);
  if (payload.insights?.length) {
    chunks.push("", "Key insights", ...payload.insights.map((item) => `- ${item}`));
  }
  if (payload.actions?.length) {
    chunks.push("", "Recommended actions");
    payload.actions.forEach((action, index) => {
      chunks.push(`${index + 1}. ${action.action}`);
      const bits = [
        action.owner && `owner: ${action.owner}`,
        action.due && `when: ${action.due}`,
      ]
        .filter(Boolean)
        .join(" · ");
      if (bits) chunks.push(bits);
      if (action.paste) chunks.push(action.paste);
    });
  }
  if (payload.artifacts?.length) {
    chunks.push("", "Artifacts");
    for (const artifact of payload.artifacts) {
      if (artifact.title) chunks.push(artifact.title);
      if (artifact.body) chunks.push(artifact.body);
    }
  }
  return chunks.join("\n").trim();
}

function isDeckArtifact(item) {
  const kind = String(item?.kind || "").toLowerCase();
  const title = String(item?.title || "");
  return kind === "deck" || /\bdeck\b/i.test(title);
}

function persistChatArtifacts(artifacts) {
  const incoming = artifacts || [];
  const decks = incoming.filter(isDeckArtifact);
  const copy = incoming.filter((item) => !isDeckArtifact(item));
  let saved = [];
  try {
    saved = window.BobArtifacts?.upsert(copy, activeChatId) || [];
  } catch {
    saved = [];
  }
  return { saved, decks };
}

function downloadDeck(title, body) {
  const blob = new Blob([body || ""], { type: "text/markdown" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${String(title || "deck").replace(/[^\w.-]+/g, "-")}.md`;
  link.click();
  URL.revokeObjectURL(link.href);
}

function appendArtifactBar(parent, saved, decks) {
  parent.querySelector(".artifact-bar")?.remove();
  if (!saved?.length && !decks?.length) return;
  const bar = el("div", "artifact-bar");
  for (const item of saved || []) {
    const chip = el("button", "artifact-chip", item.title || "Artifact");
    chip.type = "button";
    chip.dataset.artifactOpen = item.id;
    bar.append(chip);
  }
  for (const item of decks || []) {
    const chip = el("button", "artifact-chip artifact-chip-deck", item.title || "Deck");
    chip.type = "button";
    chip.dataset.deckDownload = "1";
    chip.dataset.deckTitle = item.title || "Deck";
    chip.dataset.deckBody = item.body || "";
    bar.append(chip);
  }
  parent.append(bar);
}

function setLibrary(on, options = {}) {
  const library = document.getElementById("library");
  const stage = document.querySelector(".stage");
  if (!library || !stage) return;
  library.hidden = !on;
  stage.classList.toggle("is-library", on);
  document.getElementById("open-library")?.classList.toggle("is-active", on);
  if (on) {
    window.BobArtifacts?.render();
    const url = new URL(location.href);
    url.searchParams.set("view", "library");
    history.replaceState({}, "", url);
    window.BobArtifacts?.close();
  } else {
    const url = new URL(location.href);
    if (url.searchParams.get("view") === "library") {
      url.searchParams.delete("view");
      history.replaceState({}, "", url);
    }
    if (!options.keepPanel) window.BobArtifacts?.close();
  }
}

function applyDashboardLaunch() {
  const params = new URLSearchParams(location.search);
  const taskId = params.get("task");
  const scope = (params.get("scope") || "").trim();
  if (scope) {
    const opps = workspace?.filters?.opps || [];
    const hit = opps.find(
      (item) =>
        item.id === scope || String(item.account || "").toLowerCase() === scope.toLowerCase()
    );
    const geo = (workspace?.filters?.geos || []).find(
      (item) => item.id.toLowerCase() === scope.toLowerCase()
    );
    let input = null;
    if (hit) {
      input = document.querySelector(`#filters-dialog input[name="opp"][value="${CSS.escape(hit.id)}"]`);
    } else if (geo) {
      input = document.querySelector(`#filters-dialog input[name="geo"][value="${CSS.escape(geo.id)}"]`);
    }
    if (input) input.checked = true;
  }
  if (taskId && findTask(taskId)) {
    activeTask = taskId;
    syncTaskButtons();
    syncFilterAvailability();
    fillComposer(taskId);
  }
  renderSelection();
}

function addReplyCopy(parent, text) {
  if (!text) return;
  const tools = el("div", "reply-tools");
  addCopy(tools, text, "Copy response", true);
  parent.append(tools);
}

const ARTIFACT_KICKERS = {
  email: "Email",
  talking_points: "Talking points",
  merge_instruction: "Merge",
  ask: "Ask",
  work_order: "Work order",
  deck: "Deck",
  other: "Note",
};

function isMarkdownHr(line) {
  const compact = line.replace(/\s/g, "");
  return /^(-{3,}|\*{3,}|_{3,})$/.test(compact);
}

function looksMarkdown(text) {
  return (
    /^\s*(#{1,6}\s|[-*]\s|\d+\.\s|>\s)/m.test(text) ||
    /^\s*(-{3,}|\*{3,}|_{3,})\s*$/m.test(text) ||
    /\|.+\|/.test(text) ||
    /\*\*[^*]+\*\*/.test(text) ||
    /(^|[^\w])\*[^*]+\*/.test(text) ||
    /^```/m.test(text) ||
    /^Subject:\s/m.test(text)
  );
}

function stripEmailSignoff(text) {
  return String(text || "")
    .replace(/\r\n/g, "\n")
    .replace(
      /(\n(?:best regards|kind regards|sincerely),?)\s*\n(?:[^\n]+(?:\n|$))+$/i,
      "$1\n"
    )
    .replace(/\s+$/, "\n");
}

function looksLikeEmail(text) {
  const value = String(text || "").trim();
  return /^(subject\s*:|hi\s+\w+)/im.test(value) && /best regards/i.test(value);
}

function wrapUnfencedEmail(chunk) {
  return String(chunk || "").replace(
    /(^|\n)(Subject:\s[^\n][\s\S]*?\nBest regards,?)(?:\s*\n(?:[A-Z][^\n]*)){0,4}/gi,
    (_, prefix, body) => `${prefix}\`\`\`\n${stripEmailSignoff(body).trim()}\n\`\`\``
  );
}

function fenceEmails(text) {
  const value = String(text || "");
  let out = "";
  let last = 0;
  let open = -1;
  const marker = "```";
  let index = value.indexOf(marker);
  while (index >= 0) {
    if (open < 0) {
      out += wrapUnfencedEmail(value.slice(last, index));
      open = index;
    } else {
      out += value.slice(open, index + marker.length);
      last = index + marker.length;
      open = -1;
    }
    index = value.indexOf(marker, index + marker.length);
  }
  if (open >= 0) out += value.slice(open);
  else out += wrapUnfencedEmail(value.slice(last));
  return out;
}

function artifactBlock(body, kind, title) {
  const cleaned = looksLikeEmail(body) ? stripEmailSignoff(body).trim() : String(body || "").trim();
  if (!cleaned) return el("div");
  const resolvedKind = kind || (looksLikeEmail(cleaned) ? "email" : "other");
  const block = el("div", `artifact artifact-${resolvedKind}`);
  const pre = el("pre");
  pre.textContent = cleaned;
  block.append(pre);
  addCopy(block, cleaned, "Copy artifact");
  const save = el("button", "artifact-save", "Save");
  save.type = "button";
  save.dataset.artifactSave = "1";
  save.dataset.title = title || "Untitled";
  save.dataset.kind = resolvedKind;
  block.append(save);
  return block;
}

function splitTableRow(line) {
  let value = line.trim();
  if (value.startsWith("|")) value = value.slice(1);
  if (value.endsWith("|")) value = value.slice(0, -1);
  return value.split("|").map((cell) => cell.trim());
}

function isTableSeparator(line) {
  const cells = splitTableRow(line);
  return cells.length > 0 && cells.every((cell) => /^:?-{2,}:?$/.test(cell.replace(/\s/g, "")));
}

function isTableRow(line) {
  const trimmed = line.trim();
  return trimmed.includes("|") && !isMarkdownHr(trimmed) && !isTableSeparator(trimmed);
}

function tableAlign(cell) {
  const value = cell.replace(/\s/g, "");
  const left = value.startsWith(":");
  const right = value.endsWith(":");
  if (left && right) return "center";
  if (right) return "right";
  return "left";
}

function renderMarkdownTable(header, aligns, rows) {
  const wrap = el("div", "md-table-wrap");
  const table = el("table");
  const head = el("thead");
  const headRow = el("tr");
  header.forEach((cell, index) => {
    const th = el("th");
    if (aligns[index]) th.style.textAlign = aligns[index];
    appendRich(th, cell);
    headRow.append(th);
  });
  head.append(headRow);
  table.append(head);
  const body = el("tbody");
  for (const row of rows) {
    const tr = el("tr");
    header.forEach((_, index) => {
      const td = el("td");
      if (aligns[index]) td.style.textAlign = aligns[index];
      appendRich(td, row[index] || "");
      tr.append(td);
    });
    body.append(tr);
  }
  table.append(body);
  wrap.append(table);
  return wrap;
}

function renderMarkdown(text) {
  const root = el("div", "md-prose");
  if (!text?.trim()) return root;
  const lines = fenceEmails(text).replace(/\r\n/g, "\n").split("\n");
  const listStack = [];
  const closeLists = (indent = -1) => {
    while (listStack.length && listStack[listStack.length - 1].indent > indent) {
      listStack.pop();
    }
  };
  const openList = (indent, type) => {
    while (listStack.length) {
      const top = listStack[listStack.length - 1];
      if (top.indent > indent || (top.indent === indent && top.type !== type)) {
        listStack.pop();
        continue;
      }
      break;
    }
    const top = listStack[listStack.length - 1];
    if (top && top.indent === indent && top.type === type) return top.el;
    const list = el(type);
    if (top && indent > top.indent && top.el.lastElementChild) {
      top.el.lastElementChild.append(list);
    } else {
      root.append(list);
    }
    listStack.push({ el: list, indent, type });
    return list;
  };
  let fence = null;
  const flushFence = () => {
    if (!fence) return;
    const body = fence.join("\n").replace(/^\n+|\n+$/g, "");
    if (body.trim()) root.append(artifactBlock(body));
    fence = null;
  };
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index].replace(/\s+$/, "");
    const trimmed = line.trim();
    const next = (lines[index + 1] || "").trim();
    if (isTableRow(trimmed) && isTableSeparator(next)) {
      closeLists();
      const header = splitTableRow(trimmed);
      const aligns = splitTableRow(next).map(tableAlign);
      index += 1;
      const rows = [];
      while (index + 1 < lines.length && isTableRow((lines[index + 1] || "").trim())) {
        index += 1;
        rows.push(splitTableRow(lines[index]));
      }
      root.append(renderMarkdownTable(header, aligns, rows));
      continue;
    }
    if (trimmed.startsWith("```")) {
      closeLists();
      if (fence) flushFence();
      else fence = [];
      continue;
    }
    if (fence) {
      fence.push(line);
      continue;
    }
    if (!trimmed) {
      continue;
    }
    if (isMarkdownHr(trimmed)) {
      closeLists();
      root.append(el("hr"));
      continue;
    }
    const heading = trimmed.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      closeLists();
      const depth = heading[1].length;
      const tag = depth <= 2 ? "h2" : depth === 3 ? "h3" : "h4";
      const node = el(tag);
      appendRich(node, heading[2]);
      root.append(node);
      continue;
    }
    if (trimmed.startsWith(">")) {
      closeLists();
      const quote = el("blockquote");
      appendRich(quote, trimmed.replace(/^>\s?/, ""));
      root.append(quote);
      continue;
    }
    const listMatch = line.match(/^(\s*)([-*]|\d+\.)\s+(.*)$/);
    if (listMatch) {
      const indent = listMatch[1].length;
      const type = /^\d+\./.test(listMatch[2]) ? "ol" : "ul";
      const list = openList(indent, type);
      const item = el("li");
      appendRich(item, listMatch[3]);
      list.append(item);
      continue;
    }
    closeLists();
    const paragraph = el("p");
    appendRich(paragraph, trimmed);
    root.append(paragraph);
  }
  closeLists();
  flushFence();
  return root;
}

function appendNumericRich(parent, text) {
  const re = /(\$\d[\d,]*(?:\.\d+)?[MK]?|\d+(?:\.\d+)?x|\d+\s*days?)/gi;
  let last = 0;
  const value = text || "";
  for (const match of value.matchAll(re)) {
    if (match.index > last) parent.append(document.createTextNode(value.slice(last, match.index)));
    parent.append(el("span", "num", match[0]));
    last = match.index + match[0].length;
  }
  if (last < value.length) parent.append(document.createTextNode(value.slice(last)));
}

function appendRich(parent, text) {
  const value = text || "";
  const tokenRe = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\n]+\*)/g;
  let last = 0;
  let matched = false;
  for (const match of value.matchAll(tokenRe)) {
    matched = true;
    if (match.index > last) appendNumericRich(parent, value.slice(last, match.index));
    const token = match[0];
    if (token.startsWith("**")) {
      const strong = el("strong");
      appendNumericRich(strong, token.slice(2, -2));
      parent.append(strong);
    } else if (token.startsWith("`")) {
      const code = el("code");
      code.textContent = token.slice(1, -1);
      parent.append(code);
    } else {
      const em = el("em");
      appendNumericRich(em, token.slice(1, -1));
      parent.append(em);
    }
    last = match.index + token.length;
  }
  if (!matched) appendNumericRich(parent, value);
  else if (last < value.length) appendNumericRich(parent, value.slice(last));
}

function extractMetrics(...parts) {
  const blob = parts.filter(Boolean).join("\n");
  const metrics = [];
  const coverage = blob.match(/coverage[^.\n]{0,48}?(\d+(?:\.\d+)?)\s*x/i);
  if (coverage) metrics.push({ label: "Coverage", value: `${coverage[1]}x` });
  const verbal = blob.match(/verbal(?:\s+call)?[^$\n]{0,28}\$([\d,]+(?:\.\d+)?)/i);
  if (verbal) metrics.push({ label: "Verbal call", value: `$${verbal[1]}` });
  const landing = blob.match(/landing[^$\n]{0,28}\$([\d,]+(?:\.\d+)?)/i);
  if (landing) metrics.push({ label: "Landing", value: `$${landing[1]}` });
  const cycle = blob.match(/cycle[^.\n]{0,28}?(\d+)\s*days/i);
  if (cycle) metrics.push({ label: "Cycle", value: `${cycle[1]}d` });
  return metrics;
}

function parseLiveInsights(block) {
  return (block || "")
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.startsWith("- "))
    .map((line) => line.slice(2).trim())
    .filter(Boolean);
}

function parseLiveActions(block) {
  const actions = [];
  let current = null;
  for (const raw of (block || "").split("\n")) {
    const line = raw.trim();
    if (!line) continue;
    const match = line.match(/^(\d+)\.\s+(.*?)(?:\s+\(([^)]*)\))?\s*$/);
    if (match) {
      let owner = "";
      let due = "";
      for (const piece of (match[3] || "").split(",")) {
        const part = piece.trim();
        if (part.toLowerCase().startsWith("owner:")) owner = part.split(":").slice(1).join(":").trim();
        if (part.toLowerCase().startsWith("when:")) due = part.split(":").slice(1).join(":").trim();
      }
      current = { action: match[2].trim(), owner, due, paste: "" };
      actions.push(current);
      continue;
    }
    if (current && line.toLowerCase().startsWith("paste:")) {
      current.paste = line.slice(6).trim();
    }
  }
  return actions;
}

function parseLiveArtifacts(block) {
  if (!block || ["", "none", "none."].includes(block.trim().toLowerCase())) return [];
  const items = [];
  const re =
    /###\s+(.+?)(?:\s+·\s+(email|merge_instruction|talking_points|ask|work_order|deck|other))?\s*\n```[a-zA-Z0-9_-]*\n([\s\S]*?)```/g;
  for (const match of block.matchAll(re)) {
    items.push({
      title: match[1].trim(),
      kind: match[2] || "other",
      body: match[3].trim(),
    });
  }
  return items;
}

function extractFencedEmails(text) {
  const items = [];
  const seen = new Set();
  const re = /```[a-zA-Z0-9_-]*\n([\s\S]*?)```/g;
  for (const match of String(text || "").matchAll(re)) {
    const body = match[1].trim();
    if (!looksLikeEmail(body) || seen.has(body)) continue;
    seen.add(body);
    const subject = (body.match(/^Subject:\s*(.+)$/im) || [])[1];
    items.push({
      title: (subject || "Sendable email").trim(),
      kind: "email",
      body,
    });
  }
  if (items.length) return items;
  const loose = String(text || "").match(/^Subject:\s[^\n]+\n[\s\S]*?\nBest regards,?/im);
  if (loose && looksLikeEmail(loose[0])) {
    const body = stripEmailSignoff(loose[0]).trim();
    const subject = (body.match(/^Subject:\s*(.+)$/im) || [])[1];
    items.push({
      title: (subject || "Sendable email").trim(),
      kind: "email",
      body,
    });
  }
  return items;
}

function extractReplyArtifacts(event, fallbackText) {
  const items = [];
  const seen = new Set();
  const push = (item) => {
    const body = String(item?.body || "").trim();
    if (!body || seen.has(body)) return;
    seen.add(body);
    items.push({
      title: item.title || "Untitled",
      kind: item.kind || (looksLikeEmail(body) ? "email" : "other"),
      body,
      id: item.id,
    });
  };
  for (const item of event?.artifacts || []) push(item);
  const text = event?.text || fallbackText || "";
  for (const item of parseLiveArtifacts(text)) push(item);
  for (const item of extractFencedEmails(text)) push(item);
  return items;
}

function parsePartialBriefing(text) {
  const headings = ["## Summary", "## Key Insights", "## Recommended Actions", "## Artifacts"];
  const positions = headings.map((heading) => text.indexOf(heading));
  if (positions[0] < 0) return null;
  const sections = {};
  headings.forEach((heading, index) => {
    if (positions[index] < 0) return;
    const start = positions[index] + heading.length;
    let end = text.length;
    for (let next = index + 1; next < headings.length; next += 1) {
      if (positions[next] >= 0) {
        end = positions[next];
        break;
      }
    }
    sections[heading.slice(3)] = text.slice(start, end).trim();
  });
  return {
    kind: "briefing",
    summary: sections.Summary || "",
    insights: parseLiveInsights(sections["Key Insights"] || ""),
    actions: parseLiveActions(sections["Recommended Actions"] || ""),
    artifacts: parseLiveArtifacts(sections.Artifacts || ""),
  };
}

function renderBriefing(payload, options = {}) {
  const live = Boolean(options.live);
  const wrap = el("div", live ? "briefing live" : "briefing");
  const summary = el("article", "card card-summary");
  summary.append(el("h3", "", "Summary"));
  const metrics = extractMetrics(payload.summary, ...(payload.insights || []));
  if (metrics.length) {
    const row = el("div", "metrics");
    for (const metric of metrics) {
      const tile = el("div", "metric");
      tile.append(el("span", "metric-label", metric.label));
      tile.append(el("span", "metric-value", metric.value));
      row.append(tile);
    }
    summary.append(row);
  }
  const summaryText = el("p", "summary-text");
  if (payload.summary) appendRich(summaryText, payload.summary);
  else if (live) summaryText.append(el("span", "card-empty", "Writing the briefing…"));
  summary.append(summaryText);
  wrap.append(summary);

  if (live || payload.insights?.length) {
    const insights = el("article", "card card-insights");
    insights.append(el("h3", "", "Key insights"));
    if (payload.insights?.length) {
      const list = el("ul");
      for (const item of payload.insights) {
        const li = el("li");
        appendRich(li, item);
        list.append(li);
      }
      insights.append(list);
    } else {
      insights.append(el("p", "card-empty", "Pulling the takeaways…"));
    }
    wrap.append(insights);
  }

  if (live || payload.actions?.length) {
    const actions = el("article", "card card-actions");
    actions.append(el("h3", "", "Recommended actions"));
    if (payload.actions?.length) {
      for (const action of payload.actions) {
        const row = el("div", "action-row");
        const body = el("div", "action-body");
        const line = el("p", "action-text");
        appendRich(line, action.action);
        body.append(line);
        const genericOwner = /^(you|revops|deal desk|otc)$/i.test((action.owner || "").trim());
        const bits = [
          action.owner && !genericOwner && `owner: ${action.owner}`,
          action.due && `when: ${action.due}`,
        ]
          .filter(Boolean)
          .join(" · ");
        if (bits) body.append(el("p", "meta", bits));
        if (action.paste) {
          const paste = el("div", "paste");
          appendRich(paste, action.paste);
          addCopy(paste, action.paste, "Copy paste line");
          body.append(paste);
        }
        row.append(body);
        actions.append(row);
      }
    } else {
      actions.append(el("p", "card-empty", "Drafting next steps…"));
    }
    wrap.append(actions);
  }

  if (live || payload.artifacts?.length) {
    const artifacts = el("article", "card card-artifacts");
    artifacts.append(el("h3", "", "Paste-ready"));
    if (payload.artifacts?.length) {
      for (const artifact of payload.artifacts) {
        const kind = artifact.kind || "other";
        const block = el("div", `artifact artifact-${kind}`);
        block.append(el("p", "artifact-kicker", ARTIFACT_KICKERS[kind] || "Note"));
        block.append(el("strong", "", artifact.title));
        const pre = el("pre");
        const body =
          kind === "email" ? stripEmailSignoff(artifact.body || "").trim() : artifact.body;
        appendRich(pre, body);
        block.append(pre);
        addCopy(block, body, "Copy artifact");
        const save = el("button", "artifact-save", "Save");
        save.type = "button";
        save.dataset.artifactSave = "1";
        save.dataset.title = artifact.title || "Untitled";
        save.dataset.kind = kind;
        artifacts.append(block);
        block.append(save);
      }
    } else {
      artifacts.append(el("p", "card-empty", "Preparing copy…"));
    }
    wrap.append(artifacts);
  }
  if (!live) addReplyCopy(wrap, briefingText(payload));
  return wrap;
}

function placeholderNode() {
  const node = el("div", "placeholder");
  node.id = "placeholder";
  const img = document.createElement("img");
  img.src = "/static/assets/bob.png?v=2";
  img.alt = "";
  img.className = "placeholder-bob";
  img.addEventListener("error", () => img.remove(), { once: true });
  node.append(
    img,
    el("h2", "", `What should ${assistantName} work on?`),
    el("p", "", "Pick a task, adjust filters, edit the draft, then send.")
  );
  const picks = [];
  for (const group of workspace?.tasks || []) {
    if (group.items?.[0]) picks.push(group.items[0]);
    if (picks.length === 4) break;
  }
  if (picks.length) {
    const row = el("div", "starters");
    for (const item of picks) {
      const chip = el("button", "starter", item.label);
      chip.type = "button";
      chip.addEventListener("click", () => selectTask(item.id));
      row.append(chip);
    }
    node.append(row);
  }
  return node;
}

function setStatus(node, label) {
  let text = node.querySelector(".status-label");
  if (!node.querySelector(".status-dots")) {
    const dots = el("span", "status-dots");
    dots.append(el("i"), el("i"), el("i"));
    node.replaceChildren(dots, el("span", "status-label", label));
    return;
  }
  if (text) text.textContent = label;
}

function resizePrompt() {
  prompt.style.height = "auto";
  prompt.style.height = `${Math.min(prompt.scrollHeight, 200)}px`;
}

function threadEl() {
  return chatContent || canvas;
}

function canvasHasTurns() {
  return Boolean(threadEl().querySelector(".turn"));
}

function showEmptyCanvas() {
  threadEl().replaceChildren(placeholderNode());
  renderQueryNav();
}

function isChatNearBottom() {
  if (!canvas) return true;
  return canvas.scrollHeight - canvas.scrollTop - canvas.clientHeight <= 64;
}

function syncScrollButton() {
  if (!scrollBottomBtn) return;
  scrollBottomBtn.classList.toggle("is-visible", !isChatNearBottom());
}

function scrollChat(force) {
  if (!canvas) return;
  if (!force && !stickToBottom) {
    syncScrollButton();
    return;
  }
  canvas.scrollTop = canvas.scrollHeight;
  stickToBottom = true;
  syncScrollButton();
}

function revealLatestQuery(turn) {
  if (!canvas || !turn) return;
  stickToBottom = true;
  const query = turn.querySelector(".turn-head") || turn;
  const offset =
    query.getBoundingClientRect().top - canvas.getBoundingClientRect().top;
  canvas.scrollTop += offset - 8;
  stickToBottom = true;
  syncScrollButton();
}

function bootChatScroll() {
  if (!canvas) return;
  canvas.addEventListener(
    "scroll",
    () => {
      if (!pinningReasoning) stickToBottom = isChatNearBottom();
      syncScrollButton();
      highlightQueryNav();
    },
    { passive: true }
  );
  scrollBottomBtn?.addEventListener("click", () => {
    stickToBottom = true;
    canvas.scrollTo({ top: canvas.scrollHeight, behavior: "smooth" });
    syncScrollButton();
  });
  const target = threadEl();
  if (typeof ResizeObserver === "function" && target) {
    new ResizeObserver(() => {
      if (stickToBottom && !pinningReasoning) canvas.scrollTop = canvas.scrollHeight;
      syncScrollButton();
    }).observe(target);
  }
}

function snapshotActive() {
  const chat = chats.find((item) => item.id === activeChatId);
  if (!chat) return;
  chat.html = threadEl().innerHTML;
  persistChats();
}

function pruneChats(list) {
  const pinned = list.filter((item) => item.pinned);
  const rest = list.filter((item) => !item.pinned);
  const used = rest.filter(
    (item) => item.id === activeChatId || String(item.html || "").includes("turn")
  );
  const unused = rest.filter((item) => !used.includes(item));
  const budget = Math.max(0, CHATS_LIMIT - pinned.length);
  const keptRest = [...used, ...unused].slice(0, budget);
  const keepIds = new Set([...pinned, ...keptRest].map((item) => item.id));
  return list.filter((item) => keepIds.has(item.id));
}

function persistChats() {
  chats = pruneChats(chats);
  const payload = {
    activeChatId,
    chats: chats.map((item) => ({
      id: item.id,
      sessionId: item.sessionId || "",
      title: item.title || "Chat",
      html: item.html || "",
      pinned: Boolean(item.pinned),
      updated: item.updated || "",
    })),
  };
  try {
    localStorage.setItem(CHATS_KEY, JSON.stringify(payload));
  } catch {
    payload.chats = payload.chats.map((item, index) =>
      item.pinned || index < 8 ? item : { ...item, html: "" }
    );
    try {
      localStorage.setItem(CHATS_KEY, JSON.stringify(payload));
    } catch {
      /* quota */
    }
  }
}

function loadChats() {
  try {
    const raw = JSON.parse(localStorage.getItem(CHATS_KEY) || "");
    if (!raw || !Array.isArray(raw.chats)) return;
    chats = raw.chats.filter((item) => item && item.id);
    activeChatId = chats.some((item) => item.id === raw.activeChatId)
      ? raw.activeChatId
      : chats[0]?.id || "";
  } catch {
    chats = [];
    activeChatId = "";
  }
}

function restoreActiveChat() {
  const chat = chats.find((item) => item.id === activeChatId);
  if (chat?.sessionId) sessionId = chat.sessionId;
  if (chat?.html && chat.html.includes("turn")) {
    threadEl().innerHTML = chat.html;
    for (const turn of threadEl().querySelectorAll(".turn.pending")) {
      turn.classList.remove("pending");
      turn.querySelector(".status")?.remove();
      turn.querySelector(".caret")?.remove();
    }
    hydrateTurns();
    renderQueryNav();
    scrollChat(true);
    return true;
  }
  return false;
}

function historyTitle(text) {
  const compact = text.replace(/\s+/g, " ").trim();
  return compact.length > 42 ? `${compact.slice(0, 41)}…` : compact;
}

function timeAgo(iso) {
  const then = new Date(iso).getTime();
  if (!then) return "";
  const seconds = Math.round((Date.now() - then) / 1000);
  if (seconds < 45) return "just now";
  if (seconds < 3600) return `${Math.max(1, Math.round(seconds / 60))}m ago`;
  if (seconds < 86400) return `${Math.max(1, Math.round(seconds / 3600))}h ago`;
  if (seconds < 86400 * 7) return `${Math.max(1, Math.round(seconds / 86400))}d ago`;
  return new Date(iso).toLocaleDateString();
}

function historyMeta(chat) {
  if (chat.running) return "Running";
  return timeAgo(chat.updated) || "";
}

function sortedChats(list) {
  const rows = [...list];
  if (chatsSort === "title") {
    rows.sort((a, b) => String(a.title || "").localeCompare(String(b.title || "")));
  }
  return rows;
}

function historyAction(label, path, onClick, on) {
  const button = el("button", on ? "history-action is-on" : "history-action");
  button.type = "button";
  button.title = label;
  button.setAttribute("aria-label", label);
  button.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${path}</svg>`;
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    onClick();
  });
  return button;
}

function historyRow(chat) {
  const row = el("div", "history-row");
  const button = el("button", "history-item");
  button.type = "button";
  button.title = chat.title;
  if (chat.id === activeChatId) {
    button.classList.add("active");
    button.setAttribute("aria-current", "true");
  }
  button.append(el("span", "history-title", chat.title));
  const meta = historyMeta(chat);
  if (meta) button.append(el("span", "history-meta", meta));
  button.addEventListener("click", () => openChat(chat.id));
  const actions = el("div", "history-actions");
  actions.append(
    historyAction(
      chat.pinned ? "Unpin" : "Pin",
      '<path d="M12 17v5M8 3h8l-1 7h3l-6 6-6-6h3Z" />',
      () => togglePin(chat.id),
      chat.pinned
    ),
    historyAction(
      "Rename",
      '<path d="M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />',
      () => askRenameChat(chat.id, chat.title)
    ),
    historyAction("Delete", '<path d="M5 7h14M10 11v6M14 11v6M9 7l1-3h4l1 3M7 7l1 14h8l1-14" />', () =>
      askDeleteChat(chat.id, chat.title)
    )
  );
  row.append(button, actions);
  return row;
}

function renderHistory() {
  const pinnedRoot = document.getElementById("pinned-history");
  const pinnedWrap = document.getElementById("sidebar-pinned");
  const chatsWrap = document.getElementById("sidebar-chats");
  const pinned = chats.filter((item) => item.pinned);
  const rest = sortedChats(chats.filter((item) => !item.pinned));
  if (pinnedRoot && pinnedWrap) {
    pinnedRoot.replaceChildren();
    pinnedWrap.hidden = pinned.length === 0;
    for (const chat of pinned) pinnedRoot.append(historyRow(chat));
  }
  chatHistory.replaceChildren();
  chatsWrap?.classList.toggle("is-collapsed", chatsCollapsed);
  const toggle = document.getElementById("toggle-chats");
  if (toggle) toggle.setAttribute("aria-expanded", String(!chatsCollapsed));
  if (!chats.length) {
    chatHistory.append(el("p", "history-empty", "There are no chats yet."));
    return;
  }
  if (!rest.length) {
    chatHistory.append(el("p", "history-empty", "No other chats besides the ones already pinned."));
    return;
  }
  for (const chat of rest) chatHistory.append(historyRow(chat));
}

function togglePin(chatId) {
  const chat = chats.find((item) => item.id === chatId);
  if (!chat) return;
  chat.pinned = !chat.pinned;
  renderHistory();
  persistChats();
  renderRecents();
}

function askRenameChat(chatId, title) {
  pendingRenameChatId = chatId;
  const input = document.getElementById("rename-chat-input");
  if (input) input.value = title || "";
  openDialog(document.getElementById("rename-dialog"));
  input?.focus();
  input?.select();
}

function renameChat(chatId, title) {
  const chat = chats.find((item) => item.id === chatId);
  const next = String(title || "").trim();
  if (!chat || !next) return;
  chat.title = historyTitle(next);
  renderHistory();
  persistChats();
  renderRecents();
}

function renderRecents() {
  const root = document.getElementById("recents-list");
  if (!root) return;
  const query = (document.getElementById("recents-search")?.value || "").trim().toLowerCase();
  const sort = document.getElementById("recents-sort")?.value || "recent";
  let rows = chats.filter((item) => !query || String(item.title || "").toLowerCase().includes(query));
  if (sort === "title") {
    rows = [...rows].sort((a, b) => String(a.title || "").localeCompare(String(b.title || "")));
  } else if (sort === "pinned") {
    rows = [...rows].sort((a, b) => Number(Boolean(b.pinned)) - Number(Boolean(a.pinned)));
  }
  root.replaceChildren();
  if (!rows.length) {
    root.append(el("p", "history-empty", chats.length ? "No matching chats." : "There are no chats yet."));
    return;
  }
  const groups =
    sort === "pinned"
      ? [
          ["Pinned", rows.filter((item) => item.pinned)],
          ["Chats", rows.filter((item) => !item.pinned)],
        ]
      : [["", rows]];
  for (const [label, items] of groups) {
    if (!items.length) continue;
    if (label) root.append(el("h3", "recents-group", label));
    for (const chat of items) {
      const row = el("div", "recents-row");
      const check = document.createElement("input");
      check.type = "checkbox";
      check.checked = recentsSelected.has(chat.id);
      check.setAttribute("aria-label", `Select ${chat.title}`);
      check.addEventListener("change", () => {
        if (check.checked) recentsSelected.add(chat.id);
        else recentsSelected.delete(chat.id);
        const del = document.getElementById("recents-delete");
        if (del) del.hidden = recentsSelected.size === 0;
      });
      row.append(check, historyRow(chat));
      root.append(row);
    }
  }
  const del = document.getElementById("recents-delete");
  if (del) del.hidden = recentsSelected.size === 0;
}

async function deleteChat(chatId) {
  const index = chats.findIndex((item) => item.id === chatId);
  if (index < 0) return;
  const wasActive = chatId === activeChatId;
  if (wasActive) abandonInFlight();
  chats.splice(index, 1);
  if (!wasActive) {
    renderHistory();
    persistChats();
    renderRecents();
    recentsSelected.delete(chatId);
    return;
  }
  const next = chats[0];
  if (next) {
    activeChatId = "";
    openChat(next.id);
    renderRecents();
    return;
  }
  await createSession();
  activeChatId = "";
  showEmptyCanvas();
  renderHistory();
  persistChats();
  renderRecents();
  prompt.focus();
}

function ensureActiveChat(title) {
  if (activeChatId) {
    const existing = chats.find((item) => item.id === activeChatId);
    if (existing) return existing;
  }
  const chat = {
    id: crypto.randomUUID(),
    sessionId,
    title: historyTitle(title),
    html: "",
    pinned: false,
    updated: new Date().toISOString(),
    running: false,
  };
  chats.unshift(chat);
  activeChatId = chat.id;
  renderHistory();
  persistChats();
  return chat;
}

function settleIncompleteTurn() {
  const last = threadEl().querySelector(".turn:last-child");
  if (!last) return;
  const inFlight = last.classList.contains("pending");
  last.querySelector(".status")?.remove();
  last.querySelector(".caret")?.remove();
  last.classList.remove("pending");
  if (inFlight && !last.querySelector(".stopped")) {
    last.append(el("p", "error stopped", `Stopped. ${assistantName} cancelled this reply.`));
  }
}

function abandonInFlight() {
  abortController?.abort();
  abortController = null;
  requestGen += 1;
  setBusy(false);
}

function openChat(chatId) {
  const chat = chats.find((item) => item.id === chatId);
  if (!chat) return;
  closeDialogs();
  setLibrary(false, { keepPanel: true });
  closeSidebarOnNarrow();
  if (chat.id === activeChatId) {
    prompt.focus();
    return;
  }
  abandonInFlight();
  settleIncompleteTurn();
  snapshotActive();
  activeChatId = chat.id;
  sessionId = chat.sessionId;
  if (chat.html && chat.html.includes("turn")) {
    threadEl().innerHTML = chat.html;
    hydrateTurns();
  } else showEmptyCanvas();
  renderHistory();
  persistChats();
  renderQueryNav();
  scrollChat(true);
  prompt.focus();
}

async function createSession() {
  const response = await fetch(apiUrl("/api/session"), { method: "POST" });
  if (!response.ok) throw new Error(`${assistantName} is unavailable`);
  const session = await response.json();
  sessionId = session.session_id;
  return sessionId;
}

async function startNewChat() {
  setLibrary(false);
  abandonInFlight();
  settleIncompleteTurn();
  snapshotActive();
  if (!canvasHasTurns() && !activeChatId) {
    prompt.focus();
    return;
  }
  await createSession();
  activeChatId = "";
  clearTaskSelection();
  prompt.value = "";
  resizePrompt();
  clearAttachments();
  showEmptyCanvas();
  renderHistory();
  persistChats();
  prompt.focus();
}

function renderQueryNav() {
  if (!queryNav) return;
  const turns = [...canvas.querySelectorAll(".turn")];
  queryNav.replaceChildren();
  queryNav.hidden = turns.length === 0;
  turns.forEach((turn, index) => {
    if (!turn.id) turn.id = `turn-${index + 1}`;
    const mark = el("button", "query-mark");
    mark.type = "button";
    const preview = turn.querySelector(".bubble.user")?.textContent || `Query ${index + 1}`;
    const label = preview.replace(/\s+/g, " ").trim().slice(0, 80);
    mark.dataset.preview = label;
    mark.setAttribute("aria-label", `Jump to query ${index + 1}: ${label}`);
    mark.addEventListener("click", () => {
      turn.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    queryNav.append(mark);
  });
  highlightQueryNav();
}

function highlightQueryNav() {
  const turns = [...canvas.querySelectorAll(".turn")];
  const marks = [...queryNav.querySelectorAll(".query-mark")];
  if (!turns.length || !marks.length) return;
  const target = canvas.getBoundingClientRect().top + canvas.clientHeight * 0.28;
  let active = 0;
  turns.forEach((turn, index) => {
    if (turn.getBoundingClientRect().top <= target) active = index;
  });
  marks.forEach((mark, index) => mark.classList.toggle("active", index === active));
}

function hydrateTurns() {
  for (const button of threadEl().querySelectorAll(".turn-delete")) button.remove();
  for (const para of threadEl().querySelectorAll(".reasoning-body p")) {
    const line = para.textContent.trim();
    const words = line.split(/\s+/);
    if (
      words.length >= 2 &&
      words.length <= 8 &&
      line.length <= 64 &&
      !/[.!?:]$/.test(line) &&
      /^[A-Z]/.test(line)
    ) {
      para.classList.add("reasoning-title");
    }
  }
}

function appendTurn(userText) {
  document.getElementById("placeholder")?.remove();
  const turn = el("section", "turn pending");
  turn.id = `turn-${crypto.randomUUID()}`;
  const userBubble = el("div", "bubble user", userText);
  const head = el("div", "turn-head");
  head.append(userBubble);
  const reasoning = el("div", "reasoning is-open");
  reasoning.hidden = !showReasoning;
  reasoning.dataset.open = "true";
  reasoning.dataset.streaming = "true";
  const trigger = el("button", "reasoning-trigger");
  trigger.type = "button";
  const triggerLabel = el("span", "reasoning-trigger-label", "Thinking");
  const chevron = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  chevron.setAttribute("viewBox", "0 0 24 24");
  chevron.setAttribute("aria-hidden", "true");
  chevron.classList.add("reasoning-chevron");
  const chevronPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
  chevronPath.setAttribute("d", "M6 9l6 6 6-6");
  chevron.append(chevronPath);
  trigger.append(triggerLabel, chevron);
  const reasoningShell = el("div", "reasoning-shell");
  const reasoningBody = el("div", "reasoning-body");
  reasoningShell.append(reasoningBody);
  reasoning.append(trigger, reasoningShell);
  const status = el("p", "status");
  setStatus(status, `${assistantName} is working…`);
  const reply = el("div", "reply");
  const assistant = el("div", "turn-assistant");
  assistant.append(reasoning, status, reply);
  turn.append(head, assistant);
  threadEl().append(turn);
  revealLatestQuery(turn);
  ensureActiveChat(userText);
  snapshotActive();
  renderQueryNav();
  return { userBubble, status, reply, turn, reasoning, reasoningBody, triggerLabel };
}

function setBusy(busy) {
  send.disabled = busy;
  send.hidden = busy;
  stop.hidden = !busy;
  attachBtn.disabled = busy;
  const chat = chats.find((item) => item.id === activeChatId);
  if (chat) {
    chat.running = busy;
    chat.updated = new Date().toISOString();
    renderHistory();
    persistChats();
  }
}

function selectTask(taskId) {
  if (activeTask === taskId) {
    clearTaskSelection();
    prompt.value = "";
    resizePrompt();
    prompt.focus();
    return;
  }
  activeTask = taskId;
  syncTaskButtons();
  syncFilterAvailability();
  fillComposer(taskId);
  renderSelection();
  closeDialogs();
  closeSidebarOnNarrow();
}

function renderAttachChips() {
  attachChips.replaceChildren();
  attachChips.hidden = !attachments.length;
  for (const item of attachments) {
    const chip = el("div", "attach-chip");
    chip.append(el("span", "", item.filename));
    const remove = el("button", "", "×");
    remove.type = "button";
    remove.setAttribute("aria-label", `Remove ${item.filename}`);
    remove.addEventListener("click", () => {
      attachments = attachments.filter((file) => file !== item);
      renderAttachChips();
    });
    chip.append(remove);
    attachChips.append(chip);
  }
}

function clearAttachments() {
  attachments = [];
  attachInput.value = "";
  renderAttachChips();
}

function suffixOf(name) {
  const dot = name.lastIndexOf(".");
  return dot === -1 ? "" : name.slice(dot).toLowerCase();
}

function readFileAsAttachment(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || "");
      const base64 = result.includes(",") ? result.split(",")[1] : result;
      resolve({
        filename: file.name,
        mime_type: file.type,
        content_base64: base64,
      });
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

async function addFiles(fileList) {
  const incoming = [...fileList];
  for (const file of incoming) {
    if (attachments.length >= MAX_ATTACH) break;
    if (!ALLOWED_ATTACH.has(suffixOf(file.name))) continue;
    if (file.size > MAX_ATTACH_BYTES) continue;
    attachments.push(await readFileAsAttachment(file));
  }
  renderAttachChips();
  attachInput.value = "";
}

async function readSse(response, onEvent, signal) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const onAbort = () => reader.cancel();
  signal?.addEventListener("abort", onAbort, { once: true });
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() || "";
      for (const chunk of chunks) {
        const line = chunk
          .split("\n")
          .filter((part) => part.startsWith("data:"))
          .map((part) => part.slice(5).trim())
          .join("");
        if (!line) continue;
        const parsed = JSON.parse(line);
        if (parsed.type !== "delta") {
          console.log(`[${activeRole}.sse]`, parsed.type, parsed);
        }
        onEvent(parsed);
      }
    }
  } finally {
    signal?.removeEventListener("abort", onAbort);
  }
}

async function askBob({ text }) {
  abortController?.abort();
  const gen = ++requestGen;
  abortController = new AbortController();
  const { signal } = abortController;
  settleIncompleteTurn();
  const filters = currentFilters();
  const files = attachments.map((item) => ({ ...item }));
  const preview = files.length
    ? `${text}\n\nAttached: ${files.map((item) => item.filename).join(", ")}`
    : text;
  const { userBubble, status, reply, turn, reasoning, reasoningBody, triggerLabel } =
    appendTurn(preview);
  let reasoningText = "";
  const paintReasoning = () => {
    if (!reasoning || !reasoningBody) return;
    const titleKeys = new Set();
    const stripped = String(reasoningText || "")
      .replace(/\*\*([^*]+)\*\*/g, (_, title) => {
        const clean = String(title).trim();
        if (clean) titleKeys.add(clean.replace(/\s+/g, " ").toLowerCase());
        return clean;
      })
      .replace(/`([^`]+)`/g, "$1");
    const isTitle = (line) => {
      const key = line.replace(/\s+/g, " ").toLowerCase();
      if (titleKeys.has(key)) return true;
      const words = line.split(/\s+/);
      if (words.length < 2 || words.length > 8) return false;
      if (line.length > 64 || /[.!?:]$/.test(line)) return false;
      return /^[A-Z]/.test(line);
    };
    reasoningBody.replaceChildren();
    if (reasoningText.trim()) {
      const seen = new Set();
      for (const para of stripped.split(/\n{2,}/)) {
        const line = para.trim();
        const key = line.replace(/\s+/g, " ").toLowerCase();
        if (!line || seen.has(key)) continue;
        seen.add(key);
        reasoningBody.append(
          el("p", isTitle(line) ? "reasoning-title" : "", line)
        );
      }
    }
    reasoning.hidden = false;
    reasoning.dataset.streaming = "true";
    setReasoningOpen(reasoning, true);
    if (triggerLabel) triggerLabel.textContent = "Thinking";
  };
  const finishReasoning = () => {
    if (!reasoning) return;
    const hasContent = Boolean(reasoningText.trim());
    reasoning.dataset.streaming = "false";
    if (!hasContent) {
      reasoning.hidden = true;
      return;
    }
    reasoning.hidden = false;
    setReasoningOpen(reasoning, false);
  };
  const chatId = activeChatId;
  const onThisChat = () => gen === requestGen && canvas.contains(reply);
  let streamEl = null;
  let caret = null;
  let incoming = "";
  let shown = "";
  let timer = null;
  let pendingReply = null;
  let replaceQuietly = false;
  const STREAM_MS = 95;
  const paintShown = () => {
    if (looksMarkdown(shown)) {
      if (!streamEl) {
        streamEl = el("div", "stream md-prose");
        caret = el("span", "caret");
        reply.append(streamEl);
      } else {
        streamEl.className = "stream md-prose";
      }
      const md = renderMarkdown(shown);
      streamEl.replaceChildren();
      for (const node of [...md.childNodes]) streamEl.append(node);
      if (caret) streamEl.append(caret);
      scrollChat();
      return;
    }
    if (!streamEl) {
      streamEl = el("div", "stream");
      caret = el("span", "caret");
      streamEl.append(caret);
      reply.append(streamEl);
    } else {
      streamEl.className = "stream";
    }
    streamEl.replaceChildren(document.createTextNode(shown));
    if (caret) streamEl.append(caret);
    scrollChat();
  };
  const applyReply = (event) => {
    caret?.remove();
    status.remove();
    turn.classList.remove("pending");
    streamEl?.remove();
    reply.querySelector(".briefing")?.remove();
    const extracted = extractReplyArtifacts(event, shown);
    const { saved, decks } = persistChatArtifacts(extracted);
    if (event.kind === "briefing") {
      reply.append(renderBriefing(event));
    } else {
      reply.append(renderMarkdown(event.text || shown));
      addReplyCopy(reply, event.text || shown);
    }
    appendArtifactBar(reply, saved, decks);
    scrollChat();
    snapshotActive();
  };
  const tickReveal = () => {
    if (!onThisChat()) {
      clearInterval(timer);
      timer = null;
      return;
    }
    if (incoming) {
      let take = "";
      const words = pendingReply ? 2 : 1;
      for (let i = 0; i < words && incoming; i += 1) {
        const match = incoming.match(/^\S+\s*/);
        if (!match) {
          take += incoming;
          incoming = "";
          break;
        }
        take += match[0];
        incoming = incoming.slice(match[0].length);
      }
      shown += take;
      paintShown();
      return;
    }
    clearInterval(timer);
    timer = null;
    if (pendingReply) {
      const event = pendingReply;
      pendingReply = null;
      applyReply(event);
    }
  };
  const startReveal = () => {
    if (!timer) timer = setInterval(tickReveal, STREAM_MS);
  };
  setBusy(true);
  const body = {
    role: activeRole,
    session_id: sessionId,
    task_id: activeTask,
    message: text,
    filters,
  };
  if (files.length) body.attachments = files;
  clearAttachments();
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
    const headerSession = response.headers.get("X-Session-Id");
    if (headerSession) {
      sessionId = headerSession;
      const chat = chats.find((item) => item.id === chatId);
      if (chat) chat.sessionId = headerSession;
    }
    if (!response.ok) {
      if (!onThisChat()) return;
      status.remove();
      turn.classList.remove("pending");
      reply.append(el("p", "error", "Could not send that. Try again."));
      return;
    }
    await readSse(
      response,
      (event) => {
        if (!onThisChat()) return;
        if (event.type === "prompt") {
          userBubble.textContent = event.text;
          const chat = chats.find((item) => item.id === chatId);
          if (chat && canvas.querySelectorAll(".turn").length === 1) {
            chat.title = historyTitle(event.text);
            renderHistory();
          }
        }
        if (event.type === "status") setStatus(status, event.label);
        if (event.type === "reasoning") {
          if (event.text) {
            const chunk = event.text;
            if (chunk.startsWith(reasoningText)) reasoningText = chunk;
            else if (reasoningText && reasoningText.includes(chunk.trim())) {
              /* already painted */
            } else if (reasoningText.trim() && chunk.includes(reasoningText.trim())) {
              reasoningText = chunk;
            } else {
              reasoningText += reasoningText ? `\n\n${chunk}` : chunk;
            }
          }
          paintReasoning();
        }
        if (event.type === "reasoning_done") finishReasoning();
        if (event.type === "reset") {
          replaceQuietly = Boolean(reply.querySelector(".briefing"));
          incoming = "";
          shown = "";
          pendingReply = null;
          reply.querySelector(".briefing")?.remove();
          if (streamEl && caret) streamEl.replaceChildren(caret);
          else if (streamEl) streamEl.replaceChildren();
        }
        if (event.type === "delta") {
          incoming += event.text;
          if (!replaceQuietly) startReveal();
        }
        if (event.type === "reply") {
          if (replaceQuietly || reply.querySelector(".briefing")) {
            incoming = "";
            replaceQuietly = false;
            applyReply(event);
            return;
          }
          pendingReply = event;
          startReveal();
        }
        if (event.type === "error") {
          if (timer) {
            clearInterval(timer);
            timer = null;
          }
          incoming = "";
          pendingReply = null;
          replaceQuietly = false;
          status.remove();
          turn.classList.remove("pending");
          finishReasoning();
          reply.append(el("p", "error", event.message));
          scrollChat();
          snapshotActive();
        }
      },
      signal
    );
    if (signal.aborted) {
      const abortError = new DOMException("Aborted", "AbortError");
      throw abortError;
    }
  } catch (err) {
    if (!onThisChat()) return;
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
    incoming = "";
    pendingReply = null;
    if (err.name === "AbortError") {
      settleIncompleteTurn();
    } else {
      status.remove();
      turn.classList.remove("pending");
      reply.append(el("p", "error", `${assistantName} lost the connection. Try that again.`));
    }
  } finally {
    if (gen !== requestGen) {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
      return;
    }
    if (incoming || pendingReply) startReveal();
    abortController = null;
    setBusy(false);
    finishReasoning();
    snapshotActive();
    prompt.focus();
  }
}

function fillSelect(select, items, allLabel) {
  if (!select) return;
  const current = select.value;
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
  if ([...select.options].some((option) => option.value === current)) select.value = current;
}

function addChecks(root, items, name) {
  if (!root) return;
  for (const item of items || []) {
    const row = el("label", "check");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = name;
    input.value = item.id;
    row.append(input, document.createTextNode(item.label));
    root.append(row);
  }
}

function bindSmoothGroup(block) {
  const summary = block.querySelector("summary");
  const panel = block.querySelector(".group-panel");
  summary.addEventListener("click", (event) => {
    if (!block.open) return;
    event.preventDefault();
    if (block.classList.contains("closing")) return;
    block.classList.add("closing");
    const finish = (end) => {
      if (end && end.target !== panel) return;
      if (end && end.propertyName && end.propertyName !== "grid-template-rows") return;
      clearTimeout(timer);
      panel.removeEventListener("transitionend", finish);
      block.open = false;
      block.classList.remove("closing");
    };
    const timer = setTimeout(finish, 280);
    panel.addEventListener("transitionend", finish);
  });
}

function showTaskGroup(group, anchor) {
  if (!taskItemsDialog || !taskItemsNav) return;
  taskItemsNav.replaceChildren();
  if (taskItemsTitle) taskItemsTitle.textContent = group.label;
  for (const item of group.items || []) {
    const button = el("button", "task", item.label);
    button.type = "button";
    button.dataset.taskId = item.id;
    if (item.id === activeTask) button.classList.add("active");
    button.addEventListener("click", () => selectTask(item.id));
    taskItemsNav.append(button);
  }
  openDialog(taskItemsDialog, anchor, { keep: [tasksDialog] });
}

function renderTasks(groups) {
  taskMenu.replaceChildren();
  for (const group of groups) {
    const button = el("button", "task-group", group.label);
    button.type = "button";
    button.dataset.group = group.label;
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      const same =
        !taskItemsDialog.hidden &&
        taskItemsDialog.classList.contains("is-open") &&
        taskItemsTitle?.textContent === group.label;
      if (same) {
        closePopover(taskItemsDialog);
        button.classList.remove("active");
        return;
      }
      for (const node of taskMenu.querySelectorAll(".task-group")) {
        node.classList.toggle("active", node === button);
      }
      showTaskGroup(group, button);
    });
    taskMenu.append(button);
  }
}

function isNarrowViewport() {
  return window.matchMedia("(max-width: 860px)").matches;
}

function setSidebar(open) {
  workspaceEl.classList.toggle("sidebar-collapsed", !open);
  sidebarEl?.setAttribute("aria-hidden", open ? "false" : "true");
  toggleSidebarBtn?.setAttribute("aria-expanded", open ? "true" : "false");
  toggleSidebarBtn?.setAttribute("aria-pressed", open ? "true" : "false");
  toggleSidebarBtn?.setAttribute("aria-label", open ? "Hide sidebar" : "Show sidebar");
  toggleSidebarBtn?.classList.toggle("is-on", open);
  if (sidebarScrim) sidebarScrim.hidden = !(open && isNarrowViewport());
}

function closeSidebarOnNarrow() {
  if (isNarrowViewport()) setSidebar(false);
}

function hideDialogNow(dialog) {
  if (!dialog) return;
  dialog.classList.remove("is-open");
  dialog.hidden = true;
}

function closePopover(dialog) {
  if (!dialog || dialog.hidden) return;
  dialog.classList.remove("is-open");
  window.setTimeout(() => {
    if (dialog.classList.contains("is-open")) return;
    hideDialogNow(dialog);
  }, 160);
}

function clearTaskGroupActive() {
  for (const node of taskMenu?.querySelectorAll(".task-group.active") || []) {
    node.classList.remove("active");
  }
}

function closeDialogById(id) {
  if (id === "tasks-dialog") closeDialogById("task-items-dialog");
  if (id === "task-items-dialog") clearTaskGroupActive();
  const dialog = document.getElementById(id);
  if (!dialog) return;
  if (dialog.classList.contains("app-popover")) closePopover(dialog);
  else hideDialogNow(dialog);
  const modalOpen = [...document.querySelectorAll(".app-dialog:not(.app-popover)")].some(
    (node) => !node.hidden
  );
  if (!modalOpen && dialogScrim) dialogScrim.hidden = true;
  if (id === "delete-dialog") pendingDeleteChatId = "";
  if (id === "rename-dialog") pendingRenameChatId = "";
}

function closeDialogs() {
  closeDialogById("task-items-dialog");
  closeDialogById("tasks-dialog");
  closeDialogById("filters-dialog");
  closeDialogById("delete-dialog");
  closeDialogById("rename-dialog");
  closeDialogById("recents-dialog");
  closeDialogById("chats-sort-dialog");
}

function placePopover(dialog, anchor) {
  if (!dialog || !anchor) return;
  const gap = 8;
  const rect = anchor.getBoundingClientRect();
  dialog.hidden = false;
  const width = dialog.offsetWidth || 280;
  const height = dialog.offsetHeight || 320;
  let left = rect.right + gap;
  let top = rect.top;
  if (left + width > window.innerWidth - 12) left = Math.max(12, rect.left - width - gap);
  if (top + height > window.innerHeight - 12) top = Math.max(12, window.innerHeight - height - 12);
  dialog.style.top = `${top}px`;
  dialog.style.left = `${left}px`;
}

function openDialog(dialog, anchor, options = {}) {
  if (!dialog) return;
  const keep = new Set(options.keep || []);
  const isPopover = dialog.classList.contains("app-popover");
  for (const node of document.querySelectorAll(".app-dialog")) {
    if (node === dialog || keep.has(node)) continue;
    if (node.classList.contains("app-popover")) closePopover(node);
    else hideDialogNow(node);
  }
  if (isPopover) {
    if (dialogScrim) dialogScrim.hidden = true;
    placePopover(dialog, anchor);
    requestAnimationFrame(() => {
      requestAnimationFrame(() => dialog.classList.add("is-open"));
    });
    return;
  }
  dialog.hidden = false;
  if (dialogScrim) dialogScrim.hidden = false;
}

function askDeleteChat(chatId, title) {
  pendingDeleteChatId = chatId;
  if (deleteDialogCopy) {
    deleteDialogCopy.textContent = `Delete “${title}”? This cannot be undone.`;
  }
  openDialog(deleteDialog);
}

function bootDialogs() {
  const openTasks = document.getElementById("open-tasks");
  const openFilters = document.getElementById("open-filters");
  const openChatsSort = document.getElementById("open-chats-sort");
  const chatsSortDialog = document.getElementById("chats-sort-dialog");
  openTasks?.addEventListener("click", (event) => {
    event.stopPropagation();
    if (!tasksDialog.hidden && tasksDialog.classList.contains("is-open")) {
      closeDialogs();
      return;
    }
    openDialog(tasksDialog, openTasks);
  });
  openFilters?.addEventListener("click", (event) => {
    event.stopPropagation();
    if (!filtersDialog.hidden && filtersDialog.classList.contains("is-open")) {
      closeDialogs();
      return;
    }
    openDialog(filtersDialog, openFilters);
  });
  openChatsSort?.addEventListener("click", (event) => {
    event.stopPropagation();
    if (!chatsSortDialog.hidden && chatsSortDialog.classList.contains("is-open")) {
      closeDialogById("chats-sort-dialog");
      return;
    }
    openDialog(chatsSortDialog, openChatsSort);
  });
  dialogScrim?.addEventListener("click", closeDialogs);
  for (const button of document.querySelectorAll("[data-close-dialog]")) {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      closeDialogById(button.getAttribute("data-close-dialog"));
    });
  }
  confirmDeleteChat?.addEventListener("click", async () => {
    const id = pendingDeleteChatId;
    closeDialogs();
    if (id) await deleteChat(id);
  });
  document.getElementById("confirm-rename-chat")?.addEventListener("click", () => {
    const id = pendingRenameChatId;
    const title = document.getElementById("rename-chat-input")?.value || "";
    closeDialogs();
    if (id) renameChat(id, title);
  });
  document.getElementById("rename-chat-input")?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      document.getElementById("confirm-rename-chat")?.click();
    }
  });
  document.getElementById("open-recents")?.addEventListener("click", () => {
    recentsSelected = new Set();
    renderRecents();
    openDialog(document.getElementById("recents-dialog"));
  });
  document.getElementById("recents-search")?.addEventListener("input", renderRecents);
  document.getElementById("recents-sort")?.addEventListener("change", renderRecents);
  document.getElementById("chats-sort")?.addEventListener("change", (event) => {
    chatsSort = event.target.value || "recent";
    renderHistory();
  });
  document.getElementById("recents-delete")?.addEventListener("click", async () => {
    const ids = [...recentsSelected];
    recentsSelected = new Set();
    for (const id of ids) await deleteChat(id);
    renderRecents();
  });
  document.getElementById("toggle-chats")?.addEventListener("click", () => {
    chatsCollapsed = !chatsCollapsed;
    renderHistory();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (taskItemsDialog?.classList.contains("is-open")) {
      closeDialogById("task-items-dialog");
      return;
    }
    closeDialogs();
  });
  document.addEventListener("mousedown", (event) => {
    const openPopovers = [...document.querySelectorAll(".app-popover.is-open")];
    if (!openPopovers.length) return;
    if (openPopovers.some((node) => node.contains(event.target))) return;
    if (event.target.closest("#open-tasks, #open-filters, #open-chats-sort")) return;
    for (const node of openPopovers) closePopover(node);
  });
  window.addEventListener("resize", () => {
    if (tasksDialog.classList.contains("is-open")) placePopover(tasksDialog, openTasks);
    if (filtersDialog.classList.contains("is-open")) placePopover(filtersDialog, openFilters);
    if (chatsSortDialog?.classList.contains("is-open")) placePopover(chatsSortDialog, openChatsSort);
  });
}

function bootSidebar() {
  setSidebar(!isNarrowViewport());
  window.matchMedia("(max-width: 860px)").addEventListener("change", (event) => {
    setSidebar(!event.matches);
  });
  toggleSidebarBtn?.addEventListener("click", () => {
    setSidebar(workspaceEl.classList.contains("sidebar-collapsed"));
  });
  sidebarScrim?.addEventListener("click", () => setSidebar(false));
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = prompt.value.trim();
  if ((!text && !attachments.length) || send.disabled) return;
  prompt.value = "";
  resizePrompt();
  askBob({ text: text || "Review the attached files." });
});

stop.addEventListener("click", () => {
  settleIncompleteTurn();
  snapshotActive();
  scrollChat(true);
  abortController?.abort();
  setBusy(false);
});

newChat.addEventListener("click", () => {
  startNewChat();
  closeSidebarOnNarrow();
});

attachBtn.addEventListener("click", () => attachInput.click());
attachInput.addEventListener("change", () => addFiles(attachInput.files || []));

function bootComposerDropzone() {
  if (!composerDrop) return;
  let dragDepth = 0;
  const showOverlay = () => {
    if (composerDropOverlay) composerDropOverlay.hidden = false;
    composerDrop.classList.add("is-dragover");
  };
  const hideOverlay = () => {
    dragDepth = 0;
    if (composerDropOverlay) composerDropOverlay.hidden = true;
    composerDrop.classList.remove("is-dragover");
  };
  composerDrop.addEventListener("dragenter", (event) => {
    event.preventDefault();
    dragDepth += 1;
    showOverlay();
  });
  composerDrop.addEventListener("dragover", (event) => {
    event.preventDefault();
  });
  composerDrop.addEventListener("dragleave", (event) => {
    event.preventDefault();
    dragDepth = Math.max(0, dragDepth - 1);
    if (dragDepth === 0) hideOverlay();
  });
  composerDrop.addEventListener("drop", (event) => {
    event.preventDefault();
    hideOverlay();
    if (event.dataTransfer?.files?.length) addFiles(event.dataTransfer.files);
  });
}

prompt.addEventListener("input", resizePrompt);

bootChatScroll();

prompt.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

async function boot() {
  applyAssistant();
  roleSelect?.addEventListener("change", () => {
    const next = roleSelect.value;
    if (!VALID_ROLES.has(next) || next === activeRole) return;
    abandonInFlight();
    snapshotActive();
    localStorage.setItem(ROLE_KEY, next);
    location.reload();
  });
  bootSidebar();
  bootDialogs();
  loadChats();
  const saved = chats.find((item) => item.id === activeChatId);
  if (saved?.sessionId) sessionId = saved.sessionId;
  if (!sessionId) await createSession();
  const workspaceResponse = await fetch(apiUrl("/api/workspace"));
  if (!workspaceResponse.ok) throw new Error(`${assistantName} workspace is unavailable`);
  workspace = await workspaceResponse.json();
  applyAssistant();
  showReasoning = Boolean(workspace?.ui?.reasoning);
  renderTasks(workspace.tasks || []);
  bootComposerDropzone();
  renderHistory();
  if (!restoreActiveChat()) showEmptyCanvas();
  const filters = workspace.filters || {};
  addChecks(filterOrg, filters.geos || [], "geo");
  addChecks(filterOrg, filters.boats || [], "boat");
  addChecks(filterOpps, filters.opps || [], "opp");
  addChecks(filterReports, filters.report_types || [], "report");
  fillSelect(filterSizes, filters.sizes || [], "All sizes");
  fillSelect(filterStages, filters.stages || [], "All stages");
  fillSelect(filterWindows, filters.windows || [], "All windows");
  syncFilterAvailability();
  applyDashboardLaunch();
  renderSelection();
  const refreshDraft = () => {
    if (activeTask) fillComposer(activeTask);
    renderSelection();
  };
  filterOrg.addEventListener("change", refreshDraft);
  filterOpps.addEventListener("change", refreshDraft);
  filterReports.addEventListener("change", refreshDraft);
  filterSizes?.addEventListener("change", refreshDraft);
  filterStages?.addEventListener("change", refreshDraft);
  filterWindows?.addEventListener("change", refreshDraft);
  document.getElementById("clear-selections")?.addEventListener("click", () => {
    for (const input of document.querySelectorAll("#filters-dialog .checks input:checked")) {
      input.checked = false;
    }
    for (const select of document.querySelectorAll("#filters-dialog select")) {
      select.value = "";
    }
    clearTaskSelection();
    prompt.value = "";
    resizePrompt();
    prompt.focus();
    renderSelection();
  });
  document.getElementById("open-library")?.addEventListener("click", () => {
    setLibrary(true);
    closeSidebarOnNarrow();
  });
  canvas?.addEventListener("click", (event) => {
    const save = event.target.closest("[data-artifact-save]");
    if (save) {
      const block = save.closest(".artifact");
      const body = block?.querySelector("pre")?.textContent || "";
      const item = {
        title: save.dataset.title || "Untitled",
        kind: save.dataset.kind || "other",
        body,
      };
      if (isDeckArtifact(item)) {
        downloadDeck(item.title, body);
        return;
      }
      window.BobArtifacts?.upsert([item], activeChatId);
      save.textContent = "Saved";
      return;
    }
    const chip = event.target.closest("[data-artifact-open]");
    if (chip?.dataset.artifactOpen) {
      window.BobArtifacts?.open(chip.dataset.artifactOpen);
      return;
    }
    const deck = event.target.closest("[data-deck-download]");
    if (deck) {
      downloadDeck(deck.dataset.deckTitle, deck.dataset.deckBody);
    }
  });
  window.__onOpenArtifact = (item, expanded) => {
    const panel = document.getElementById("artifact-panel");
    const chat = chats.find((row) => row.id === item.chatId);
    if (chat) {
      setLibrary(false, { keepPanel: true });
      if (chat.id !== activeChatId) openChat(chat.id);
      panel?.classList.toggle("is-wide", Boolean(expanded));
      return;
    }
    if (!document.getElementById("library")?.hidden) panel?.classList.add("is-wide");
  };
  if (new URLSearchParams(location.search).get("view") === "library") setLibrary(true);
}

boot();
