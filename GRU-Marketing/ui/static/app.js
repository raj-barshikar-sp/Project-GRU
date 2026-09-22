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
const filterContent = document.getElementById("filter-content");
const workspaceEl = document.getElementById("workspace");
const toggleSidebarBtn = document.getElementById("toggle-sidebar");
const queryNav = document.getElementById("query-nav");
const composerDrop = document.getElementById("composer-drop");
const composerDropOverlay = document.getElementById("composer-drop-overlay");
const composerHint = document.getElementById("composer-hint");
const composerSuggest = document.getElementById("composer-suggest");
const composerSuggestCopy = document.getElementById("composer-suggest-copy");
const composerSuggestPrimary = document.getElementById("composer-suggest-primary");
const composerSuggestSecondary = document.getElementById("composer-suggest-secondary");
const composerSuggestDismiss = document.getElementById("composer-suggest-dismiss");
const sidebarEl = document.getElementById("sidebar");
const sidebarScrim = document.getElementById("sidebar-scrim");
const dialogScrim = document.getElementById("dialog-scrim");
const tasksDialog = document.getElementById("tasks-dialog");
const taskItemsDialog = document.getElementById("task-items-dialog");
const taskItemsNav = document.getElementById("task-items");
const taskItemsTitle = document.getElementById("task-items-dialog-title");
const filtersDialog = document.getElementById("filters-dialog");
const chatSortDialog = document.getElementById("chat-sort-dialog");
const chatSortMenu = document.getElementById("chat-sort-menu");
const chatRecents = document.getElementById("chat-recents");
const chatRecentsBody = document.getElementById("chat-recents-body");
const chatRecentsSearch = document.getElementById("chat-recents-search");
const chatRecentsSearchBtn = document.getElementById("chat-recents-search-btn");
const chatRecentsSearchWrap = document.getElementById("chat-recents-search-wrap");
const chatRecentsSelect = document.getElementById("chat-recents-select");
const chatRecentsDelete = document.getElementById("chat-recents-delete");
const deleteDialog = document.getElementById("delete-dialog");
const deleteDialogTitle = document.getElementById("delete-dialog-title");
const deleteDialogCopy = document.getElementById("delete-dialog-copy");
const confirmDeleteChat = document.getElementById("confirm-delete-chat");
const collectionPromptDialog = document.getElementById("collection-prompt-dialog");
const collectionPromptTitle = document.getElementById("collection-prompt-title");
const collectionPromptInput = document.getElementById("collection-prompt-input");
const confirmCollectionPrompt = document.getElementById("confirm-collection-prompt");
const moveCollectionDialog = document.getElementById("move-collection-dialog");
const moveCollectionList = document.getElementById("move-collection-list");
let pendingDeleteChatId = "";
let pendingDeleteCollectionId = "";
let collectionPromptMode = "";
let renameCollectionId = "";
let renameChatId = "";
let moveChatId = "";

const ALLOWED_ATTACH = new Set([".pdf", ".csv", ".txt", ".xlsx", ".xls", ".docx", ".doc"]);
const MAX_ATTACH = 5;
const MAX_ATTACH_BYTES = 8 * 1024 * 1024;

let sessionId = "";
let workspace = null;
let activeTask = "";
let abortController = null;
let requestGen = 0;
let chats = [];
let collections = [];
let activeChatId = "";
let activeCollectionId = "";
const expandedCollections = new Set();
let collectionsShowAll = false;
const COLLECTION_SIDEBAR_LIMIT = 5;
const CHAT_LIST_KEY = "gru-chat-list";
const GROUP_LABELS = { none: "None", collection: "Collection", pinned: "Pinned" };
const SORT_LABELS = { activity: "Last activity", name: "Name" };
let chatsCollapsed = false;
let chatGroup = "none";
let chatSort = "activity";
let recentsQuery = "";
let recentsSelecting = false;
const recentsPicked = new Set();
let chatSortPane = "";
let attachments = [];
let showReasoning = false;
const pendingChats = new Set();
const liveChats = new Set();
const pollTimers = new Map();
const CHATS_KEY = "gru-chats";
const LAST_JOB_KEY = "gru-last-job";
const CHATS_LIMIT = 40;

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

let launchGeo = "";
let launchAccounts = [];
let launchEvents = [];
let launchSizes = "";
let launchStages = "";
let launchWindows = "";
let lastTaskId = "";
let sentTaskId = "";
let sentFilterKey = "";
let suggestKind = "";

function currentFilters() {
  return {
    campaigns: selectedValues("campaign"),
    campaign_types: selectedValues("campaign_type"),
    asset_types: selectedValues("asset_type"),
    content: selectedValues("content"),
    opps: selectedValues("campaign"),
    boats: selectedValues("campaign_type"),
    geos: launchGeo ? [launchGeo] : [],
    report_types: launchEvents,
    sizes: launchSizes ? [launchSizes] : [],
    stages: launchStages ? [launchStages] : [],
    windows: launchWindows ? [launchWindows] : [],
    events: launchEvents,
    accounts: launchAccounts,
  };
}

function allowedFilterNames(task) {
  const all = ["campaign", "campaign_type", "asset_type", "content"];
  const mapped = {
    campaigns: "campaign",
    campaign_types: "campaign_type",
    asset_types: "asset_type",
    content: "content",
  };
  if (!task) return new Set(all);
  if (Array.isArray(task.filter_policy?.categories)) {
    return new Set(
      task.filter_policy.categories.map((name) => mapped[name]).filter(Boolean)
    );
  }
  if (Array.isArray(task.filters)) return new Set(task.filters);
  return new Set(all);
}

function policyCampaignTypes(task) {
  const types = task?.filter_policy?.campaign_types;
  return Array.isArray(types) && types.length ? types : null;
}

function syncFilterAvailability() {
  const task = activeTask ? findTask(activeTask) : null;
  const names = allowedFilterNames(task);
  const restrict = Boolean(task);
  const policyTypes = policyCampaignTypes(task);
  const typeInputs = [
    ...document.querySelectorAll('#filters-dialog input[name="campaign_type"]'),
  ];
  for (const input of typeInputs) {
    const allowed =
      (!restrict || names.has("campaign_type")) &&
      (!policyTypes || policyTypes.includes(input.value));
    input.disabled = !allowed;
    if (!allowed) input.checked = false;
  }
  const selectedTypes = typeInputs
    .filter((node) => node.checked && !node.disabled)
    .map((node) => node.value);
  const assetInputs = [
    ...document.querySelectorAll('#filters-dialog input[name="asset_type"]'),
  ];
  for (const input of assetInputs) {
    const allowed = !restrict || names.has("asset_type");
    input.disabled = !allowed;
    if (!allowed) input.checked = false;
  }
  const selectedAssets = assetInputs
    .filter((node) => node.checked && !node.disabled)
    .map((node) => node.value);
  for (const input of document.querySelectorAll(
    "#filters-dialog .checks input, #filters-dialog select"
  )) {
    if (input.name === "campaign_type" || input.name === "asset_type") continue;
    let allowed = !restrict || names.has(input.name);
    if (allowed && input.name === "campaign") {
      const rowType = input.dataset.type;
      if (policyTypes && rowType && !policyTypes.includes(rowType)) allowed = false;
      if (selectedTypes.length && rowType && !selectedTypes.includes(rowType)) {
        allowed = false;
      }
    }
    if (allowed && input.name === "content") {
      const rowType = input.dataset.type;
      if (selectedAssets.length && rowType && !selectedAssets.includes(rowType)) {
        allowed = false;
      }
    }
    input.disabled = !allowed;
    if (!allowed) {
      if (input.type === "checkbox") input.checked = false;
      else input.value = "";
    }
  }
  for (const block of document.querySelectorAll("#filters-dialog .filter-block")) {
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

function joinNames(names) {
  const labels = names.filter(Boolean);
  if (!labels.length) return "";
  if (labels.length === 1) return labels[0];
  if (labels.length === 2) return `${labels[0]} and ${labels[1]}`;
  return `${labels.slice(0, -1).join(", ")}, and ${labels[labels.length - 1]}`;
}

function fillPrompt(template, values) {
  if (!template) return "";
  const needed = [...String(template).matchAll(/\{(\w+)\}/g)].map((match) => match[1]);
  if (needed.length && !needed.some((name) => values[name])) return "";
  let text = template.replace(/\{(\w+)\}/g, (_, name) => values[name] || "");
  text = text.replace(/\s{2,}/g, " ");
  text = text.replace(/\s+for\s+(?=as\b)/gi, "");
  text = text.replace(
    /\s+(?:for|using|around|related to|at|in|from|on|covering|as a|as an)\s*(?=[.,:;?!]|$)/gi,
    ""
  );
  text = text.replace(/\s*\(\s*\)/g, "");
  text = text.replace(/\s{2,}/g, " ").replace(/\s+([.,:;?!])/g, "$1").trim();
  if (!text || /\{(\w+)\}/.test(text) || /\bhow did perform\b/i.test(text)) return "";
  return text;
}

function composeDraft(taskId) {
  const task = findTask(taskId);
  if (!task) return "";
  const filters = currentFilters();
  const campaigns = workspace?.filters?.campaigns || workspace?.filters?.opps || [];
  const campaignMap = Object.fromEntries(campaigns.map((item) => [item.id, item]));
  const contentMap = Object.fromEntries(
    (workspace?.filters?.content || []).map((item) => [item.id, item])
  );
  const campaign = joinNames(
    filters.campaigns
      .map((id) => campaignMap[id]?.label)
      .filter(Boolean)
      .map((label) => String(label).split(" · ").pop())
  );
  const campaignType = joinNames(filters.campaign_types);
  const assetType = joinNames(filters.asset_types);
  const content = joinNames(
    filters.content.map((id) => contentMap[id]?.label).filter(Boolean)
  );
  const accounts = workspace?.filters?.accounts || [];
  const accountMap = Object.fromEntries(accounts.map((item) => [item.id, item]));
  const events = workspace?.filters?.events || workspace?.filters?.report_types || [];
  const eventMap = Object.fromEntries(events.map((item) => [item.id, item]));
  const account = joinNames(
    filters.accounts.map((id) => accountMap[id]?.label).filter(Boolean)
  );
  const event = joinNames(
    filters.events.map((id) => eventMap[id]?.name || eventMap[id]?.label).filter(Boolean)
  );
  const region =
    joinNames(filters.geos) || campaignMap[filters.campaigns[0]]?.region || "";
  const values = {
    account,
    territory: region,
    region,
    campaign,
    campaign_type: campaignType,
    asset_type: assetType,
    content,
    event,
  };
  return (
    fillPrompt(task.scoped_prompt, values) ||
    fillPrompt(task.geo_prompt, values) ||
    task.default_prompt ||
    ""
  );
}

function syncTaskButtons() {
  for (const node of document.querySelectorAll("#task-menu .task, #task-items .task")) {
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
  chip.dataset.label = label;
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

function syncChatUrl() {
  const params = new URLSearchParams(location.search);
  const next = new URLSearchParams();
  const view = params.get("view");
  const artifact = params.get("artifact");
  if (view) next.set("view", view);
  if (artifact) next.set("artifact", artifact);
  if (activeTask) next.set("task", activeTask);
  if (activeCollectionId) next.set("collection", activeCollectionId);
  const campaign = document.querySelector(
    '#filters-dialog input[name="campaign"]:checked:not(:disabled)'
  );
  if (campaign) next.set("campaign", campaign.value);
  const type = document.querySelector(
    '#filters-dialog input[name="campaign_type"]:checked:not(:disabled)'
  );
  if (type) next.set("type", type.value);
  if (launchGeo) next.set("geo", launchGeo);
  if (launchSizes) next.set("sizes", launchSizes);
  if (launchStages) next.set("stages", launchStages);
  if (launchWindows) next.set("windows", launchWindows);
  if (launchAccounts[0]) next.set("account", launchAccounts[0]);
  if (launchEvents[0]) next.set("event", launchEvents[0]);
  const qs = next.toString();
  const href = qs ? `/chat?${qs}` : "/chat";
  if (`${location.pathname}${location.search}` !== href) {
    history.replaceState(null, "", href);
  }
}

function renderSelection() {
  const panel = document.getElementById("sidebar-selected");
  const root = document.getElementById("selected-chips");
  if (!panel || !root) return;
  const wanted = [];
  const task = activeTask ? findTask(activeTask) : null;
  if (task) {
    const group = taskGroupLabel(activeTask);
    const label = group ? `${group} · ${task.label}` : task.label;
    wanted.push({
      label,
      onClear: () => {
        clearTaskSelection();
        prompt.value = "";
        resizePrompt();
        prompt.focus();
      },
    });
  }
  if (launchGeo) {
    wanted.push({
      label: `Geo · ${launchGeo}`,
      onClear: () => {
        launchGeo = "";
        if (activeTask) fillComposer(activeTask);
        else renderSelection();
      },
    });
  }
  if (launchSizes) {
    wanted.push({
      label: `Size · ${launchSizes}`,
      onClear: () => {
        launchSizes = "";
        renderSelection();
      },
    });
  }
  if (launchStages) {
    wanted.push({
      label: `Type · ${launchStages}`,
      onClear: () => {
        launchStages = "";
        renderSelection();
      },
    });
  }
  if (launchWindows) {
    wanted.push({
      label: `Time · ${launchWindows}`,
      onClear: () => {
        launchWindows = "";
        renderSelection();
      },
    });
  }
  for (const input of document.querySelectorAll(
    '#filters-dialog .checks input:checked:not(:disabled)'
  )) {
    const row = input.closest(".check");
    const label = (row?.textContent || input.value).replace(/\s+/g, " ").trim();
    wanted.push({
      label,
      onClear: () => {
        input.checked = false;
        input.dispatchEvent(new Event("change", { bubbles: true }));
      },
    });
  }
  for (const select of document.querySelectorAll("#filters-dialog select:not(:disabled)")) {
    if (!select.value) continue;
    const chosen = select.selectedOptions[0];
    const label = (chosen?.textContent || select.value).trim();
    wanted.push({
      label,
      onClear: () => {
        select.value = "";
        select.dispatchEvent(new Event("change", { bubbles: true }));
      },
    });
  }
  const keep = new Set(wanted.map((item) => item.label));
  for (const chip of [...root.children]) {
    if (!keep.has(chip.dataset.label) && !chip.classList.contains("is-out")) {
      if (window.JamesMotion?.leave) {
        window.JamesMotion.leave(chip, () => chip.remove());
      } else {
        chip.remove();
      }
    }
  }
  const existing = new Map(
    [...root.children]
      .filter((node) => !node.classList.contains("is-out"))
      .map((node) => [node.dataset.label, node])
  );
  for (const item of wanted) {
    if (existing.has(item.label)) continue;
    const chip = makeSelectionChip(item.label, item.onClear);
    root.append(chip);
    window.JamesMotion?.enter?.(chip);
  }
  panel.hidden = ![...root.children].some((node) => !node.classList.contains("is-out"));
  syncChatUrl();
  syncComposerHint();
}

function clearTaskSelection() {
  activeTask = "";
  syncTaskButtons();
  syncFilterAvailability();
  renderSelection();
}

function hasSelections() {
  if (activeTask || launchGeo || launchSizes || launchStages || launchWindows) return true;
  if (launchAccounts.length || launchEvents.length) return true;
  if (document.querySelector("#filters-dialog .checks input:checked")) return true;
  for (const select of document.querySelectorAll("#filters-dialog select")) {
    if (select.value) return true;
  }
  return false;
}

function clearAllSelections() {
  for (const input of document.querySelectorAll("#filters-dialog .checks input:checked")) {
    input.checked = false;
  }
  for (const select of document.querySelectorAll("#filters-dialog select")) {
    select.value = "";
  }
  launchGeo = "";
  launchSizes = "";
  launchStages = "";
  launchWindows = "";
  launchAccounts = [];
  launchEvents = [];
  clearTaskSelection();
}

function fillComposer(taskId) {
  activeTask = taskId;
  prompt.value = composeDraft(taskId);
  resizePrompt();
  prompt.focus();
  syncComposerHint();
}

const CLIPBOARD_ICON =
  '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="2"></rect><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"></path></svg>';
const CHECK_ICON =
  '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5 9.5 17 19 7.5"></path></svg>';

function addCopy(parent, text, label, inline) {
  const button = el("button", inline ? "copy inline t-icon-swap" : "copy t-icon-swap");
  button.type = "button";
  button.dataset.copy = text;
  button.dataset.state = "a";
  button.setAttribute("aria-label", label || "Copy");
  button.title = label || "Copy";
  const clip = el("span", "t-icon");
  clip.dataset.icon = "a";
  clip.innerHTML = CLIPBOARD_ICON;
  const check = el("span", "t-icon");
  check.dataset.icon = "b";
  check.innerHTML = CHECK_ICON;
  button.append(clip, check);
  parent.append(button);
}

function setReasoningOpen(box, open) {
  if (!box) return;
  const think = box.querySelector(".t-think");
  const label = box.querySelector(".reasoning-trigger-label");
  if (think && box.dataset.streaming !== "true" && box.dataset.done !== "true") {
    window.JamesMotion?.setThinkLine(think, open ? "Hide reasoning" : "Show reasoning", {
      shimmer: false,
    });
  } else if (label && box.dataset.streaming !== "true" && box.dataset.done !== "true") {
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
  button.dataset.state = "b";
  const prior = button.getAttribute("aria-label");
  button.setAttribute("aria-label", "Copied");
  clearTimeout(button._copyTimer);
  button._copyTimer = setTimeout(() => {
    button.dataset.state = "a";
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

function persistChatArtifacts(artifacts) {
  if (!artifacts?.length) return [];
  const persistable = artifacts.filter((item) => item.kind !== "pptx");
  const decks = artifacts.filter((item) => item.kind === "pptx");
  let stored = persistable;
  if (persistable.length) {
    try {
      const saved = window.JamesArtifacts?.upsertFromChat(persistable, activeChatId);
      if (saved?.length) stored = saved;
    } catch {
      /* private mode / quota */
    }
    if (stored === persistable) {
      stored = persistable.map((item) => ({
        ...item,
        id:
          item.id ||
          `${item.title || "Untitled"}|${item.kind || "other"}|${String(item.body || "").slice(0, 24)}`,
      }));
    }
  }
  return [...stored, ...decks];
}

function applyLaunchPrompt(taskId) {
  let packed = null;
  try {
    packed = JSON.parse(sessionStorage.getItem("james-launch") || "null");
    sessionStorage.removeItem("james-launch");
  } catch {
    packed = null;
  }
  if (!packed || packed.task !== taskId) return;
  if (packed.prompt) {
    prompt.value = packed.prompt;
    resizePrompt();
  }
  prompt.focus();
  if (packed.send && prompt.value.trim() && !send.disabled) {
    requestAnimationFrame(() => form.requestSubmit());
  }
}

function returningToChat() {
  try {
    const entry = performance.getEntriesByType("navigation")[0];
    return entry?.type === "reload" || entry?.type === "back_forward";
  } catch {
    return false;
  }
}

function dashboardLaunchParams() {
  // syncChatUrl keeps the task and filter ticks in the address bar, so on a
  // reload those params are the chat we are already in, not a new launch.
  if (returningToChat()) return false;
  const params = new URLSearchParams(location.search);
  return ["task", "campaign", "geo", "account", "event", "type", "scope", "sizes", "stages", "windows"].some(
    (key) => (params.get(key) || "").trim()
  );
}

function applyDashboardLaunch() {
  const params = new URLSearchParams(location.search);
  const taskId = params.get("task");
  const campaignId = (params.get("campaign") || "").trim();
  const scope = (params.get("scope") || "").trim();
  const geo = (params.get("geo") || "").trim();
  const type = (params.get("type") || params.get("stages") || "").trim();
  const accountId = (params.get("account") || "").trim();
  const eventId = (params.get("event") || "").trim();
  const sizes = (params.get("sizes") || "").trim();
  const stages = (params.get("stages") || "").trim();
  const windows = (params.get("windows") || "").trim();
  const campaigns = workspace?.filters?.campaigns || workspace?.filters?.opps || [];
  const tickCampaign = (id) => {
    const input = document.querySelector(
      `#filters-dialog input[name="campaign"][value="${CSS.escape(id)}"]`
    );
    if (input) input.checked = true;
  };
  if (campaignId) tickCampaign(campaignId);
  if (scope && !campaignId) {
    const hit = campaigns.find(
      (item) =>
        item.id === scope ||
        String(item.label || item.account || "").toLowerCase() === scope.toLowerCase()
    );
    if (hit) tickCampaign(hit.id);
  }
  if (type) {
    const typeInput = document.querySelector(
      `#filters-dialog input[name="campaign_type"][value="${CSS.escape(type)}"]`
    );
    if (typeInput) typeInput.checked = true;
  }
  launchGeo = geo;
  launchSizes = sizes;
  launchStages = stages;
  launchWindows = windows;
  launchAccounts = accountId ? [accountId] : [];
  launchEvents = eventId ? [eventId] : [];
  if (taskId && findTask(taskId)) {
    activeTask = taskId;
    lastTaskId = taskId;
    syncTaskButtons();
    syncFilterAvailability();
    fillComposer(taskId);
    applyLaunchPrompt(taskId);
  }
  renderSelection();
}

function addReplyCopy(parent, text, options = {}) {
  if (!text) return;
  const tools = el("div", "reply-tools");
  addCopy(tools, text, "Copy response", true);
  if (options.save) {
    const save = el("button", "reply-action", "Save this reply");
    save.type = "button";
    save.addEventListener("click", () => saveReplyAsNote(text, options.title || "Saved reply"));
    tools.append(save);
  }
  parent.append(tools);
}

function saveReplyAsNote(text, title) {
  try {
    window.JamesArtifacts?.upsertFromChat(
      [{ title, body: text, kind: "other" }],
      activeChatId
    );
    window.JamesMotion?.showToast("Saved to artifacts.");
  } catch {
    window.JamesMotion?.showToast("Could not save that reply.");
  }
}

function downloadArtifact(artifact) {
  if (artifact?.url) {
    const link = document.createElement("a");
    link.href = artifact.url;
    link.download = artifact.filename || artifact.title || "deck.pptx";
    link.target = "_blank";
    link.rel = "noopener";
    link.click();
    return;
  }
  const body = String(artifact?.body || "");
  if (!body) return;
  const slug = String(artifact.title || "artifact")
    .replace(/[^\w.-]+/g, "-")
    .replace(/^-|-$/g, "") || "artifact";
  const blob = new Blob([body], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${slug}.txt`;
  link.click();
  URL.revokeObjectURL(url);
}

function attachNotice(parent, payload) {
  if (!payload?.notice) return;
  parent.append(el("p", "sample-badge", "Sample data"));
}

function renderDeckDownloads(parent, downloads) {
  if (!downloads?.length) return;
  if (parent.querySelector(".artifact-chip-row .artifact-chip-download")) return;
  const row = el("div", "artifact-chip-row");
  for (const item of downloads) {
    const link = el("a", "artifact-chip-download");
    link.href = item.url;
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = "Open PowerPoint";
    if (item.filename) link.setAttribute("download", item.filename);
    row.append(link);
  }
  parent.append(row);
}

function retryTurn(turn) {
  const text = turn?.dataset?.retryText || "";
  if (!text.trim() || send.disabled) return;
  prompt.value = text;
  resizePrompt();
  form.requestSubmit();
}

function addRetry(parent, turn) {
  const button = el("button", "reply-action retry-turn", "Try again");
  button.type = "button";
  button.addEventListener("click", () => retryTurn(turn));
  parent.append(button);
}

function artifactChipIcon(kind) {
  const icon = el("span", "artifact-chip-icon");
  const drawn = window.JamesArtifacts?.kindIcon?.(kind);
  if (drawn) icon.append(drawn);
  else icon.textContent = kind === "email" ? "✉" : "📄";
  return icon;
}

const ARTIFACT_KICKERS = {
  email: "Email",
  talking_points: "Talking points",
  merge_instruction: "Merge",
  ask: "Ask",
  work_order: "Work order",
  other: "Note",
  pptx: "PowerPoint",
};

function looksHtmlDocument(body) {
  const text = String(body || "").trim();
  if (!text || looksLikeEmail(text)) return false;
  return /^<!DOCTYPE html/i.test(text) || /^<html[\s>]/i.test(text);
}

function renderArtifactPreview(target, body, kind) {
  if (!target) return;
  target.replaceChildren();
  const text = String(body || "");
  if (looksHtmlDocument(text)) {
    const frame = document.createElement("iframe");
    frame.className = "artifact-pane-frame";
    frame.setAttribute("sandbox", "allow-scripts");
    frame.setAttribute("referrerpolicy", "no-referrer");
    frame.title = "Artifact preview";
    frame.srcdoc = text;
    target.append(frame);
    return;
  }
  const page = el("div", "artifact-preview-page");
  const cleaned =
    kind === "email" || looksLikeEmail(text) ? stripEmailSignoff(text).trim() : text;
  page.append(renderMarkdown(cleaned));
  target.append(page);
}

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

function artifactBlock(body, kind) {
  const cleaned = looksLikeEmail(body) ? stripEmailSignoff(body).trim() : String(body || "").trim();
  if (!cleaned) return el("div");
  const block = el("div", `artifact artifact-${kind || (looksLikeEmail(cleaned) ? "email" : "other")}`);
  const pre = el("pre");
  pre.textContent = cleaned;
  block.append(pre);
  addCopy(block, cleaned, "Copy artifact");
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
  const spend = blob.match(/(?:spend|budget)[^$\n]{0,28}\$([\d,]+(?:\.\d+)?)/i);
  if (spend) metrics.push({ label: "Spend", value: `$${spend[1]}` });
  const mqls = blob.match(/(\d[\d,]*)\s*MQLs?/i);
  if (mqls) metrics.push({ label: "MQLs", value: mqls[1] });
  const days = blob.match(/(\d+)\s*days?\s+left(?:\s+in(?:\s+the)?\s+quarter)?/i);
  if (days) metrics.push({ label: "Days left", value: days[1] });
  return metrics;
}

function selectedCampaign() {
  const id = selectedValues("campaign")[0];
  if (!id) return null;
  const rows = workspace?.filters?.campaigns || workspace?.filters?.opps || [];
  return rows.find((row) => row.id === id) || null;
}

function formatSpend(amount) {
  const n = Number(amount);
  if (!Number.isFinite(n)) return "";
  return `$${Math.round(n).toLocaleString("en-US")}`;
}

function briefingHeader() {
  const campaign = selectedCampaign();
  if (!campaign) return null;
  const head = el("header", "briefing-head");
  const titleRow = el("div", "briefing-title-row");
  titleRow.append(el("h2", "briefing-title", campaign.label || campaign.account || ""));
  const score = Number(campaign.health);
  if (Number.isFinite(score) && score > 0) {
    const label = score >= 70 ? "On track" : score >= 45 ? "Watch" : "Off";
    const pill = el("span", "briefing-pill", label);
    pill.classList.add(score >= 70 ? "is-good" : score >= 45 ? "is-ok" : "is-thin");
    titleRow.append(pill);
  }
  head.append(titleRow);
  const bits = [
    campaign.region || campaign.territory,
    campaign.type || campaign.owner,
    campaign.spend != null && campaign.spend !== "" ? `spend ${formatSpend(campaign.spend)}` : "",
  ].filter(Boolean);
  if (bits.length) head.append(el("p", "briefing-meta", bits.join(" · ")));
  return head;
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
    /###\s+(.+?)(?:\s+·\s+(email|merge_instruction|talking_points|ask|work_order|other))?\s*\n```[a-zA-Z0-9_-]*\n([\s\S]*?)```/g;
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
    const url = String(item?.url || "").trim();
    if (!body && !url) return;
    const key = url || body;
    if (seen.has(key)) return;
    seen.add(key);
    items.push({
      title: item.title || "Untitled",
      kind: item.kind || (looksLikeEmail(body) ? "email" : "other"),
      body,
      url,
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

// A sentence ends at . ! or ? followed by a space or the end of the line.
// Without that guard the line ended inside "brief.json.md" or "2.0x", and the
// old character-count fallback cut the lead in the middle of a word. Returning
// nothing is the honest answer when there is no clean first sentence.
function spokenLine(summary) {
  const text = String(summary || "").replace(/\s+/g, " ").trim();
  if (!text) return "";
  const sentence = text.match(/^.{12,240}?[.!?](?=\s|$)/);
  return sentence ? sentence[0].trim() : "";
}

// The lead line above the card is the opening sentence of the summary, so the
// card itself carries what is left. Printing the whole summary under it made
// the reader parse the same sentence twice.
function summaryTail(summary, lead) {
  const text = String(summary || "").replace(/\s+/g, " ").trim();
  if (!lead || !text.startsWith(lead)) return text;
  const rest = text.slice(lead.length);
  // Splitting anywhere but a word boundary would start this paragraph in the
  // middle of a word, so keep the summary whole instead.
  if (rest && !/^\s/.test(rest)) return text;
  return rest.trim();
}

function rememberLastJob(taskId) {
  const task = findTask(taskId);
  if (!task) return;
  try {
    localStorage.setItem(
      LAST_JOB_KEY,
      JSON.stringify({ task: taskId, next: task.next_task || "" })
    );
  } catch {
    /* private mode / quota */
  }
}

function shouldOfferNextJob(event) {
  if (!event || event.kind === "cannot" || event.kind === "error") return false;
  const text = String(event.text || "");
  return !/I only handle marketing work/i.test(text);
}

function nextJobTask() {
  const current = findTask(activeTask || lastTaskId);
  const nextId = current?.next_task;
  return nextId ? findTask(nextId) : null;
}

function nextJobButton() {
  const next = nextJobTask();
  if (!next) return null;
  const button = el("button", "next-job");
  button.type = "button";
  button.append(el("span", "next-job-kicker", "Want this next?"));
  button.append(el("strong", "", next.label));
  button.addEventListener("click", () => selectTask(next.id));
  return button;
}

function renderBriefing(payload, options = {}) {
  const live = Boolean(options.live);
  const wrap = el("div", live ? "briefing live" : "briefing");
  attachNotice(wrap, payload);
  const header = briefingHeader();
  if (header) wrap.append(header);
  const lead = !live && payload.summary ? spokenLine(payload.summary) : "";
  if (lead) wrap.append(el("p", "briefing-voice", lead));
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
  const summaryBody = summaryTail(payload.summary, lead);
  if (summaryBody) {
    const summaryText = el("p", "summary-text");
    appendRich(summaryText, summaryBody);
    summary.append(summaryText);
  } else if (live) {
    const summaryText = el("p", "summary-text");
    summaryText.append(el("span", "card-empty", "Writing the briefing…"));
    summary.append(summaryText);
  }
  // A one-sentence summary is fully carried by the lead line, which leaves the
  // card holding nothing but its own heading.
  if (metrics.length || summaryBody || live) wrap.append(summary);

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
      let step = 0;
      for (const action of payload.actions) {
        step += 1;
        const row = el("div", "action-row");
        row.append(el("span", "action-index", String(step)));
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
        const next = nextJobTask();
        if (next && !live) {
          row.classList.add("is-job");
          row.title = `Continue with ${next.label}`;
          row.addEventListener("click", () => selectTask(next.id));
        }
        actions.append(row);
      }
    } else {
      actions.append(el("p", "card-empty", "Drafting next steps…"));
    }
    wrap.append(actions);
  }

  if (live || payload.artifacts?.length) {
    const artifacts = el("article", "card card-artifacts");
    artifacts.append(el("h3", "", "Artifacts"));
    if (payload.artifacts?.length) {
      for (const artifact of payload.artifacts) {
        const kind = artifact.kind || "other";
        const body =
          kind === "email" ? stripEmailSignoff(artifact.body || "").trim() : artifact.body;
        const storedChip = persistChatArtifacts([{ ...artifact, body, kind }]);
        const saved = storedChip?.[0] || artifact;
        const chip = el("button", `artifact-chip artifact-${kind}`);
        chip.type = "button";
        chip.dataset.artifactId = saved.id || "";
        chip.dataset.artifactKind = kind;
        const icon = artifactChipIcon(kind);
        const copy = el("span", "artifact-chip-copy");
        copy.append(el("strong", "", artifact.title || "Untitled"));
        copy.append(el("span", "", ARTIFACT_KICKERS[kind] || "Note"));
        chip.append(icon, copy);
        chip.addEventListener("click", (event) => {
          event.preventDefault();
          event.stopPropagation();
          if (kind === "pptx" && artifact.url) {
            downloadArtifact({ ...artifact, kind, filename: artifact.filename || artifact.title });
            return;
          }
          const stored = persistChatArtifacts([{ ...artifact, body, kind }]);
          const item = stored?.[0];
          if (item) window.JamesArtifacts?.openPane(item, undefined, { instant: true });
        });
        const row = el("div", "artifact-chip-row");
        row.append(chip);
        if (body || artifact.url) {
          const dl = el("button", "artifact-chip-download", kind === "pptx" ? "Open" : "Download");
          dl.type = "button";
          dl.addEventListener("click", (event) => {
            event.stopPropagation();
            downloadArtifact({
              ...artifact,
              body,
              kind,
              filename: artifact.filename || artifact.title,
            });
          });
          row.append(dl);
        }
        artifacts.append(row);
      }
    } else {
      artifacts.append(el("p", "card-empty", "Preparing copy…"));
    }
    wrap.append(artifacts);
  }
  if (!live) {
    if (shouldOfferNextJob(payload)) {
      const next = nextJobButton();
      if (next) wrap.append(next);
    }
    addReplyCopy(wrap, briefingText(payload), {
      save: !payload.artifacts?.length,
      title: payload.summary ? "Briefing" : "Saved reply",
    });
  }
  renderDeckDownloads(wrap, payload.downloads);
  return wrap;
}

function renderReceipt(payload) {
  const wrap = el("div", "receipt");
  attachNotice(wrap, payload);
  const card = el("article", "card card-receipt");
  card.append(el("h3", "", "Receipt"));
  const fields = payload.fields || [];
  for (const field of fields) {
    const row = el("div", "receipt-row");
    row.append(el("span", "receipt-label", field.label || ""));
    row.append(el("span", "receipt-value", field.value || ""));
    card.append(row);
  }
  if (payload.next_step) {
    card.append(el("p", "receipt-next", payload.next_step));
  }
  if (payload.assumptions?.length) {
    const list = el("ul", "receipt-assumptions");
    for (const item of payload.assumptions) {
      const li = el("li");
      appendRich(li, item);
      list.append(li);
    }
    card.append(list);
  }
  wrap.append(card);
  if (fields.length < 3 && payload.text) {
    wrap.append(renderMarkdown(payload.text));
  }
  if (shouldOfferNextJob(payload)) {
    const next = nextJobButton();
    if (next) wrap.append(next);
  }
  addReplyCopy(wrap, payload.text || briefingText(payload), { save: true, title: "Receipt" });
  renderDeckDownloads(wrap, payload.downloads);
  return wrap;
}

function renderQuestion(payload) {
  const wrap = el("div", "question-card");
  attachNotice(wrap, payload);
  const card = el("article", "card");
  card.append(el("h3", "", "Question"));
  card.append(renderMarkdown(payload.text || ""));
  wrap.append(card);
  addReplyCopy(wrap, payload.text || "", { save: true, title: "Question" });
  return wrap;
}

function renderCannot(payload) {
  const wrap = el("div", "cannot-card");
  attachNotice(wrap, payload);
  const card = el("article", "card");
  card.append(el("h3", "", "Can't do that"));
  const body = el("p");
  appendRich(body, payload.text || payload.why || payload.requested || "");
  card.append(body);
  const open = el("button", "reply-action", "Open task menu");
  open.type = "button";
  open.addEventListener("click", () => openTaskMenu(document.getElementById("open-tasks")));
  card.append(open);
  wrap.append(card);
  return wrap;
}

function openFirstArtifact(artifacts) {
  const item = artifacts?.find((row) => row.kind !== "pptx" && !row.url);
  if (!item) return;
  window.JamesArtifacts?.openPane(item, undefined, { instant: true });
}

function placeholderChoice(id, kicker, title, hint) {
  const button = el("button", "placeholder-choice");
  button.type = "button";
  button.id = id;
  const kickerEl = el("span", "placeholder-choice-kicker", kicker);
  const titleEl = el("span", "placeholder-choice-title", title);
  const hintEl = el("span", "placeholder-choice-hint", hint);
  button.append(kickerEl, titleEl, hintEl);
  return button;
}

function placeholderNode() {
  const node = el("div", "placeholder t-stagger is-shown");
  node.id = "placeholder";
  const img = document.createElement("img");
  img.src = "/static/james.png?v=2";
  img.alt = "";
  img.className = "placeholder-bob";
  const actions = el("div", "placeholder-actions t-stagger-line t-stagger-line--3");
  actions.append(
    placeholderChoice("open-tasks-empty", "Start here", "Choose a task", "Opens the task menu"),
    placeholderChoice("open-filters-empty", "Optional", "Set filters", "Limit by campaign and type")
  );
  node.append(
    img,
    el("h2", "t-stagger-line t-stagger-line--1", "Let’s get some work done!"),
    el("p", "t-stagger-line t-stagger-line--2", "Type below, or choose a task and set filters."),
    actions
  );
  return node;
}

function setStatus(node, label) {
  let text = node.querySelector(".status-label");
  if (!node.querySelector(".status-dots")) {
    const dots = el("span", "status-dots");
    dots.append(el("i"), el("i"), el("i"));
    const live = el("span", "status-label t-text-swap", label);
    node.replaceChildren(dots, live);
    return;
  }
  if (text) {
    if (window.JamesMotion?.swapText) window.JamesMotion.swapText(text, label);
    else text.textContent = label;
  }
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

function syncEmptyShell() {
  const library = Boolean(
    workspaceEl?.classList.contains("is-library-view") || workspaceEl?.classList.contains("is-recents-view")
  );
  const empty = !library && !canvasHasTurns() && Boolean(document.getElementById("placeholder"));
  workspaceEl?.classList.toggle("is-empty", empty);
}

function showEmptyCanvas() {
  const paint = () => {
    threadEl().replaceChildren(placeholderNode());
    renderQueryNav();
    syncEmptyShell();
  };
  if (threadEl().querySelector(".turn") && window.JamesMotion?.crossFade) {
    window.JamesMotion.crossFade(threadEl(), paint);
    return;
  }
  paint();
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
  chat.sentTaskId = sentTaskId;
  chat.sentFilterKey = sentFilterKey;
  persistChats();
}

function persistChats() {
  const payload = {
    activeChatId,
    chats: chats.slice(0, CHATS_LIMIT).map((item) => ({
      id: item.id,
      sessionId: item.sessionId || "",
      title: item.title || "Chat",
      html: item.html || "",
      sentTaskId: item.sentTaskId || "",
      sentFilterKey: item.sentFilterKey || "",
      updatedAt: item.updatedAt || 0,
      pinned: Boolean(item.pinned),
      collectionId: item.collectionId || "",
    })),
  };
  try {
    localStorage.setItem(CHATS_KEY, JSON.stringify(payload));
  } catch {
    payload.chats = payload.chats.map((item, index) =>
      index < 8 ? item : { ...item, html: "" }
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
    chats = raw.chats.filter((item) => item && item.id).map((item) => ({
      ...item,
      pinned: Boolean(item.pinned),
      collectionId: item.collectionId || "",
    }));
    // A blank saved id is a new chat the user opened on purpose. Falling back
    // to the newest thread would drop them somewhere they did not leave.
    const savedId = raw.activeChatId || "";
    activeChatId = chats.some((item) => item.id === savedId) ? savedId : "";
  } catch {
    chats = [];
    activeChatId = "";
  }
}

function syncBusy() {
  setBusy(pendingChats.has(activeChatId));
}

function stopPoll(chatId) {
  const timer = pollTimers.get(chatId);
  if (timer) window.clearTimeout(timer);
  pollTimers.delete(chatId);
}

function paintReplyNode(event, options = {}) {
  const autoOpen = Boolean(options.autoOpen);
  const storedArtifacts = persistChatArtifacts(extractReplyArtifacts(event, event.text || ""));
  const payload = storedArtifacts.length ? { ...event, artifacts: storedArtifacts } : event;
  if (event.kind === "briefing") {
    const node = renderBriefing(payload);
    if (autoOpen) openFirstArtifact(payload.artifacts);
    return node;
  }
  if (event.kind === "receipt") return renderReceipt(payload);
  if (event.kind === "question") return renderQuestion(payload);
  if (event.kind === "cannot") return renderCannot(payload);
  const wrap = renderMarkdown(event.text || "");
  if (event.notice) wrap.prepend(el("p", "sample-badge", "Sample data"));
  addReplyCopy(wrap, event.text || "", { save: true });
  renderDeckDownloads(wrap, payload.downloads);
  if (shouldOfferNextJob(event)) {
    const next = nextJobButton();
    if (next) wrap.append(next);
  }
  return wrap;
}

function paintTurnReply(turn, event) {
  if (!turn || !event) return;
  const reply = turn.querySelector(".reply");
  if (!reply) return;
  turn.querySelector(".status")?.remove();
  turn.querySelector(".caret")?.remove();
  turn.querySelector(".stopped")?.remove();
  turn.classList.remove("pending");
  const box = turn.querySelector(".reasoning");
  if (box) {
    box.dataset.streaming = "false";
    const body = box.querySelector(".reasoning-body");
    if (!body?.textContent?.trim()) box.hidden = true;
    else {
      box.dataset.done = "true";
      setReasoningOpen(box, false);
    }
  }
  reply.querySelector(".briefing")?.remove();
  reply.querySelector(".receipt")?.remove();
  reply.querySelector(".question-card")?.remove();
  reply.querySelector(".cannot-card")?.remove();
  reply.querySelector(".stream")?.remove();
  reply.querySelector(".error")?.remove();
  reply.querySelector(".md-prose")?.remove();
  if (event.kind === "error") {
    const err = el("p", "error", event.text || event.message || "Something went wrong.");
    reply.append(err);
    addRetry(reply, turn);
  } else {
    reply.append(paintReplyNode(event));
  }
  revealLatestQuery(turn);
  snapshotActive();
  renderQueryNav();
}

function applyServerRecord(chatId, record) {
  if (!record) return;
  const chat = chats.find((item) => item.id === chatId);
  const last = (record.turns || [])[record.turns.length - 1];
  if (chat) {
    if (record.session_id) chat.sessionId = record.session_id;
    if (record.title) chat.title = record.title;
  }
  if (!last) return;
  const pending = last.reply == null && last.status !== "cancelled" && last.status !== "done" && last.status !== "error";
  if (pending) pendingChats.add(chatId);
  else pendingChats.delete(chatId);
  if (chatId !== activeChatId) {
    syncBusy();
    persistChats();
    renderHistory();
    return;
  }
  let turn = threadEl().querySelector(".turn.pending:last-child") || threadEl().querySelector(".turn:last-child");
  if (!turn) {
    renderHistory();
    return;
  }
  if (last.reply) {
    if (liveChats.has(chatId)) {
      persistChats();
      renderHistory();
      return;
    }
    if (
      !turn.classList.contains("pending") &&
      turn.querySelector(".md-prose, .briefing, .receipt, .question-card, .error")
    ) {
      pendingChats.delete(chatId);
      syncBusy();
      persistChats();
      renderHistory();
      return;
    }
    paintTurnReply(turn, last.reply);
  } else if (last.status === "cancelled") {
    settleIncompleteTurn();
    snapshotActive();
  } else {
    turn.classList.add("pending");
    turn.querySelector(".stopped")?.remove();
    const status = turn.querySelector(".status");
    if (status && last.status_label) setStatus(status, last.status_label);
  }
  syncBusy();
  renderHistory();
}

async function fetchChatRecord(chatId) {
  const response = await fetch(`/api/chats/${encodeURIComponent(chatId)}`);
  if (!response.ok) return null;
  return response.json();
}

function resumePendingChat(chatId) {
  if (!chatId) return;
  stopPoll(chatId);
  let idle = 0;
  const tick = async () => {
    const record = await fetchChatRecord(chatId);
    applyServerRecord(chatId, record);
    const last = record?.turns?.[record.turns.length - 1];
    const pending = Boolean(
      last && last.reply == null && last.status !== "cancelled" && last.status !== "done" && last.status !== "error"
    );
    if (!pending) {
      pollTimers.delete(chatId);
      return;
    }
    if (record && record.running === false) idle += 1;
    else idle = 0;
    if (idle >= 4) {
      applyServerRecord(chatId, {
        ...record,
        turns: [
          ...(record.turns || []).slice(0, -1),
          {
            ...last,
            status: "error",
            reply: { kind: "error", text: "I didn't get an answer back. Try that again." },
          },
        ],
      });
      pollTimers.delete(chatId);
      pendingChats.delete(chatId);
      syncBusy();
      return;
    }
    pendingChats.add(chatId);
    if (chatId === activeChatId) syncBusy();
    pollTimers.set(chatId, window.setTimeout(tick, 800));
  };
  tick();
}

async function cancelChatRun(chatId) {
  if (!chatId) return;
  stopPoll(chatId);
  pendingChats.delete(chatId);
  try {
    await fetch(`/api/chats/${encodeURIComponent(chatId)}/cancel`, { method: "POST" });
  } catch {
    /* offline */
  }
}

function restoreActiveChat() {
  const chat = chats.find((item) => item.id === activeChatId);
  if (chat?.sessionId) sessionId = chat.sessionId;
  if (!activeCollectionId && chat?.collectionId) activeCollectionId = chat.collectionId;
  sentTaskId = chat?.sentTaskId || "";
  sentFilterKey = chat?.sentFilterKey || "";
  hideComposerSuggest();
  if (chat?.html && chat.html.includes("turn")) {
    threadEl().innerHTML = chat.html;
    hydrateTurns();
    renderQueryNav();
    scrollChat(true);
    resumePendingChat(chat.id);
    syncEmptyShell();
    return true;
  }
  if (chat?.id) resumePendingChat(chat.id);
  syncEmptyShell();
  return false;
}

function historyTitle(text) {
  const compact = text.replace(/\s+/g, " ").trim();
  return compact.length > 42 ? `${compact.slice(0, 41)}…` : compact;
}

function relativeTime(stamp) {
  const ms = Number(stamp) || 0;
  if (!ms) return "";
  const sec = Math.max(0, Math.floor((Date.now() - ms) / 1000));
  if (sec < 45) return "just now";
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 7) return `${day}d ago`;
  return new Date(ms).toLocaleDateString();
}

function touchChat(chat) {
  if (chat) chat.updatedAt = Date.now();
}

function sortChats(items) {
  return [...items].sort((a, b) => {
    const pin = Number(Boolean(b.pinned)) - Number(Boolean(a.pinned));
    if (pin) return pin;
    return (Number(b.updatedAt) || 0) - (Number(a.updatedAt) || 0);
  });
}

function loadChatListPrefs() {
  try {
    const raw = JSON.parse(localStorage.getItem(CHAT_LIST_KEY) || "{}");
    chatsCollapsed = Boolean(raw.collapsed);
    if (raw.sort === "name" || raw.sort === "activity") chatSort = raw.sort;
    if (raw.group === "collection" || raw.group === "pinned" || raw.group === "none") chatGroup = raw.group;
  } catch {
    /* private mode */
  }
}

function persistChatListPrefs() {
  try {
    localStorage.setItem(
      CHAT_LIST_KEY,
      JSON.stringify({ collapsed: chatsCollapsed, sort: chatSort, group: chatGroup })
    );
  } catch {
    /* private mode */
  }
}

function orderChats(items) {
  return [...items].sort((a, b) => {
    if (chatSort === "name") {
      return (a.title || "").localeCompare(b.title || "", undefined, { sensitivity: "base" });
    }
    return (Number(b.updatedAt) || 0) - (Number(a.updatedAt) || 0);
  });
}

function recentsDate(stamp) {
  const ms = Number(stamp) || 0;
  if (!ms) return "";
  const sec = Math.max(0, Math.floor((Date.now() - ms) / 1000));
  const day = Math.floor(sec / 86400);
  if (sec < 45) return "just now";
  if (sec < 3600) return `${Math.max(1, Math.floor(sec / 60))}m ago`;
  if (day < 1) return `${Math.max(1, Math.floor(sec / 3600))}h ago`;
  if (day === 1) return "1 day ago";
  if (day < 7) return `${day} days ago`;
  return new Date(ms).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function groupedChatSections(items) {
  const ordered = orderChats(items);
  if (chatGroup === "pinned") {
    const pinned = ordered.filter((item) => item.pinned);
    const rest = ordered.filter((item) => !item.pinned);
    return [
      pinned.length ? { title: "Pinned", items: pinned } : null,
      rest.length ? { title: pinned.length ? "Other" : "", items: rest } : null,
    ].filter(Boolean);
  }
  if (chatGroup === "collection") {
    const groups = new Map();
    for (const chat of ordered) {
      const key = chat.collectionId || "";
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(chat);
    }
    const rows = [];
    for (const folder of collections) {
      const members = groups.get(folder.id);
      if (members?.length) rows.push({ title: folder.name, items: members });
    }
    const loose = groups.get("") || [];
    if (loose.length) rows.push({ title: collections.length ? "Other chats" : "", items: loose });
    return rows.length ? rows : [{ title: "", items: ordered }];
  }
  return [{ title: "", items: ordered }];
}

function svgIcon(pathD) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", pathD);
  svg.append(path);
  return svg;
}

function historyAction(className, label, pathD) {
  const button = el("button", `history-action ${className}`);
  button.type = "button";
  button.title = label;
  button.setAttribute("aria-label", label);
  button.append(svgIcon(pathD));
  return button;
}

function appendHistoryRow(parent, chat) {
  const row = el("div", "history-row");
  row.dataset.id = chat.id;
  const button = el("button", "history-item");
  button.type = "button";
  button.title = chat.title;
  if (chat.id === activeChatId) {
    row.classList.add("is-active");
    button.classList.add("active");
    button.setAttribute("aria-current", "true");
  }
  if (chat.pinned) row.classList.add("is-pinned");
  const body = el("span", "history-item-body");
  body.append(el("span", "history-item-title", chat.title));
  const meta = [];
  if (pendingChats.has(chat.id)) meta.push("Running");
  const when = relativeTime(chat.updatedAt);
  if (when) meta.push(when);
  if (meta.length) body.append(el("span", "history-item-meta", meta.join(" · ")));
  button.append(body);
  button.addEventListener("click", () => openChat(chat.id));
  const actions = el("span", "history-actions");
  const pin = historyAction(
    `history-pin${chat.pinned ? " is-on" : ""}`,
    chat.pinned ? `Unpin ${chat.title}` : `Pin ${chat.title}`,
    "M12 17v5M9 3h6v7.8c1.2.3 2 1.4 2 2.7V15H7v-1.5c0-1.3.8-2.4 2-2.7V3z"
  );
  pin.addEventListener("click", (event) => {
    event.stopPropagation();
    togglePin(chat);
  });
  const rename = historyAction("history-move", `Rename ${chat.title}`, "M4 20h4l10-10-4-4L4 16v4z");
  rename.addEventListener("click", (event) => {
    event.stopPropagation();
    askRenameChat(chat);
  });
  const move = historyAction("history-move", `Move ${chat.title} to a collection`, "M3 7h6l2 2h10v10H3z");
  move.addEventListener("click", (event) => {
    event.stopPropagation();
    askMoveChat(chat);
  });
  const remove = el("button", "history-action history-delete", "×");
  remove.type = "button";
  remove.setAttribute("aria-label", `Delete ${chat.title}`);
  remove.title = "Delete chat";
  remove.addEventListener("click", (event) => {
    event.stopPropagation();
    askDeleteChat(chat.id, chat.title);
  });
  actions.append(pin, rename, move, remove);
  row.append(button, actions);
  parent.append(row);
}

function chatMatchesNeedle(chat, needle) {
  if (!needle) return true;
  const snippet = String(chat.html || "")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ");
  const hay = `${chat.title || ""} ${chat.preview || ""} ${snippet}`.toLowerCase();
  return hay.includes(needle);
}

function renderHistory() {
  if (!chatHistory) return;
  chatHistory.replaceChildren();
  const listed = chats;
  const pinned = sortChats(listed.filter((item) => item.pinned));
  const groupedIds = new Set(
    listed.filter((item) => item.collectionId).map((item) => item.id)
  );
  const ungrouped = sortChats(
    listed.filter((item) => !item.pinned && !item.collectionId)
  );

  const block = (title) => {
    const section = el("section", "history-block");
    if (title) section.append(el("h3", "sidebar-chats-label sidebar-library-label", title));
    chatHistory.append(section);
    return section;
  };

  const collectionBlock = block("Collections");
  const newCollection = el("button", "sidebar-new-collection");
  newCollection.type = "button";
  newCollection.id = "new-collection";
  newCollection.append(svgIcon("M12 5v14M5 12h14"), document.createTextNode("New collection"));
  newCollection.addEventListener("click", () => askCollectionPrompt("create"));
  collectionBlock.append(newCollection);
  const visibleFolders = collectionsShowAll
    ? collections
    : collections.slice(0, COLLECTION_SIDEBAR_LIMIT);
  for (const folder of visibleFolders) {
    const members = sortChats(listed.filter((item) => item.collectionId === folder.id));
    const group = el("div", "collection-group");
    const head = el("div", "collection-head");
    const toggle = el("button", "collection-toggle");
    toggle.type = "button";
    toggle.append(
      svgIcon("M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-8l-2-2H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2z"),
      el("span", "collection-toggle-name", folder.name)
    );
    toggle.title = expandedCollections.has(folder.id) ? "Hide chats" : "Show chats";
    toggle.addEventListener("click", () => {
      if (expandedCollections.has(folder.id)) expandedCollections.delete(folder.id);
      else expandedCollections.add(folder.id);
      activeCollectionId = folder.id;
      syncChatUrl();
      const open = expandedCollections.has(folder.id);
      group.classList.toggle("is-open", open);
      toggle.title = open ? "Hide chats" : "Show chats";
    });
    const add = historyAction("history-pin", `New chat in ${folder.name}`, "M12 5v14M5 12h14");
    add.addEventListener("click", (event) => {
      event.stopPropagation();
      startNewChat({ collectionId: folder.id, force: true });
    });
    const rename = historyAction("history-move", `Rename ${folder.name}`, "M4 20h4l10-10-4-4L4 16v4z");
    rename.addEventListener("click", (event) => {
      event.stopPropagation();
      askCollectionPrompt("rename", folder);
    });
    const remove = el("button", "history-action history-delete", "×");
    remove.type = "button";
    remove.setAttribute("aria-label", `Delete ${folder.name}`);
    remove.title = "Delete collection";
    remove.addEventListener("click", (event) => {
      event.stopPropagation();
      askDeleteCollection(folder);
    });
    const actions = el("span", "history-actions");
    actions.append(add, rename, remove);
    head.append(toggle, actions);
    group.append(head);
    const fold = el("div", "collection-fold");
    const inner = el("div", "collection-fold-inner collection-chats");
    if (!members.length) inner.append(el("p", "history-empty", "No chats in this collection."));
    for (const chat of orderChats(members)) appendHistoryRow(inner, chat);
    fold.append(inner);
    group.append(fold);
    if (expandedCollections.has(folder.id)) group.classList.add("is-open");
    collectionBlock.append(group);
  }
  if (collections.length > COLLECTION_SIDEBAR_LIMIT) {
    const more = el("button", "collection-all");
    more.type = "button";
    more.append(
      svgIcon("M6 12h.01M12 12h.01M18 12h.01"),
      document.createTextNode(collectionsShowAll ? "Show less" : "All collections")
    );
    more.addEventListener("click", () => {
      collectionsShowAll = !collectionsShowAll;
      renderHistory();
      if (collectionsShowAll) {
        chatHistory?.querySelector(".collection-group:last-of-type")?.scrollIntoView({
          block: "nearest",
        });
      }
    });
    collectionBlock.append(more);
  }

  if (pinned.length) {
    const pinnedBlock = block("Pinned");
    const list = el("div", "history-group");
    list.setAttribute("aria-label", "Pinned chats");
    for (const chat of orderChats(pinned)) appendHistoryRow(list, chat);
    pinnedBlock.append(list);
  }

  const chatsBlock = el("section", "history-block");
  chatHistory.append(chatsBlock);
  const head = el("div", "chats-head");
  const toggle = el("button", "chats-head-toggle");
  toggle.type = "button";
  toggle.setAttribute("aria-expanded", chatsCollapsed ? "false" : "true");
  toggle.append(el("span", "", "Chats"));
  toggle.addEventListener("click", () => {
    chatsCollapsed = !chatsCollapsed;
    persistChatListPrefs();
    chatsBlock.classList.toggle("is-collapsed", chatsCollapsed);
    chatsBlock.classList.toggle("is-open", !chatsCollapsed);
    toggle.setAttribute("aria-expanded", chatsCollapsed ? "false" : "true");
  });
  const tools = el("div", "chats-head-tools");
  const viewAll = historyAction("chats-tool", "View all chats", "M7 17L17 7M10 7h7v7");
  viewAll.id = "open-chat-recents";
  viewAll.addEventListener("click", (event) => {
    event.stopPropagation();
    showRecents();
  });
  const sortBtn = historyAction("chats-tool", "Group and sort chats", "M4 6h16M7 12h10M10 18h4");
  sortBtn.id = "open-chat-sort";
  sortBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    openChatSortMenu(sortBtn);
  });
  tools.append(viewAll, sortBtn);
  head.append(toggle, tools);
  chatsBlock.append(head);
  const fold = el("div", "collection-fold");
  const inner = el("div", "collection-fold-inner");
  if (!ungrouped.length && !pinned.length && !groupedIds.size) {
    inner.append(el("p", "history-empty", "No chats yet."));
  } else if (!ungrouped.length) {
    inner.append(el("p", "history-empty", "No other chats."));
  } else {
    const list = el("div", "history-group");
    for (const chat of orderChats(ungrouped)) appendHistoryRow(list, chat);
    inner.append(list);
  }
  fold.append(inner);
  chatsBlock.append(fold);
  if (chatsCollapsed) chatsBlock.classList.add("is-collapsed");
  else chatsBlock.classList.add("is-open");
  window.JamesMotion?.enterSeen?.(chatHistory, chatHistory.querySelectorAll(".history-row"));
}

function isRecentsOpen() {
  return Boolean(chatRecents && !chatRecents.hidden);
}

function hideRecents(options = {}) {
  if (!chatRecents || chatRecents.hidden) {
    workspaceEl?.classList.remove("is-recents-view");
    return;
  }
  const instant = Boolean(options.instant);
  const hide = () => {
    chatRecents.classList.remove("is-open", "is-closing");
    chatRecents.hidden = true;
    workspaceEl?.classList.remove("is-recents-view");
    recentsQuery = "";
    recentsSelecting = false;
    recentsPicked.clear();
    if (chatRecentsSearch) {
      chatRecentsSearch.value = "";
      chatRecentsSearch.hidden = true;
    }
    chatRecentsSearchWrap?.classList.remove("is-open");
    syncRecentsChrome();
    syncEmptyShell();
  };
  closeDialogById("chat-sort-dialog");
  if (instant || !window.JamesMotion) hide();
  else window.JamesMotion.closeSurface(chatRecents, hide);
}

function showRecents() {
  if (!chatRecents) return;
  window.JamesArtifacts?.hideLibrary();
  closeDialogById("chat-sort-dialog");
  chatRecents.hidden = false;
  workspaceEl?.classList.add("is-recents-view");
  renderRecents();
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      if (window.JamesMotion) window.JamesMotion.openSurface(chatRecents);
      else chatRecents.classList.add("is-open");
    });
  });
}

function syncRecentsChrome() {
  if (chatRecentsSelect) {
    chatRecentsSelect.textContent = recentsSelecting ? "Cancel" : "Select";
  }
  if (chatRecentsDelete) {
    chatRecentsDelete.hidden = !recentsSelecting || recentsPicked.size === 0;
    chatRecentsDelete.textContent = recentsPicked.size > 1 ? `Delete ${recentsPicked.size}` : "Delete";
  }
  chatRecents?.classList.toggle("is-selecting", recentsSelecting);
}

function appendRecentsRow(parent, chat) {
  const row = el("button", "chat-recents-row");
  row.type = "button";
  row.dataset.id = chat.id;
  if (chat.id === activeChatId && !recentsSelecting) row.classList.add("is-active");
  if (recentsPicked.has(chat.id)) row.classList.add("is-picked");
  if (recentsSelecting) {
    const mark = el("span", "chat-recents-check");
    mark.setAttribute("aria-hidden", "true");
    row.append(mark);
  }
  row.append(el("span", "chat-recents-name", chat.title || "Untitled"));
  const meta = el("span", "chat-recents-meta");
  if (chat.pinned) meta.append(el("span", "chat-recents-badge", "Pinned"));
  const when = recentsDate(chat.updatedAt);
  if (when) meta.append(el("span", "chat-recents-when", when));
  row.append(meta);
  row.addEventListener("click", () => {
    if (recentsSelecting) {
      if (recentsPicked.has(chat.id)) recentsPicked.delete(chat.id);
      else recentsPicked.add(chat.id);
      renderRecents();
      return;
    }
    hideRecents();
    openChat(chat.id);
  });
  parent.append(row);
}

function renderRecents() {
  if (!chatRecentsBody) return;
  chatRecentsBody.replaceChildren();
  const needle = recentsQuery.trim().toLowerCase();
  const matches = chats.filter((chat) => chatMatchesNeedle(chat, needle));
  if (!matches.length) {
    const empty = el("p", "history-empty", needle ? "No chats match that search." : "No chats yet.");
    chatRecentsBody.append(empty);
    window.JamesMotion?.enter?.(empty, "t-row");
    syncRecentsChrome();
    return;
  }
  for (const section of groupedChatSections(matches)) {
    if (section.title) chatRecentsBody.append(el("h2", "chat-recents-group", section.title));
    const list = el("div", "chat-recents-list");
    for (const chat of section.items) appendRecentsRow(list, chat);
    chatRecentsBody.append(list);
  }
  window.JamesMotion?.enterSeen?.(chatRecentsBody, chatRecentsBody.querySelectorAll(".chat-recents-row"));
  syncRecentsChrome();
}

function renderChatSortMenu() {
  if (!chatSortMenu) return;
  chatSortMenu.replaceChildren();
  const addOption = (label, on, run) => {
    const button = el("button", `chat-sort-item${on ? " is-on" : ""}`, label);
    button.type = "button";
    button.addEventListener("click", run);
    chatSortMenu.append(button);
  };
  if (chatSortPane === "group") {
    addOption("Back", false, () => {
      chatSortPane = "";
      renderChatSortMenu();
    });
    for (const [id, label] of Object.entries(GROUP_LABELS)) {
      addOption(label, chatGroup === id, () => {
        chatGroup = id;
        persistChatListPrefs();
        chatSortPane = "";
        closeDialogById("chat-sort-dialog");
        renderHistory();
        if (isRecentsOpen()) renderRecents();
      });
    }
    return;
  }
  if (chatSortPane === "sort") {
    addOption("Back", false, () => {
      chatSortPane = "";
      renderChatSortMenu();
    });
    for (const [id, label] of Object.entries(SORT_LABELS)) {
      addOption(label, chatSort === id, () => {
        chatSort = id;
        persistChatListPrefs();
        chatSortPane = "";
        closeDialogById("chat-sort-dialog");
        renderHistory();
        if (isRecentsOpen()) renderRecents();
      });
    }
    return;
  }
  const group = el("button", "chat-sort-row");
  group.type = "button";
  group.append(el("span", "", "Group by"), el("span", "chat-sort-value", GROUP_LABELS[chatGroup] || "None"));
  group.addEventListener("click", () => {
    chatSortPane = "group";
    renderChatSortMenu();
  });
  const sort = el("button", "chat-sort-row");
  sort.type = "button";
  sort.append(el("span", "", "Sort by"), el("span", "chat-sort-value", SORT_LABELS[chatSort] || "Last activity"));
  sort.addEventListener("click", () => {
    chatSortPane = "sort";
    renderChatSortMenu();
  });
  chatSortMenu.append(group, sort);
}

function openChatSortMenu(anchor) {
  chatSortPane = "";
  renderChatSortMenu();
  openDialog(chatSortDialog, anchor);
}

async function patchChat(chatId, body) {
  const response = await fetch(`/api/chats/${encodeURIComponent(chatId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) return null;
  return response.json();
}

async function togglePin(chat) {
  chat.pinned = !chat.pinned;
  renderHistory();
  persistChats();
  await patchChat(chat.id, { pinned: chat.pinned });
}

async function setChatCollection(chat, collectionId) {
  chat.collectionId = collectionId || "";
  if (collectionId) activeCollectionId = collectionId;
  renderHistory();
  persistChats();
  syncChatUrl();
  await patchChat(chat.id, { collection_id: collectionId || null });
}

function askMoveChat(chat) {
  moveChatId = chat.id;
  if (!moveCollectionList) return;
  moveCollectionList.replaceChildren();
  if (chat.collectionId) {
    const none = el("button", "move-collection-item", "Remove from collection");
    none.type = "button";
    none.addEventListener("click", () => {
      closeDialogs();
      setChatCollection(chat, "");
    });
    moveCollectionList.append(none);
  }
  for (const folder of collections) {
    const button = el("button", "move-collection-item", folder.name);
    button.type = "button";
    if (folder.id === chat.collectionId) button.classList.add("is-current");
    button.addEventListener("click", () => {
      closeDialogs();
      setChatCollection(chat, folder.id);
    });
    moveCollectionList.append(button);
  }
  const create = el("button", "move-collection-item", "New collection…");
  create.type = "button";
  create.addEventListener("click", () => {
    closeDialogs();
    askCollectionPrompt("create", null, chat.id);
  });
  moveCollectionList.append(create);
  openDialog(moveCollectionDialog);
}

function askCollectionPrompt(mode, folder, moveAfterId) {
  collectionPromptMode = mode;
  renameCollectionId = folder?.id || "";
  renameChatId = "";
  if (moveAfterId) moveChatId = moveAfterId;
  if (collectionPromptTitle) {
    collectionPromptTitle.textContent = mode === "rename" ? "Rename collection" : "New collection";
  }
  if (collectionPromptInput) {
    collectionPromptInput.value = folder?.name || "";
    collectionPromptInput.placeholder = "e.g. Q4 product launches";
  }
  openDialog(collectionPromptDialog);
  collectionPromptInput?.focus();
  collectionPromptInput?.select();
}

function askRenameChat(chat) {
  collectionPromptMode = "rename-chat";
  renameChatId = chat.id;
  renameCollectionId = "";
  if (collectionPromptTitle) collectionPromptTitle.textContent = "Rename chat";
  if (collectionPromptInput) {
    collectionPromptInput.value = chat.title || "";
    collectionPromptInput.placeholder = "e.g. Q4 pipeline review";
  }
  openDialog(collectionPromptDialog);
  collectionPromptInput?.focus();
  collectionPromptInput?.select();
}

function askDeleteCollection(folder) {
  pendingDeleteCollectionId = folder.id;
  pendingDeleteChatId = "";
  if (deleteDialogTitle) deleteDialogTitle.textContent = "Delete collection";
  if (deleteDialogCopy) {
    deleteDialogCopy.textContent = `Delete “${folder.name}”? Chats stay in the list, ungrouped.`;
  }
  openDialog(deleteDialog);
}

let collectionSaveBusy = false;

async function submitCollectionPrompt() {
  const name = collectionPromptInput?.value.trim() || "";
  if (!name) {
    collectionPromptInput?.focus();
    return;
  }
  if (collectionSaveBusy) return;
  collectionSaveBusy = true;
  const mode = collectionPromptMode;
  const renameId = renameCollectionId;
  const chatId = renameChatId;
  const movingId = moveChatId;
  try {
    if (mode === "rename-chat" && chatId) {
      const chat = chats.find((item) => item.id === chatId);
      if (!chat) throw new Error("rename-chat");
      const record = await patchChat(chatId, { title: name.slice(0, 80) });
      if (!record) throw new Error("rename-chat");
      chat.title = record.title || name.slice(0, 80);
      closeDialogById("collection-prompt-dialog");
      renderHistory();
      persistChats();
      if (isRecentsOpen()) renderRecents();
      return;
    }
    if (mode === "rename" && renameId) {
      const response = await fetch(`/api/collections/${encodeURIComponent(renameId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      if (!response.ok) throw new Error("rename");
      const row = await response.json();
      collections = collections.map((item) => (item.id === row.id ? row : item));
      closeDialogById("collection-prompt-dialog");
      renderHistory();
      return;
    }
    const response = await fetch("/api/collections", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (!response.ok) throw new Error("create");
    const row = await response.json();
    collections.unshift(row);
    activeCollectionId = row.id;
    closeDialogById("collection-prompt-dialog");
    const moving = chats.find((item) => item.id === movingId);
    if (moving) await setChatCollection(moving, row.id);
    else {
      renderHistory();
      persistChats();
      syncChatUrl();
    }
  } catch {
    const failed =
      mode === "rename-chat"
        ? "Could not rename that chat. Try again."
        : "Could not save that collection. Try again.";
    window.JamesMotion?.showToast(failed);
    collectionPromptInput?.focus();
  } finally {
    collectionSaveBusy = false;
  }
}

async function deleteCollection(collectionId) {
  const response = await fetch(`/api/collections/${encodeURIComponent(collectionId)}`, {
    method: "DELETE",
  });
  if (!response.ok) return;
  collections = collections.filter((item) => item.id !== collectionId);
  for (const chat of chats) {
    if (chat.collectionId === collectionId) chat.collectionId = "";
  }
  if (activeCollectionId === collectionId) activeCollectionId = "";
  renderHistory();
  persistChats();
  syncChatUrl();
}

async function loadLibrary() {
  try {
    const [chatPayload, folderPayload] = await Promise.all([
      fetch("/api/chats").then((res) => res.json()),
      fetch("/api/collections").then((res) => res.json()),
    ]);
    if (Array.isArray(folderPayload?.collections)) collections = folderPayload.collections;
    if (Array.isArray(chatPayload?.chats)) {
      const remote = new Map(chatPayload.chats.map((row) => [row.id, row]));
      chats = chats.map((item) => {
        const row = remote.get(item.id);
        if (!row) return item;
        return {
          ...item,
          sessionId: row.session_id || item.sessionId || "",
          title: row.title || item.title || "Chat",
          updatedAt: Date.parse(row.updated_at || "") || item.updatedAt || 0,
          pinned: Boolean(row.pinned),
          collectionId: row.collection_id || "",
        };
      });
    }
  } catch {
    /* offline */
  }
}

function chatHasLocalThread(item) {
  return Boolean(item?.html && String(item.html).includes("turn"));
}

function keepSidebarChat(item) {
  if (!item?.id) return false;
  if (item.id === activeChatId) return true;
  if (item.pinned || item.collectionId) return true;
  if (pendingChats.has(item.id)) return true;
  return chatHasLocalThread(item);
}

function forgetImportedChats() {
  const next = chats.filter(keepSidebarChat);
  if (next.length === chats.length) return;
  chats = next;
  if (activeChatId && !chats.some((item) => item.id === activeChatId)) {
    activeChatId = chats[0]?.id || "";
  }
  persistChats();
}

async function deleteChat(chatId) {
  const index = chats.findIndex((item) => item.id === chatId);
  if (index < 0) return;
  const wasActive = chatId === activeChatId;
  stopPoll(chatId);
  pendingChats.delete(chatId);
  if (wasActive) detachInFlight();
  fetch(`/api/chats/${encodeURIComponent(chatId)}`, { method: "DELETE" }).catch(() => {});
  chats.splice(index, 1);
  if (!wasActive) {
    renderHistory();
    persistChats();
    return;
  }
  const next = chats[0];
  if (next) {
    activeChatId = "";
    openChat(next.id);
    return;
  }
  await createSession();
  activeChatId = "";
  sentTaskId = "";
  sentFilterKey = "";
  hideComposerSuggest();
  clearAllSelections();
  prompt.value = "";
  resizePrompt();
  syncComposerHint();
  showEmptyCanvas();
  renderHistory();
  persistChats();
  prompt.focus();
}

function ensureActiveChat(title) {
  if (activeChatId) {
    const existing = chats.find((item) => item.id === activeChatId);
    if (existing) {
      touchChat(existing);
      return existing;
    }
  }
  const chat = {
    id: crypto.randomUUID(),
    sessionId,
    title: historyTitle(title),
    html: "",
    updatedAt: Date.now(),
    pinned: false,
    collectionId: activeCollectionId || "",
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
  const box = last.querySelector(".reasoning");
  if (box && inFlight) {
    box.dataset.done = "true";
    box.dataset.streaming = "false";
  }
  const think = last.querySelector(".t-think");
  if (think && inFlight) window.JamesMotion?.stopThinking(think, "Stopped");
  if (inFlight && !last.querySelector(".stopped")) {
    last.append(el("p", "error stopped", "Stopped. James cancelled this reply."));
  }
}

function detachInFlight() {
  abortController?.abort();
  abortController = null;
  requestGen += 1;
  syncBusy();
}

function abandonInFlight() {
  detachInFlight();
}

function openChat(chatId) {
  window.JamesArtifacts?.hideLibrary();
  hideRecents();
  const chat = chats.find((item) => item.id === chatId);
  if (!chat || chat.id === activeChatId) return;
  detachInFlight();
  snapshotActive();
  clearAllSelections();
  prompt.value = "";
  resizePrompt();
  syncComposerHint();
  sentTaskId = chat.sentTaskId || "";
  sentFilterKey = chat.sentFilterKey || "";
  hideComposerSuggest();
  activeChatId = chat.id;
  activeCollectionId = chat.collectionId || "";
  sessionId = chat.sessionId;
  const paint = () => {
    if (chat.html && chat.html.includes("turn")) {
      threadEl().innerHTML = chat.html;
      hydrateTurns();
    } else showEmptyCanvas();
  };
  if (window.JamesMotion?.crossFade) window.JamesMotion.crossFade(threadEl(), paint);
  else paint();
  syncEmptyShell();
  renderHistory();
  persistChats();
  syncChatUrl();
  renderQueryNav();
  scrollChat(true);
  prompt.focus();
  closeSidebarOnNarrow();
  resumePendingChat(chat.id);
}

window.JamesChat = {
  openChat,
  hideRecents,
  hasChat(id) {
    return Boolean(id && chats.some((item) => item.id === id));
  },
  renderPreview: renderArtifactPreview,
};
window.JamesArtifacts?.resyncPane?.();

async function createSession() {
  const session = await fetch("/api/session", { method: "POST" }).then((res) => res.json());
  sessionId = session.session_id;
  return sessionId;
}

async function startNewChat(options = {}) {
  const keepDraft = Boolean(options.keepDraft);
  if (options.collectionId !== undefined) activeCollectionId = options.collectionId || "";
  detachInFlight();
  snapshotActive();
  const blank =
    !keepDraft &&
    !options.force &&
    !canvasHasTurns() &&
    !activeChatId &&
    !hasSelections() &&
    !prompt.value.trim() &&
    !attachments.length;
  if (blank) {
    prompt.focus();
    return;
  }
  await createSession();
  activeChatId = "";
  sentTaskId = "";
  sentFilterKey = "";
  hideComposerSuggest();
  if (!keepDraft) {
    clearAllSelections();
    prompt.value = "";
    resizePrompt();
    clearAttachments();
  }
  syncComposerHint();
  showEmptyCanvas();
  renderHistory();
  persistChats();
  syncChatUrl();
  if (keepDraft) renderSelection();
  prompt.focus();
}

function renderQueryNav() {
  if (!queryNav) return;
  const turns = [...canvas.querySelectorAll(".turn")];
  const keep = new Set(turns.map((turn) => turn.id));
  for (const mark of [...queryNav.querySelectorAll(".query-mark")]) {
    if (!keep.has(mark.dataset.turn)) {
      if (window.JamesMotion?.leave) window.JamesMotion.leave(mark, () => mark.remove());
      else mark.remove();
    }
  }
  turns.forEach((turn, index) => {
    if (!turn.id) turn.id = `turn-${index + 1}`;
    let mark = queryNav.querySelector(`[data-turn="${CSS.escape(turn.id)}"]`);
    if (!mark) {
      mark = el("button", "query-mark");
      mark.type = "button";
      mark.dataset.turn = turn.id;
      queryNav.append(mark);
      window.JamesMotion?.enter?.(mark, "t-row");
    }
    const preview = turn.querySelector(".bubble.user")?.textContent || `Query ${index + 1}`;
    const label = preview.replace(/\s+/g, " ").trim().slice(0, 80);
    mark.dataset.preview = label;
    mark.setAttribute("aria-label", `Jump to query ${index + 1}: ${label}`);
    mark.onclick = () => {
      if (!canvas) return;
      stickToBottom = false;
      const query = turn.querySelector(".turn-head") || turn;
      const offset =
        query.getBoundingClientRect().top - canvas.getBoundingClientRect().top;
      const top = canvas.scrollTop + offset - 12;
      if (typeof canvas.scrollTo === "function") {
        canvas.scrollTo({ top, behavior: "smooth" });
      } else {
        canvas.scrollTop = top;
      }
      syncScrollButton();
    };
  });
  const show = turns.length > 0;
  if (show) {
    queryNav.hidden = false;
    requestAnimationFrame(() => queryNav.classList.add("is-visible"));
  } else {
    queryNav.classList.remove("is-visible");
    const wait = window.JamesMotion?.reducedMotion?.() ? 0 : 160;
    window.setTimeout(() => {
      if (!queryNav.querySelector(".query-mark")) queryNav.hidden = true;
    }, wait);
  }
  highlightQueryNav();
}

function highlightQueryNav() {
  const turns = [...canvas.querySelectorAll(".turn")];
  const marks = [...queryNav.querySelectorAll(".query-mark:not(.is-out)")];
  if (!turns.length || !marks.length) return;
  const target = canvas.getBoundingClientRect().top + canvas.clientHeight * 0.28;
  let active = 0;
  turns.forEach((turn, index) => {
    if (turn.getBoundingClientRect().top <= target) active = index;
  });
  marks.forEach((mark, index) => mark.classList.toggle("active", index === active));
}

function hydrateTurns() {
  window.JamesArtifacts?.refreshChatChips?.(threadEl());
  for (const button of threadEl().querySelectorAll(".turn-delete")) button.remove();
  // Finished turns stay folded. A pending turn is still live on the server.
  for (const box of threadEl().querySelectorAll(".turn:not(.pending) .reasoning")) {
    box.dataset.streaming = "false";
    const label = box.querySelector(".t-think-text") || box.querySelector(".reasoning-trigger-label");
    if (label?.textContent?.startsWith("Thought for")) box.dataset.done = "true";
    setReasoningOpen(box, false);
  }
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

function dismissPlaceholder() {
  workspaceEl?.classList.remove("is-empty");
  const placeholder = document.getElementById("placeholder");
  if (!placeholder) return;
  if (window.JamesMotion?.reducedMotion()) {
    placeholder.remove();
    return;
  }
  placeholder.classList.add("t-stagger", "is-hiding");
  placeholder.classList.remove("is-shown");
  window.setTimeout(() => placeholder.remove(), 220);
}

function settleFirstQuery(composer, bubble, from) {
  const reduced = window.JamesMotion?.reducedMotion?.();
  workspaceEl?.classList.remove("is-empty");
  workspaceEl?.classList.add("is-leaving-empty");
  const placeholder = document.getElementById("placeholder");
  if (placeholder) {
    placeholder.classList.add("t-stagger", "is-hiding");
    placeholder.classList.remove("is-shown");
  }
  const ease = "cubic-bezier(0.22, 1, 0.36, 1)";
  const dur = window.JamesMotion?.tokenMs("--duration-fast", 250) || 250;
  if (!reduced && composer && from) {
    const composerTo = composer.getBoundingClientRect();
    const cDy = from.composerTop - composerTo.top;
    if (Math.abs(cDy) > 2) {
      composer.style.transition = "none";
      composer.style.transform = `translateY(${cDy}px)`;
    }
    if (bubble) {
      const bubbleTo = bubble.getBoundingClientRect();
      const bDy = from.bubbleTop - bubbleTo.top;
      if (Math.abs(bDy) > 2) {
        bubble.style.transition = "none";
        bubble.style.transform = `translateY(${bDy}px)`;
      }
    }
    void composer.offsetWidth;
    requestAnimationFrame(() => {
      composer.style.transition = `transform ${dur}ms ${ease}`;
      composer.style.transform = "none";
      if (bubble) {
        bubble.style.transition = `transform ${dur}ms ${ease}`;
        bubble.style.transform = "none";
      }
    });
  }
  window.setTimeout(() => {
    placeholder?.remove();
    workspaceEl?.classList.remove("is-leaving-empty");
    if (composer) {
      composer.style.transition = "";
      composer.style.transform = "";
    }
    if (bubble) {
      bubble.style.transition = "";
      bubble.style.transform = "";
    }
  }, reduced ? 0 : dur + 40);
}

function appendTurn(userText) {
  const first = Boolean(workspaceEl?.classList.contains("is-empty"));
  const composer = document.querySelector(".composer");
  const turn = el("section", "turn pending t-stagger");
  turn.id = `turn-${crypto.randomUUID()}`;
  const userBubble = el("div", "bubble user t-stagger-line t-stagger-line--1", userText);
  const head = el("div", "turn-head");
  head.append(userBubble);
  const reasoning = el("div", "reasoning is-open");
  reasoning.hidden = !showReasoning;
  reasoning.dataset.open = "true";
  reasoning.dataset.streaming = "true";
  const trigger = el("button", "reasoning-trigger");
  trigger.type = "button";
  const triggerLabel = el("span", "t-think reasoning-trigger-label");
  triggerLabel.setAttribute("role", "status");
  const sizer = el("span", "t-think-sizer", "James is thinking…");
  sizer.setAttribute("aria-hidden", "true");
  const thinkText = el("span", "t-think-text", "Thinking");
  thinkText.setAttribute("data-text", "Thinking");
  triggerLabel.append(sizer, thinkText);
  const chevron = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  chevron.setAttribute("viewBox", "0 0 24 24");
  chevron.setAttribute("aria-hidden", "true");
  chevron.classList.add("reasoning-chevron");
  const chevronPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
  chevronPath.setAttribute("d", "M6 9l6 6 6-6");
  chevron.append(chevronPath);
  trigger.append(chevron, triggerLabel);
  const reasoningShell = el("div", "reasoning-shell");
  const reasoningBody = el("div", "reasoning-body t-reason");
  const reasonText = el("div", "t-reason-text");
  reasoningBody.append(reasonText);
  reasoningShell.append(reasoningBody);
  reasoning.append(trigger, reasoningShell);
  window.JamesMotion?.startThinking(triggerLabel, "Thinking");
  const status = el("p", "status");
  setStatus(status, "James is working…");
  const reply = el("div", "reply");
  const assistant = el("div", "turn-assistant");
  assistant.append(reasoning, status, reply);
  turn.append(head, assistant);
  threadEl().append(turn);
  if (first) {
    turn.classList.add("is-shown");
    const from = {
      composerTop: composer?.getBoundingClientRect().top || 0,
      bubbleTop: userBubble.getBoundingClientRect().top,
    };
    settleFirstQuery(composer, userBubble, from);
  } else {
    dismissPlaceholder();
    requestAnimationFrame(() => {
      requestAnimationFrame(() => turn.classList.add("is-shown"));
    });
  }
  revealLatestQuery(turn);
  ensureActiveChat(userText);
  snapshotActive();
  renderQueryNav();
  return { userBubble, status, reply, turn, reasoning, reasoningBody, triggerLabel };
}

function setBusy(busy) {
  const swap = document.getElementById("send-swap");
  if (swap) swap.dataset.state = busy ? "b" : "a";
  send.disabled = busy;
  send.hidden = false;
  stop.hidden = false;
  stop.disabled = !busy;
  attachBtn.disabled = busy;
  syncComposerHint();
}

function clipSuggestLabel(text) {
  const compact = String(text || "").replace(/\s+/g, " ").trim();
  return compact.length > 48 ? `${compact.slice(0, 47)}…` : compact;
}

function filterKey() {
  return JSON.stringify(currentFilters());
}

function hideComposerSuggest() {
  if (!composerSuggest) return;
  suggestKind = "";
  if (composerSuggest.hidden) return;
  const hide = (node) => {
    node.hidden = true;
    node.classList.remove("is-open", "is-closing");
  };
  if (window.JamesMotion?.closeSurface) window.JamesMotion.closeSurface(composerSuggest, hide);
  else hide(composerSuggest);
}

function showComposerSuggest(kind, copy) {
  if (!composerSuggest || !composerSuggestCopy) return;
  suggestKind = kind;
  composerSuggestCopy.textContent = copy;
  if (composerSuggestPrimary) composerSuggestPrimary.textContent = "Start new chat";
  if (composerSuggestSecondary) composerSuggestSecondary.textContent = "Stay here";
  composerSuggest.hidden = false;
  requestAnimationFrame(() => {
    if (window.JamesMotion?.openSurface) window.JamesMotion.openSurface(composerSuggest);
    else composerSuggest.classList.add("is-open");
  });
}

function shouldSuggestNewChat(nextTaskId) {
  if (!canvasHasTurns() || !nextTaskId) return false;
  if (sentTaskId && sentTaskId === nextTaskId) return false;
  if (sentTaskId && findTask(sentTaskId)?.next_task === nextTaskId) return false;
  return true;
}

function offerTaskSwitch(nextTaskId) {
  if (!shouldSuggestNewChat(nextTaskId)) {
    if (suggestKind === "task") hideComposerSuggest();
    return;
  }
  const nextLabel = clipSuggestLabel(findTask(nextTaskId)?.label || "this job");
  const prev = sentTaskId ? findTask(sentTaskId) : null;
  const copy = prev
    ? `This chat is about ${clipSuggestLabel(prev.label)}. Start a new chat for ${nextLabel}?`
    : `This chat already has a reply. Start a new chat for ${nextLabel}?`;
  showComposerSuggest("task", copy);
}

function offerFilterRefresh() {
  if (suggestKind === "task") return;
  if (!canvasHasTurns() || !activeTask) {
    if (suggestKind === "filters") hideComposerSuggest();
    return;
  }
  if (sentTaskId && sentTaskId !== activeTask) return;
  if (!sentFilterKey || filterKey() === sentFilterKey) {
    if (suggestKind === "filters") hideComposerSuggest();
    return;
  }
  showComposerSuggest(
    "filters",
    "Draft updated for the new filters. Send to refresh, or start a new chat to keep the last briefing."
  );
}

function bootComposerSuggest() {
  composerSuggestPrimary?.addEventListener("click", () => {
    startNewChat({ keepDraft: true });
  });
  composerSuggestSecondary?.addEventListener("click", () => hideComposerSuggest());
  composerSuggestDismiss?.addEventListener("click", () => hideComposerSuggest());
}

function scopeHintLine() {
  const bits = [];
  const task = activeTask ? findTask(activeTask) : null;
  if (task) bits.push(task.label);
  if (launchGeo) bits.push(launchGeo);
  if (launchStages) bits.push(launchStages);
  if (launchSizes) bits.push(launchSizes);
  if (launchWindows) bits.push(launchWindows);
  const campaign = document.querySelector(
    '#filters-dialog input[name="campaign"]:checked:not(:disabled)'
  );
  if (campaign) {
    const row = campaign.closest(".check");
    bits.push((row?.textContent || campaign.value).replace(/\s+/g, " ").trim());
  }
  const type = document.querySelector(
    '#filters-dialog input[name="campaign_type"]:checked:not(:disabled)'
  );
  if (type && !launchStages) {
    const row = type.closest(".check");
    bits.push((row?.textContent || type.value).replace(/\s+/g, " ").trim());
  }
  return bits.filter(Boolean).join(" · ");
}

function syncComposerHint() {
  if (!composerHint) return;
  const empty = Boolean(workspaceEl?.classList.contains("is-empty"));
  const line = scopeHintLine();
  if (line) composerHint.textContent = line;
  else composerHint.textContent = "Pick a task, edit if you want, then send.";
  const show = Boolean(line) || (!empty && !prompt.value.trim() && !send.disabled && !attachments.length);
  composerHint.hidden = !show;
  composerHint.classList.toggle("is-out", !show);
}

function selectTask(taskId) {
  if (activeTask === taskId) {
    clearTaskSelection();
    prompt.value = "";
    resizePrompt();
    prompt.focus();
    hideComposerSuggest();
    return;
  }
  const switching = shouldSuggestNewChat(taskId);
  activeTask = taskId;
  lastTaskId = taskId;
  syncTaskButtons();
  syncFilterAvailability();
  fillComposer(taskId);
  renderSelection();
  closeDialogs();
  closeSidebarOnNarrow();
  if (switching) offerTaskSwitch(taskId);
  else if (suggestKind === "task") hideComposerSuggest();
}

function renderAttachChips() {
  if (!attachChips) return;
  const keep = new Set(attachments.map((item) => item.filename));
  for (const chip of [...attachChips.children]) {
    if (!keep.has(chip.dataset.filename)) {
      if (window.JamesMotion?.leave) window.JamesMotion.leave(chip, () => chip.remove());
      else chip.remove();
    }
  }
  for (const item of attachments) {
    if (attachChips.querySelector(`[data-filename="${CSS.escape(item.filename)}"]`)) continue;
    const chip = el("div", "attach-chip");
    chip.dataset.filename = item.filename;
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
    window.JamesMotion?.enter?.(chip);
  }
  attachChips.hidden = !attachments.length && !attachChips.querySelector(".attach-chip:not(.is-out)");
  syncComposerHint();
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
          console.log("[bob.sse]", parsed.type, parsed);
        }
        onEvent(parsed);
      }
    }
  } finally {
    signal?.removeEventListener("abort", onAbort);
  }
}

async function askJames({ text }) {
  abortController?.abort();
  const gen = ++requestGen;
  abortController = new AbortController();
  const { signal } = abortController;
  settleIncompleteTurn();
  const filters = currentFilters();
  const files = attachments.map((item) => ({ ...item }));
  sentTaskId = activeTask || sentTaskId;
  sentFilterKey = filterKey();
  if (sentTaskId) rememberLastJob(sentTaskId);
  hideComposerSuggest();
  const preview = files.length
    ? `${text}\n\nAttached: ${files.map((item) => item.filename).join(", ")}`
    : text;
  const { userBubble, status, reply, turn, reasoning, reasoningBody, triggerLabel } =
    appendTurn(preview);
  turn.dataset.retryText = text;
  let reasoningText = "";
  let reasoningOpened = false;
  const thinkingStart = Date.now();
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
    const reasonHost = reasoningBody.querySelector(".t-reason-text") || reasoningBody;
    reasonHost.replaceChildren();
    if (reasoningText.trim()) {
      const seen = new Set();
      for (const para of stripped.split(/\n{2,}/)) {
        const line = para.trim();
        const key = line.replace(/\s+/g, " ").toLowerCase();
        if (!line || seen.has(key)) continue;
        seen.add(key);
        reasonHost.append(
          el("p", isTitle(line) ? "reasoning-title" : "", line)
        );
      }
    }
    window.JamesMotion?.followReasoning(reasoningBody);
    reasoning.hidden = false;
    reasoning.dataset.streaming = "true";
    // Opened once, then left alone: the thinking arrives in small pieces and
    // reopening on each one would fight anyone who closed the panel.
    if (!reasoningOpened) {
      reasoningOpened = true;
      setReasoningOpen(reasoning, true);
    }
    // Follow the newest line, the way the thinking reads while it is live.
    reasoningBody.scrollTop = reasoningBody.scrollHeight;
    if (triggerLabel && reasoning?.dataset.done !== "true") {
      window.JamesMotion?.setThinkLine(triggerLabel, "Thinking", { shimmer: true });
    }
  };
  const finishReasoning = () => {
    if (!reasoning) return;
    // Settling twice would close a panel the reader had just opened, and the
    // reply lands as a run of deltas followed by the reply itself.
    if (reasoning.dataset.done === "true") return;
    const hasContent = Boolean(reasoningText.trim());
    reasoning.dataset.streaming = "false";
    if (!hasContent) {
      reasoning.hidden = true;
      return;
    }
    reasoning.hidden = false;
    // The label keeps the time it took, so it stays a record of the run
    // rather than a Show/Hide switch.
    reasoning.dataset.done = "true";
    if (triggerLabel) {
      const seconds = Math.max(1, Math.round((Date.now() - thinkingStart) / 1000));
      window.JamesMotion?.stopThinking(triggerLabel, `Thought for ${seconds}s`);
    }
    reasoningBody.scrollTop = 0;
    setReasoningOpen(reasoning, false);
  };
  const chatId = activeChatId;
  pendingChats.add(chatId);
  renderHistory();
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
    if (!streamEl) {
      streamEl = el("div", "stream t-stream");
      caret = el("span", "caret");
      streamEl.append(caret);
      reply.append(streamEl);
    } else {
      streamEl.className = "stream t-stream";
    }
    if (window.JamesMotion?.paintStreamWords) {
      window.JamesMotion.paintStreamWords(streamEl, shown, caret);
    } else {
      streamEl.replaceChildren(document.createTextNode(shown));
      if (caret) streamEl.append(caret);
    }
    scrollChat();
  };
  const settleInto = (node) => {
    caret?.remove();
    status.remove();
    turn.classList.remove("pending");
    node.classList.add("t-fade-in");
    reply.append(node);
    if (streamEl) {
      const outgoing = streamEl;
      streamEl = null;
      outgoing.classList.add("is-fading");
      window.setTimeout(() => outgoing.remove(), window.JamesMotion?.tokenMs("--duration-fast", 250) || 250);
    }
  };
  const applyReply = (event) => {
    reply.querySelector(".briefing")?.remove();
    reply.querySelector(".receipt")?.remove();
    reply.querySelector(".question-card")?.remove();
    reply.querySelector(".cannot-card")?.remove();
    reply.querySelector(".md-prose")?.remove();
    if (event.kind === "error") {
      const err = el("p", "error", event.text || event.message || "Something went wrong.");
      settleInto(err);
      addRetry(reply, turn);
    } else {
      settleInto(paintReplyNode({ ...event, text: event.text || shown }, { autoOpen: true }));
    }
    liveChats.delete(chatId);
    revealLatestQuery(turn);
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
  liveChats.add(chatId);
  const body = { session_id: sessionId, message: text, filters, chat_id: chatId };
  if (turn.id) body.turn_id = turn.id;
  const chat = chats.find((item) => item.id === chatId);
  if (chat?.collectionId || activeCollectionId) {
    body.collection_id = chat?.collectionId || activeCollectionId;
  }
  if (chat?.pinned) body.pinned = true;
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
      addRetry(reply, turn);
      window.JamesMotion?.showToast("Could not send that. Try again.");
      window.JamesMotion?.shake(composerDrop);
      return;
    }
    resumePendingChat(chatId);
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
        if (event.type === "status") {
          setStatus(status, event.label);
          if (triggerLabel && reasoning?.dataset.done !== "true") {
            window.JamesMotion?.setThinkLine(triggerLabel, event.label, { shimmer: true });
          }
        }
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
          // Claude and Gemini tuck the thoughts away as soon as the answer
          // starts, rather than leaving them open above the typing reply.
          if (reasoning.dataset.streaming === "true") finishReasoning();
          incoming += event.text;
          if (!replaceQuietly) startReveal();
        }
        if (event.type === "reply") {
          finishReasoning();
          if (replaceQuietly || reply.querySelector(".briefing")) {
            incoming = "";
            replaceQuietly = false;
            applyReply(event);
            return;
          }
          if (event.kind && event.kind !== "plain") {
            incoming = "";
            pendingReply = null;
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
          addRetry(reply, turn);
          window.JamesMotion?.showToast(event.message);
          window.JamesMotion?.shake(composerDrop);
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
      reply.append(el("p", "error", "James lost the connection. Try that again."));
      addRetry(reply, turn);
      window.JamesMotion?.showToast("James lost the connection. Try that again.");
      window.JamesMotion?.shake(composerDrop);
    }
    liveChats.delete(chatId);
  } finally {
    if (gen !== requestGen) {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
      liveChats.delete(chatId);
      return;
    }
    pendingChats.delete(chatId);
    if (incoming || pendingReply) startReveal();
    else liveChats.delete(chatId);
    abortController = null;
    syncBusy();
    finishReasoning();
    snapshotActive();
    renderHistory();
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
    if (item.type) input.dataset.type = item.type;
    row.append(input, document.createTextNode(item.label));
    root.append(row);
  }
}

function openTaskMenu(anchor) {
  const openTasks = document.getElementById("open-tasks");
  if (!tasksDialog) return;
  if (!tasksDialog.hidden && tasksDialog.classList.contains("is-open")) {
    closeDialogs();
    return;
  }
  openDialog(tasksDialog, anchor || openTasks);
}

function showTaskGroup(group, anchor) {
  if (!taskItemsDialog || !taskItemsNav) return;
  taskItemsNav.replaceChildren();
  if (taskItemsTitle) taskItemsTitle.textContent = group.label;
  let section = "";
  for (const item of group.items || []) {
    if (item.section && item.section !== section) {
      section = item.section;
      taskItemsNav.append(el("p", "task-menu-subhead", section));
    }
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
  dialog.classList.remove("is-open", "is-closing");
  dialog.hidden = true;
}

function closePopover(dialog) {
  if (!dialog || dialog.hidden) return;
  window.JamesMotion?.closeSurface(dialog, hideDialogNow);
}

function closeModalDialog(dialog) {
  if (!dialog || dialog.hidden) return;
  window.JamesMotion?.closeSurface(dialog, (node) => {
    hideDialogNow(node);
    if (dialogScrim) dialogScrim.hidden = true;
  });
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
  else if (dialog.classList.contains("t-modal")) closeModalDialog(dialog);
  else hideDialogNow(dialog);
  const modalOpen = [...document.querySelectorAll(".app-dialog:not(.app-popover)")].some(
    (node) => !node.hidden
  );
  if (!modalOpen && dialogScrim) dialogScrim.hidden = true;
  if (id === "delete-dialog") {
    pendingDeleteChatId = "";
    pendingDeleteCollectionId = "";
    if (deleteDialogTitle) deleteDialogTitle.textContent = "Delete chat";
  }
  if (id === "collection-prompt-dialog") {
    collectionPromptMode = "";
    renameCollectionId = "";
    renameChatId = "";
  }
  if (id === "move-collection-dialog" && collectionPromptMode !== "create") moveChatId = "";
}

function closeDialogs() {
  closeDialogById("task-items-dialog");
  closeDialogById("tasks-dialog");
  closeDialogById("filters-dialog");
  closeDialogById("delete-dialog");
  closeDialogById("collection-prompt-dialog");
  closeDialogById("move-collection-dialog");
  closeDialogById("chat-sort-dialog");
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
      requestAnimationFrame(() => {
        if (window.JamesMotion) window.JamesMotion.openSurface(dialog);
        else dialog.classList.add("is-open");
      });
    });
    return;
  }
  dialog.hidden = false;
  dialog.classList.add("is-open");
  if (dialogScrim) dialogScrim.hidden = false;
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      if (window.JamesMotion) window.JamesMotion.openSurface(dialog);
      else dialog.classList.add("is-open");
    });
  });
}

function askDeleteChat(chatId, title) {
  pendingDeleteChatId = chatId;
  pendingDeleteCollectionId = "";
  if (deleteDialogTitle) deleteDialogTitle.textContent = "Delete chat";
  if (deleteDialogCopy) {
    deleteDialogCopy.textContent = `Delete “${title}”? This cannot be undone.`;
  }
  openDialog(deleteDialog);
}

function bootDialogs() {
  const openTasks = document.getElementById("open-tasks");
  const openFilters = document.getElementById("open-filters");
  openTasks?.addEventListener("click", (event) => {
    event.stopPropagation();
    openTaskMenu(openTasks);
  });
  openFilters?.addEventListener("click", (event) => {
    event.stopPropagation();
    if (!filtersDialog.hidden && filtersDialog.classList.contains("is-open")) {
      closeDialogs();
      return;
    }
    openDialog(filtersDialog, openFilters);
  });
  document.addEventListener("click", (event) => {
    const emptyTasks = event.target.closest("#open-tasks-empty");
    const emptyFilters = event.target.closest("#open-filters-empty");
    if (emptyTasks) {
      event.stopPropagation();
      openTaskMenu(emptyTasks);
      return;
    }
    if (emptyFilters) {
      event.stopPropagation();
      if (!filtersDialog.hidden && filtersDialog.classList.contains("is-open")) {
        closeDialogs();
        return;
      }
      openDialog(filtersDialog, emptyFilters);
    }
  });
  dialogScrim?.addEventListener("click", closeDialogs);
  for (const button of document.querySelectorAll("[data-close-dialog]")) {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      closeDialogById(button.getAttribute("data-close-dialog"));
    });
  }
  confirmDeleteChat?.addEventListener("click", async () => {
    const chatId = pendingDeleteChatId;
    const collectionId = pendingDeleteCollectionId;
    closeDialogs();
    if (collectionId) await deleteCollection(collectionId);
    else if (chatId) await deleteChat(chatId);
  });
  confirmCollectionPrompt?.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    submitCollectionPrompt();
  });
  document.getElementById("collection-prompt-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    event.stopPropagation();
    submitCollectionPrompt();
  });
  collectionPromptDialog?.addEventListener("keydown", (event) => {
    event.stopPropagation();
  });
  collectionPromptInput?.addEventListener("keydown", (event) => {
    event.stopPropagation();
    if (event.key === "Enter") {
      event.preventDefault();
      submitCollectionPrompt();
    }
  });
  document.getElementById("chat-recents-new")?.addEventListener("click", () => {
    hideRecents();
    startNewChat({ force: true });
  });
  document.getElementById("chat-recents-sort")?.addEventListener("click", (event) => {
    event.stopPropagation();
    openChatSortMenu(event.currentTarget);
  });
  chatRecentsSearchBtn?.addEventListener("click", (event) => {
    event.stopPropagation();
    const open = chatRecentsSearch?.hidden !== false;
    if (!chatRecentsSearch) return;
    chatRecentsSearch.hidden = !open;
    chatRecentsSearchWrap?.classList.toggle("is-open", open);
    if (open) chatRecentsSearch.focus();
    else {
      recentsQuery = "";
      chatRecentsSearch.value = "";
      renderRecents();
    }
  });
  chatRecentsSelect?.addEventListener("click", () => {
    recentsSelecting = !recentsSelecting;
    if (!recentsSelecting) recentsPicked.clear();
    renderRecents();
  });
  chatRecentsDelete?.addEventListener("click", async () => {
    const ids = [...recentsPicked];
    if (!ids.length) return;
    recentsSelecting = false;
    recentsPicked.clear();
    for (const id of ids) await deleteChat(id);
    renderRecents();
    renderHistory();
  });
  chatRecentsSearch?.addEventListener("input", () => {
    recentsQuery = chatRecentsSearch.value || "";
    renderRecents();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      if (taskItemsDialog?.classList.contains("is-open")) {
        closeDialogById("task-items-dialog");
        return;
      }
      if (chatSortDialog?.classList.contains("is-open")) {
        closeDialogById("chat-sort-dialog");
        return;
      }
      if (isRecentsOpen()) {
        hideRecents();
        return;
      }
      closeDialogs();
      return;
    }
    const typing = event.target.closest("input, textarea, select, [contenteditable]");
    if (typing) return;
    if (event.key === "/" || ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k")) {
      event.preventDefault();
      openTaskMenu(document.getElementById("open-tasks"));
    }
  });
  document.addEventListener("mousedown", (event) => {
    if (event.target.closest(".t-modal.is-open")) return;
    const openPopovers = [...document.querySelectorAll(".app-popover.is-open")].filter(
      (node) => !node.hidden
    );
    if (!openPopovers.length) return;
    if (openPopovers.some((node) => node.contains(event.target))) return;
    if (event.target.closest("#open-tasks, #open-tasks-empty, #open-filters, #open-filters-empty, #open-chat-sort, #open-chat-recents, #chat-recents-sort")) return;
    closeDialogById("task-items-dialog");
    closeDialogById("tasks-dialog");
    closeDialogById("filters-dialog");
    closeDialogById("chat-sort-dialog");
  });
  window.addEventListener("resize", () => {
    if (tasksDialog.classList.contains("is-open")) placePopover(tasksDialog, openTasks);
    if (filtersDialog.classList.contains("is-open")) placePopover(filtersDialog, openFilters);
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
  if ((!text && !attachments.length) || send.disabled) {
    if (!send.disabled) window.JamesMotion?.shake(composerDrop);
    return;
  }
  prompt.value = "";
  resizePrompt();
  askJames({ text: text || "Review the attached files." });
});

stop.addEventListener("click", () => {
  settleIncompleteTurn();
  snapshotActive();
  scrollChat(true);
  abortController?.abort();
  cancelChatRun(activeChatId);
  syncBusy();
});

newChat.addEventListener("click", () => {
  window.JamesArtifacts?.hideLibrary();
  window.JamesArtifacts?.closePane();
  hideRecents();
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

prompt.addEventListener("input", () => {
  resizePrompt();
  composerDrop?.classList.remove("is-error", "is-shaking");
  if (!prompt.value.trim() && hasSelections()) clearAllSelections();
  syncComposerHint();
});

bootChatScroll();

prompt.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

async function boot() {
  bootSidebar();
  bootDialogs();
  loadChatListPrefs();
  loadChats();
  const collectionFromUrl = (new URLSearchParams(location.search).get("collection") || "").trim();
  if (collectionFromUrl) activeCollectionId = collectionFromUrl;
  const launching = dashboardLaunchParams();
  // The saved thread is already in localStorage, so paint it before the first
  // fetch. Waiting would show the empty canvas for as long as boot is offline.
  if (launching || !restoreActiveChat()) showEmptyCanvas();
  await loadLibrary();
  forgetImportedChats();
  if (launching) {
    activeChatId = "";
    await createSession();
  } else {
    const saved = chats.find((item) => item.id === activeChatId);
    if (saved?.sessionId) sessionId = saved.sessionId;
    if (!sessionId) await createSession();
  }
  workspace = await fetch("/api/workspace").then((res) => res.json());
  showReasoning = Boolean(workspace?.ui?.reasoning);
  renderTasks(workspace.tasks);
  bootComposerDropzone();
  renderHistory();
  addChecks(filterOpps, workspace.filters.campaigns || workspace.filters.opps, "campaign");
  addChecks(filterOrg, workspace.filters.campaign_types || workspace.filters.boats, "campaign_type");
  addChecks(filterReports, workspace.filters.asset_types, "asset_type");
  addChecks(filterContent, workspace.filters.content, "content");
  syncFilterAvailability();
  applyDashboardLaunch();
  renderSelection();
  syncComposerHint();
  const refreshDraft = () => {
    syncFilterAvailability();
    if (activeTask) fillComposer(activeTask);
    renderSelection();
    offerFilterRefresh();
  };
  filterOrg?.addEventListener("change", refreshDraft);
  filterOpps?.addEventListener("change", refreshDraft);
  filterReports?.addEventListener("change", refreshDraft);
  filterContent?.addEventListener("change", refreshDraft);
  document.getElementById("clear-selections")?.addEventListener("click", () => {
    clearAllSelections();
    prompt.value = "";
    resizePrompt();
    hideComposerSuggest();
    prompt.focus();
  });
  bootComposerSuggest();
}

boot();
