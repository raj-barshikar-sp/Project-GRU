const ASK_CATALOG = [
  {
    id: "coaching", name: "Coaching & Training",
    blurb: "Practice and improve seller skills",
    asks: [
      { id: "coaching.cold_call", action: "cold_call_coaching", label: "Cold call coaching agent", account: true, keywords: "cold call coaching", prompt: "Coach my cold call for this account." },
      { id: "coaching.pitch", action: "pitch_practice", label: "Pitch practice agent", account: true, keywords: "pitch practice", prompt: "Run a pitch practice session for this account." }
    ]
  },
  {
    id: "prospecting", name: "Prospecting",
    blurb: "Prioritize territory and create outreach",
    asks: [
      { id: "prospecting.top", action: "top_prospect_accounts", label: "What are my top accounts?", keywords: "top accounts prioritize", prompt: "What are my top prospect accounts?" },
      { id: "prospecting.intel", action: "intel_analysis", label: "Run intel analysis", account: true, keywords: "intel analysis", prompt: "Run intel analysis for this prospect." },
      { id: "prospecting.messaging", action: "messaging", label: "Build messaging", account: true, keywords: "build messaging", prompt: "Build prospecting messaging for this account." },
      { id: "prospecting.whitespace", action: "territory_whitespace", label: "Territory whitespace", keywords: "territory whitespace", prompt: "Analyze territory whitespace across my accounts." }
    ]
  },
  {
    id: "expansion", name: "Customer Upsell / Cross-sell",
    blurb: "Find and develop customer growth",
    asks: [
      { id: "expansion.top", action: "top_upsell_target", label: "What is my top account to target?", keywords: "top upsell target", prompt: "What is my top customer account to target for upsell, cross-sell, or true-up?" },
      { id: "expansion.health", action: "account_360_healthcheck", label: "Account 360 healthcheck", account: true, keywords: "account 360 healthcheck", prompt: "Run an account 360 healthcheck." },
      { id: "expansion.intel", action: "intel_analysis", label: "Run intel analysis", account: true, keywords: "customer intel", prompt: "Run customer intel analysis for this account." },
      { id: "expansion.messaging", action: "messaging", label: "Build messaging", account: true, keywords: "customer messaging", prompt: "Build upsell and cross-sell messaging for this account." }
    ]
  },
  {
    id: "qualification", name: "Deal Qualification",
    blurb: "Qualify and prepare early-stage deals",
    asks: [
      { id: "qualification.plan", action: "account_plan", label: "Account plan builder", account: true, keywords: "account plan", prompt: "Build an account plan." },
      { id: "qualification.discovery", action: "discovery_prep", label: "Discovery call prep", account: true, keywords: "discovery call prep", prompt: "Prepare my discovery call." },
      { id: "qualification.notes", action: "post_meeting_notes", label: "Post-meeting notes & email", account: true, keywords: "meeting notes email", prompt: "Create post-meeting notes and an email." },
      { id: "qualification.followup", action: "suggested_follow_up", label: "Suggested follow-up content", account: true, keywords: "follow up", prompt: "Suggest follow-up content." }
    ]
  },
  {
    id: "advancement", name: "Deal Advancement",
    blurb: "Build consensus and commercial value",
    asks: [
      { id: "advancement.room", action: "digital_sales_room", label: "Digital sales room setup", account: true, keywords: "digital sales room", prompt: "Set up a digital sales room outline." },
      { id: "advancement.dmu", action: "dmu_expansion", label: "DMU expansion", account: true, keywords: "dmu expansion", prompt: "Build a DMU expansion plan." },
      { id: "advancement.plan", action: "opportunity_plan", label: "Build opportunity plan", account: true, keywords: "opportunity plan", prompt: "Build an opportunity plan." },
      { id: "advancement.bva", action: "business_value_assessment", label: "Build BVA", account: true, keywords: "build bva", prompt: "Build a business value assessment." },
      { id: "advancement.competitive", action: "competitive_positioning_deck", label: "Competitive positioning & battlecard", account: true, keywords: "competitive positioning battlecard", prompt: "Create a competitive positioning deck and battlecard." },
      { id: "advancement.quote", action: "initial_quote", label: "Build initial quote", account: true, keywords: "initial quote", prompt: "Build an initial quote." }
    ]
  },
  {
    id: "close", name: "Deal Close",
    blurb: "Validate and close cleanly",
    asks: [
      { id: "close.proposal", action: "proposal", label: "Proposal builder", account: true, keywords: "proposal", prompt: "Build a proposal." },
      { id: "close.risk", action: "deal_risk", label: "Deal risk assessment", account: true, keywords: "deal risk", prompt: "Run a deal risk assessment." },
      { id: "close.discount", action: "quote_discount_checker", label: "Quote / discount checker", account: true, keywords: "discount checker", prompt: "Check a 10% discount against local demo guardrails." },
      { id: "close.contract", action: "contract_review", label: "Review my contract", account: true, keywords: "contract review", prompt: "Review the contract using the local demo checklist." },
      { id: "close.handoff", action: "post_sales_handoff", label: "Post-sales account handoff", account: true, keywords: "post sales handoff", prompt: "Build a post-sales handoff for PS and CSM." }
    ]
  },
  {
    id: "faq", name: "FAQ Agents",
    blurb: "Local demo guidance",
    asks: [
      { id: "faq.roe", action: "rules_of_engagement", label: "Rules of engagement", keywords: "rules engagement", prompt: "Explain the local demo rules of engagement." },
      { id: "faq.commission", action: "commission_plans", label: "Commission plans", keywords: "commission plans", prompt: "Explain the local demo commission-plan guidance." },
      { id: "faq.product", action: "product_overview", label: "Product overview", keywords: "product overview", prompt: "Give me the local product overview." }
    ]
  }
];

const ASK_INDEX = new Map();
ASK_CATALOG.forEach((category) => category.asks.forEach((ask) => ASK_INDEX.set(ask.id, { ...ask, category })));

const WORKFLOWS = [
  { id: "prospecting", label: "Prospecting", keywords: "prospecting prioritize", prompt: "Find and prioritize the strongest prospects for me." },
  { id: "discovery", label: "Discovery", keywords: "discovery questions", prompt: "Prepare a discovery plan with hypotheses and questions." },
  { id: "outreach", label: "Outreach", keywords: "outreach email message", prompt: "Create personalized outreach for the key stakeholder." },
  { id: "deal-risk", label: "Deal risk", keywords: "deal risk gaps", prompt: "Assess this deal's risk and recommend next actions." }
];

const HENRY_IMAGE = "/static/assets/henry.png";

const THINKING_PHRASES = [
  "Checking CRM signals",
  "Reading buyer intent",
  "Scanning account history",
  "Mapping the buying committee",
  "Weighing competitive plays",
  "Building your recommendation"
];

const ICONS = {
  caret: '<svg class="menu-caret" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><polyline points="8,4 14,10 8,16"></polyline></svg>',
  check: '<span class="box" aria-hidden="true"><svg viewBox="0 0 12 12"><polyline points="2.4,6.3 4.8,8.7 9.6,3.5"></polyline></svg></span>',
  copy: '<svg viewBox="0 0 20 20" aria-hidden="true" focusable="false"><rect x="7" y="7" width="9.5" height="9.5" rx="2"></rect><path d="M13 4.5H5.5a2 2 0 0 0-2 2V13"></path></svg>',
  close: '<svg viewBox="0 0 20 20" aria-hidden="true" focusable="false"><line x1="5.5" y1="5.5" x2="14.5" y2="14.5"></line><line x1="14.5" y1="5.5" x2="5.5" y2="14.5"></line></svg>'
};

const THEME_KEY = "henry.theme";
const SIDEBAR_KEYS = { left: "henry.sidebar.left", right: "henry.sidebar.right" };
const TASKS_KEY = "henry.account.tasks";
const THEME_CHOICES = ["light", "dark", "system"];
const THEME_LABELS = { light: "Theme: light", dark: "Theme: dark", system: "Theme: match system" };

const state = {
  workflow: "prospecting",
  account: null,
  accounts: [],
  busy: false,
  action: null,
  ask: null,
  openGroups: new Set(["workflows"]),
  askFilter: "",
  chats: [],
  activeChatId: null,
  messages: [],
  tasksByAccount: {},
  quickViews: {}
};

const $ = (selector) => document.querySelector(selector);
const root = document.documentElement;
const conversation = $("#conversation");
const welcome = $("#welcome");
const form = $("#chat-form");
const input = $("#message");
const menuNode = $("#task-menu");
const historyNode = $("#chat-history");
const themeButton = $("#theme-switch");
const scrim = $("#scrim");

const darkQuery = window.matchMedia("(prefers-color-scheme: dark)");
const mobileQuery = window.matchMedia("(max-width: 860px)");
const reduceMotionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");

const answerSource = new WeakMap();
let thinkingTimer = null;
let scrimTimer = null;

/* --------------------------------------------------------------- storage */

function readStore(key) {
  try {
    return window.localStorage.getItem(key);
  } catch (error) {
    return null;
  }
}

function writeStore(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch (error) {
    /* private mode or blocked storage — preferences stay session-only */
  }
}

function readTasks() {
  const raw = readStore(TASKS_KEY);
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    const clean = {};
    Object.entries(parsed).forEach(([account, tasks]) => {
      if (!Array.isArray(tasks)) return;
      clean[account] = tasks
        .filter((task) => task && typeof task.text === "string" && task.text.trim())
        .map((task) => ({
          id: String(task.id || `task-${Date.now()}-${Math.random()}`),
          text: task.text.trim().slice(0, 180),
          done: Boolean(task.done)
        }));
    });
    return clean;
  } catch (error) {
    return {};
  }
}

function saveTasks() {
  writeStore(TASKS_KEY, JSON.stringify(state.tasksByAccount));
}

/* -------------------------------------------------------------- markdown */

const CONTROL_CHARS = /[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g;
const BULLET_ITEM = /^(\s{0,6})([-*+])\s+(.*)$/;
const ORDERED_ITEM = /^(\s{0,6})(\d{1,9})[.)]\s+(.*)$/;
const HEADING = /^\s{0,3}(#{1,4})\s+(.*)$/;
const FENCE = /^\s{0,3}(```|~~~)/;

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  })[char]);
}

// Splits one pipe-table row into trimmed cells, honouring escaped pipes and
// dropping the optional leading/trailing pipe.
function splitTableRow(line) {
  const text = line.trim();
  const cells = [];
  let current = "";
  let index = 0;
  while (index < text.length) {
    const char = text[index];
    if (char === "\\" && text[index + 1] === "|") {
      current += "|";
      index += 2;
      continue;
    }
    if (char === "|") {
      cells.push(current);
      current = "";
      index += 1;
      continue;
    }
    current += char;
    index += 1;
  }
  cells.push(current);
  if (cells.length > 1 && !cells[0].trim()) cells.shift();
  if (cells.length > 1 && !cells[cells.length - 1].trim()) cells.pop();
  return cells.map((cell) => cell.trim());
}

function isDelimiterRow(line, expectedColumns) {
  if (typeof line !== "string" || line.indexOf("-") === -1) return false;
  const cells = splitTableRow(line);
  if (cells.length !== expectedColumns) return false;
  return cells.every((cell) => /^:?-+:?$/.test(cell));
}

function alignmentClass(cell) {
  const left = cell.startsWith(":");
  const right = cell.endsWith(":");
  if (left && right) return "md-center";
  if (right) return "md-right";
  return "";
}

function cellAttributes(alignment) {
  return alignment ? ` class="${alignment}"` : "";
}

// Inline formatting. `text` is already HTML-escaped, so nothing here can
// introduce markup that the model controls.
function inlineMarkdown(text) {
  const codes = [];
  let out = text.replace(/`([^`\n]+)`/g, (match, code) => {
    codes.push(code);
    return `\u0001${codes.length - 1}\u0001`;
  });
  out = out.replace(/\*\*(?=\S)([\s\S]*?\S)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/\[([^\]\n]*)\]\(([^()\s]+)\)/g, (match, label, url) => {
    if (!/^https?:\/\/[^\s]+$/i.test(url)) return match;
    return `<a href="${url}" target="_blank" rel="noopener noreferrer">${label || url}</a>`;
  });
  return out.replace(/\u0001(\d+)\u0001/g, (match, index) => {
    const code = codes[Number(index)];
    return code === undefined ? match : `<code>${code}</code>`;
  });
}

function isBlank(line) {
  return typeof line !== "string" || !line.trim();
}

function isBlockStart(line) {
  return HEADING.test(line) || FENCE.test(line) || BULLET_ITEM.test(line) || ORDERED_ITEM.test(line);
}

function isTableStart(lines, index) {
  const line = lines[index];
  if (typeof line !== "string" || line.indexOf("|") === -1) return false;
  const columns = splitTableRow(line).length;
  return columns > 0 && isDelimiterRow(lines[index + 1], columns);
}

function renderTable(lines, startIndex) {
  const header = splitTableRow(lines[startIndex]);
  const alignments = splitTableRow(lines[startIndex + 1]).map(alignmentClass);
  const rows = [];
  let index = startIndex + 2;
  while (index < lines.length && !isBlank(lines[index]) && lines[index].indexOf("|") !== -1) {
    const cells = splitTableRow(lines[index]);
    const normalized = header.map((ignored, column) => cells[column] ?? "");
    rows.push(normalized);
    index += 1;
  }

  const head = header
    .map((cell, column) => `<th${cellAttributes(alignments[column] ?? "")} scope="col">${inlineMarkdown(cell)}</th>`)
    .join("");
  const body = rows
    .map((cells) => `<tr>${cells
      .map((cell, column) => `<td${cellAttributes(alignments[column] ?? "")}>${inlineMarkdown(cell)}</td>`)
      .join("")}</tr>`)
    .join("");

  return {
    html: `<div class="md-table-wrap"><table class="md-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`,
    nextIndex: index
  };
}

function markdown(value) {
  // Structured payloads keep their indentation instead of collapsing to prose.
  if (value !== null && typeof value === "object") {
    let json;
    try {
      json = JSON.stringify(value, null, 2);
    } catch (error) {
      json = String(value);
    }
    return `<pre><code>${escapeHtml(json ?? "")}</code></pre>`;
  }

  const raw = value === null || value === undefined ? "" : String(value);
  const source = escapeHtml(raw.replace(/\r\n?/g, "\n").replace(CONTROL_CHARS, ""));
  const lines = source.split("\n");
  const out = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];

    if (isBlank(line)) {
      index += 1;
      continue;
    }

    const fence = line.match(FENCE);
    if (fence) {
      const marker = fence[1];
      const body = [];
      index += 1;
      while (index < lines.length && lines[index].trim() !== marker) {
        body.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) index += 1;
      out.push(`<pre><code>${body.join("\n")}</code></pre>`);
      continue;
    }

    const heading = line.match(HEADING);
    if (heading) {
      const level = heading[1].length;
      out.push(`<h${level}>${inlineMarkdown(heading[2].trim())}</h${level}>`);
      index += 1;
      continue;
    }

    if (isTableStart(lines, index)) {
      const table = renderTable(lines, index);
      out.push(table.html);
      index = table.nextIndex;
      continue;
    }

    const bullet = line.match(BULLET_ITEM);
    const ordered = bullet ? null : line.match(ORDERED_ITEM);
    if (bullet || ordered) {
      const pattern = ordered ? ORDERED_ITEM : BULLET_ITEM;
      const items = [];
      const start = ordered ? Number(ordered[2]) : 1;
      while (index < lines.length) {
        const current = lines[index];
        const match = current.match(pattern);
        if (match) {
          items.push(match[3]);
          index += 1;
          continue;
        }
        const lazy = items.length && !isBlank(current) && !isBlockStart(current) && !isTableStart(lines, index);
        if (lazy) {
          items[items.length - 1] += ` ${current.trim()}`;
          index += 1;
          continue;
        }
        break;
      }
      const body = items.map((item) => `<li>${inlineMarkdown(item.trim())}</li>`).join("");
      out.push(ordered
        ? `<ol${start > 1 ? ` start="${start}"` : ""}>${body}</ol>`
        : `<ul>${body}</ul>`);
      continue;
    }

    const paragraph = [];
    while (index < lines.length && !isBlank(lines[index]) && !isBlockStart(lines[index]) && !isTableStart(lines, index)) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    if (!paragraph.length) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    out.push(`<p>${paragraph.map((part) => inlineMarkdown(part)).join("<br>")}</p>`);
  }

  return out.join("");
}

/* ---------------------------------------------------------- conversation */

function updateWelcome() {
  if (welcome) welcome.hidden = Boolean(conversation.querySelector(".message"));
}

function scrollToLatest() {
  const canvas = conversation.closest(".canvas");
  if (canvas) canvas.scrollTop = canvas.scrollHeight;
}

function addMessage(role, content, record = true) {
  if (record) state.messages.push({ role, content });
  const article = document.createElement("article");
  if (role === "user") {
    article.className = "message user-message";
    article.innerHTML = `<div class="bubble">${markdown(content)}</div>`;
  } else {
    article.className = "message henry-message";
    article.innerHTML = `<div class="answer">${markdown(content)}</div>
      <div class="answer-tools"><button type="button" class="copy-answer" title="Copy answer" aria-label="Copy answer">${ICONS.copy}</button></div>`;
    answerSource.set(article, typeof content === "string" ? content : JSON.stringify(content, null, 2));
  }
  conversation.appendChild(article);
  updateWelcome();
  scrollToLatest();
}

function setThinkingPhrase(node, phrase) {
  const line = document.createElement("span");
  line.textContent = phrase;
  node.replaceChildren(line);
}

function stopThinking() {
  if (thinkingTimer !== null) {
    window.clearInterval(thinkingTimer);
    thinkingTimer = null;
  }
  document.getElementById("thinking")?.remove();
}

function startThinking() {
  stopThinking();
  const node = document.createElement("article");
  node.id = "thinking";
  node.className = "message henry-message thinking";
  node.innerHTML = `<img src="${HENRY_IMAGE}" alt="" aria-hidden="true" width="30" height="30">
    <span class="sr-only">Henry is thinking</span>
    <span class="thinking-status" aria-hidden="true"></span>
    <span class="thinking-dots" aria-hidden="true"><i></i><i></i><i></i></span>`;
  conversation.appendChild(node);
  updateWelcome();
  scrollToLatest();

  const status = node.querySelector(".thinking-status");
  if (!status) return;
  let cursor = 0;
  setThinkingPhrase(status, THINKING_PHRASES[cursor]);
  if (reduceMotionQuery.matches) return;
  thinkingTimer = window.setInterval(() => {
    cursor = (cursor + 1) % THINKING_PHRASES.length;
    setThinkingPhrase(status, THINKING_PHRASES[cursor]);
  }, 2100);
}

function toast(message) {
  const node = $("#toast");
  node.textContent = message;
  node.classList.add("show");
  window.setTimeout(() => node.classList.remove("show"), 2600);
}

/* ----------------------------------------------------------- chat history */

// History holds whole conversations, not individual prompts. The open chat is
// filed away when you start a new one or switch to an older one.

function chatTitle(messages) {
  const first = messages.find((entry) => entry.role === "user");
  const text = typeof first?.content === "string" ? first.content.trim() : "";
  return text || "Untitled chat";
}

function archiveCurrentChat() {
  if (!state.messages.length) return;
  const existing = state.chats.find((chat) => chat.id === state.activeChatId);
  if (existing) {
    existing.title = chatTitle(state.messages);
    existing.messages = state.messages.slice();
    return;
  }
  state.chats.unshift({
    id: `chat-${Date.now()}-${state.chats.length}`,
    title: chatTitle(state.messages),
    messages: state.messages.slice()
  });
  state.chats = state.chats.slice(0, 20);
}

function showTranscript(messages) {
  stopThinking();
  conversation.querySelectorAll(".message").forEach((node) => node.remove());
  messages.forEach((entry) => addMessage(entry.role, entry.content, false));
  updateWelcome();
}

function startNewChat() {
  archiveCurrentChat();
  state.messages = [];
  state.activeChatId = null;
  showTranscript([]);
  renderHistory();
  clearAsk();
  input.value = "";
  autosize();
  input.focus();
}

function openChat(id) {
  if (id === state.activeChatId) return;
  const chat = state.chats.find((item) => item.id === id);
  if (!chat) return;
  archiveCurrentChat();
  state.activeChatId = id;
  state.messages = chat.messages.slice();
  showTranscript(state.messages);
  renderHistory();
}

function renderHistory() {
  if (!historyNode) return;
  historyNode.innerHTML = state.chats.length
    ? state.chats.map((chat) => {
      const current = chat.id === state.activeChatId ? " current" : "";
      return `<button type="button" class="history-item${current}" data-chat="${escapeHtml(chat.id)}" title="${escapeHtml(chat.title)}">${escapeHtml(chat.title)}</button>`;
    }).join("")
    : '<p class="empty-note">Start a new chat and this conversation gets filed here.</p>';
}

/* ------------------------------------------------------------------ theme */

function resolvedTheme(preference) {
  if (preference === "light" || preference === "dark") return preference;
  return darkQuery.matches ? "dark" : "light";
}

function applyTheme(preference, persist) {
  const choice = THEME_CHOICES.includes(preference) ? preference : "system";
  const resolved = resolvedTheme(choice);
  root.dataset.themePref = choice;
  root.dataset.theme = resolved;

  if (themeButton) {
    themeButton.title = THEME_LABELS[choice];
    themeButton.setAttribute("aria-label", `${THEME_LABELS[choice]} — click to change`);
  }
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", resolved === "dark" ? "#0c1220" : "#ffffff");
  if (persist) writeStore(THEME_KEY, choice);
}

/* ------------------------------------------------------ sidebar + dialogs */

function railButton(side) {
  return side === "left" ? $("#toggle-left") : $("#toggle-right");
}

function updateScrim() {
  if (!scrim) return;
  const open = root.dataset.right === "open"
    || root.dataset.tasks === "open"
    || (mobileQuery.matches && root.dataset.left === "open");
  window.clearTimeout(scrimTimer);
  if (open) {
    scrim.hidden = false;
    window.requestAnimationFrame(() => scrim.classList.add("show"));
    return;
  }
  scrim.classList.remove("show");
  scrimTimer = window.setTimeout(() => {
    if (!scrim.classList.contains("show")) scrim.hidden = true;
  }, 300);
}

function setSidebar(side, open, persist = true) {
  if (side === "right") {
    setDialog("right", open);
    return;
  }
  root.dataset[side] = open ? "open" : "closed";
  railButton(side)?.setAttribute("aria-expanded", String(open));
  // Only the desktop layout persists: mobile drawers always reopen closed.
  if (persist && !mobileQuery.matches) writeStore(SIDEBAR_KEYS[side], open ? "open" : "closed");
  updateScrim();
}

function toggleSidebar(side) {
  setSidebar(side, root.dataset[side] !== "open");
}

function setDialog(kind, open) {
  const node = kind === "tasks" ? $("#tasks-dialog") : $("#right-panel");
  if (!node) return;

  if (open) {
    const other = kind === "tasks" ? "right" : "tasks";
    setDialog(other, false);
    root.dataset[kind] = "open";
    node.hidden = false;
    window.requestAnimationFrame(() => node.classList.add("is-open"));
  } else {
    root.dataset[kind] = "closed";
    node.classList.remove("is-open");
    window.setTimeout(() => {
      if (root.dataset[kind] !== "open") node.hidden = true;
    }, 240);
  }
  if (kind === "right") {
    $("#toggle-right")?.setAttribute("aria-expanded", String(open));
    $("#toggle-right")?.classList.toggle("is-active", open);
  } else {
    $("#open-tasks")?.classList.toggle("is-active", open);
  }
  updateScrim();
}

/* ------------------------------------------------------------- account IO */

function accountId() {
  return state.account?.id ?? state.account?.account_id ?? null;
}

function accountName() {
  return state.account?.name ?? state.account?.company ?? null;
}

function pickField(account, keys) {
  for (const key of keys) {
    const value = account?.[key];
    if (value === undefined || value === null) continue;
    if (typeof value === "string" && !value.trim()) continue;
    if (Array.isArray(value) && !value.length) continue;
    return value;
  }
  return null;
}

function toNumber(value) {
  if (value === null || value === undefined || value === "" || typeof value === "boolean") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function compactMoney(value) {
  const number = toNumber(value);
  if (number === null || number === 0) return null;
  const abs = Math.abs(number);
  let text;
  if (abs >= 1e9) text = `$${(number / 1e9).toFixed(2)}B`;
  else if (abs >= 1e6) text = `$${(number / 1e6).toFixed(2)}M`;
  else if (abs >= 1e3) text = `$${Math.round(number / 1e3)}k`;
  else text = `$${number}`;
  return text.replace(/\.00(?=[BM]$)/, "");
}

function wholeNumber(value) {
  const number = toNumber(value);
  return number === null ? null : number.toLocaleString("en-US");
}

function daysSince(value) {
  const time = Date.parse(String(value));
  if (Number.isNaN(time)) return null;
  const days = Math.floor((Date.now() - time) / 86400000);
  return days >= 0 ? days : null;
}

function friendlyDate(value) {
  const time = Date.parse(String(value));
  if (Number.isNaN(time)) return String(value ?? "");
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" })
    .format(new Date(time));
}

function ownerLabel(value) {
  return String(value ?? "")
    .replace(/^rep-/i, "")
    .split(/[-_.\s]+/)
    .filter(Boolean)
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(" ");
}

function quickFact(label, value) {
  if (value === null || value === undefined || value === "") return "";
  return `<div class="quick-fact"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
}

function quickMetric(label, value, note, tone = "") {
  return `<div class="quick-metric ${tone}">
    <span>${escapeHtml(label)}</span><strong>${escapeHtml(value ?? "—")}</strong>
    <small>${escapeHtml(note ?? "")}</small>
  </div>`;
}

function contactCard(contact) {
  const name = String(contact?.name ?? "Unknown contact");
  const initials = name.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
  const email = String(contact?.email ?? "");
  return `<article class="contact-card">
    <span class="contact-avatar">${escapeHtml(initials)}</span>
    <div><strong>${escapeHtml(name)}</strong><span>${escapeHtml(contact?.title ?? "")}</span>
      ${email ? `<a href="mailto:${escapeHtml(email)}">${escapeHtml(email)}</a>` : ""}
    </div>
    <small>${escapeHtml(contact?.seniority ?? "")}</small>
  </article>`;
}

function renderQuickView(view) {
  const account = view?.account ?? state.account ?? {};
  const intent = Array.isArray(view?.intent) ? view.intent[0] : null;
  const tech = view?.technographics;
  const risk = view?.deal_risk;
  const activityAge = daysSince(account.last_activity_date);
  const contacts = Array.isArray(tech?.key_contacts) ? tech.key_contacts : [];
  const technologies = Array.isArray(tech?.installed_technologies)
    ? tech.installed_technologies
    : [];
  const topics = Array.isArray(intent?.intent_topics) ? intent.intent_topics : [];
  const crmProducts = Array.isArray(account.current_products) ? account.current_products : [];
  const riskLevel = String(risk?.risk_level ?? "unknown").toLowerCase();
  const riskFlags = Array.isArray(risk?.flags) ? risk.flags : [];

  return `<div class="quick-view">
    <header class="quick-head">
      <div><strong>${escapeHtml(account.name ?? "Account")}</strong>
        <span>${escapeHtml(account.domain ?? "")}</span></div>
      <span class="stage-pill">${escapeHtml(account.stage ?? "No active deal")}</span>
    </header>

    <div class="quick-metrics">
      ${quickMetric(
        "Intent",
        intent?.intent_score ?? "—",
        intent ? `${intent.buying_stage} · ${intent.profile_fit} fit` : "No signal",
        intent?.intent_score >= 80 ? "good" : ""
      )}
      ${quickMetric(
        "Pipeline",
        compactMoney(account.open_opportunity_amount) ?? "$0",
        account.target_tier ?? "Unranked",
        account.open_opportunity_amount > 0 ? "pipeline" : ""
      )}
      ${quickMetric(
        "Deal risk",
        riskLevel === "unknown" ? "—" : riskLevel,
        risk ? `${risk.risk_score}/100 score` : "Not assessed",
        `risk-${riskLevel}`
      )}
      ${quickMetric(
        "Last touch",
        activityAge === null ? "—" : `${activityAge}d`,
        friendlyDate(account.last_activity_date)
      )}
    </div>

    ${topics.length ? `<section class="quick-section">
      <div class="quick-section-head"><h4>Buying signals</h4>
        <span>${escapeHtml(intent.source)} · ${escapeHtml(friendlyDate(intent.observed_at))}</span></div>
      <div class="signal-topics">${topics.map((topic) => `<span>${escapeHtml(topic)}</span>`).join("")}</div>
    </section>` : ""}

    <section class="quick-section">
      <div class="quick-section-head"><h4>Deal health</h4>
        <span class="risk-label risk-${escapeHtml(riskLevel)}">${escapeHtml(riskLevel)}</span></div>
      <div class="quick-facts">
        ${quickFact("Days in stage", account.days_in_stage)}
        ${quickFact("Stakeholders", account.stakeholder_count)}
        ${quickFact("Business value", account.bva_complete ? "Complete" : "Not started")}
        ${quickFact("CRM products", crmProducts.join(", ") || "None")}
      </div>
      ${riskFlags.length ? `<div class="risk-flags">${riskFlags.map((flag) => `<div>
        <strong>${escapeHtml(String(flag.code).replaceAll("_", " "))}</strong>
        <span>${escapeHtml(flag.evidence)}</span><small>${escapeHtml(flag.recommendation)}</small>
      </div>`).join("")}</div>` : '<p class="quick-clear">✓ No material deal-hygiene risks detected.</p>'}
    </section>

    ${tech ? `<section class="quick-section">
      <div class="quick-section-head"><h4>Technology &amp; team</h4>
        <span>Verified ${escapeHtml(friendlyDate(tech.last_verified_at))}</span></div>
      <p class="security-team">${escapeHtml(wholeNumber(tech.it_security_headcount) ?? "0")} people in IT security</p>
      <div class="tech-chips">${technologies.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>
    </section>` : ""}

    ${contacts.length ? `<section class="quick-section">
      <div class="quick-section-head"><h4>Key contacts</h4><span>${contacts.length} found</span></div>
      <div class="contact-list">${contacts.map(contactCard).join("")}</div>
    </section>` : ""}

    <section class="quick-section">
      <div class="quick-section-head"><h4>Company profile</h4></div>
      <div class="quick-facts company-facts">
        ${quickFact("Industry", account.industry)}
        ${quickFact("Revenue", compactMoney(account.annual_revenue))}
        ${quickFact("Employees", wholeNumber(account.employee_count))}
        ${quickFact("Territory", account.territory)}
        ${quickFact("Owner", ownerLabel(account.owner_id))}
        ${quickFact("Tier", account.target_tier)}
      </div>
    </section>
  </div>`;
}

function renderAccountPanel() {
  const detailsNode = $("#account-details");
  if (!detailsNode) return;

  if (!state.account) {
    detailsNode.innerHTML = '<p class="empty-note">Select an account to see its complete quick view.</p>';
    renderAccountTasks();
    return;
  }

  const id = String(accountId());
  const view = state.quickViews[id];
  detailsNode.innerHTML = view
    ? renderQuickView(view)
    : `<div class="quick-loading">
        <div class="quick-loading-head"></div>
        <div class="quick-loading-grid"><i></i><i></i><i></i><i></i></div>
        <div class="quick-loading-block"></div><div class="quick-loading-block"></div>
      </div>`;
  renderAccountTasks();
}

function focusAccountQuickView() {
  window.requestAnimationFrame(() => {
    $("#account-details")?.scrollIntoView({
      behavior: reduceMotionQuery.matches ? "auto" : "smooth",
      block: "start"
    });
  });
}

async function loadAccountQuickView(account) {
  const id = String(account?.id ?? account?.account_id ?? "");
  if (!id || state.quickViews[id]) return;
  try {
    const view = await request(`/api/accounts/${encodeURIComponent(id)}/quick-view`);
    state.quickViews[id] = view;
    if (String(accountId()) === id) {
      renderAccountPanel();
      focusAccountQuickView();
    }
  } catch (error) {
    if (String(accountId()) !== id) return;
    $("#account-details").innerHTML = `<div class="quick-error">
      <strong>Quick view unavailable</strong><span>${escapeHtml(error.message)}</span>
      <button type="button" id="retry-quick-view">Try again</button>
    </div>`;
    $("#retry-quick-view")?.addEventListener("click", () => {
      renderAccountPanel();
      loadAccountQuickView(account);
    });
  }
}

function renderSelectedAccount() {
  const section = $("#selected-account");
  const chip = $("#selected-account-chip");
  if (!section || !chip) return;
  section.hidden = !state.account;
  chip.innerHTML = state.account
    ? `<button class="account-chip" type="button" title="Open account controls">${escapeHtml(accountName())}</button>`
    : "";
}

/* ---------------------------------------------------------- account tasks */

// Henry answers task questions from this snapshot, so every account with a
// saved list travels with the request, not just the selected one.
function taskBoard() {
  return Object.entries(state.tasksByAccount)
    .filter(([, tasks]) => Array.isArray(tasks) && tasks.length)
    .map(([id, tasks]) => ({
      account_id: id,
      account_name: accountNameFor(state.accounts.find((item) => String(item.id) === id)) || id,
      items: tasks.map((task) => ({ text: task.text, done: Boolean(task.done) }))
    }));
}

function tasksFor(account = state.account) {
  const id = account?.id ?? account?.account_id;
  return id ? state.tasksByAccount[String(id)] ?? [] : [];
}

function renderAccountTasks() {
  const node = $("#account-tasks");
  const add = $("#add-task");
  const form = $("#task-form");
  if (!node || !add || !form) return;

  const id = accountId();
  add.disabled = !id;
  if (!id) {
    form.hidden = true;
    node.innerHTML = '<p class="empty-note">Select an account to manage its tasks.</p>';
    return;
  }

  const tasks = tasksFor();
  node.innerHTML = tasks.length
    ? tasks.map((task) => `<div class="account-task${task.done ? " done" : ""}" data-task-id="${escapeHtml(task.id)}">
        <button class="task-check" type="button" aria-label="${task.done ? "Mark task incomplete" : "Mark task complete"}" aria-pressed="${task.done}">
          ${ICONS.check}
        </button>
        <span class="task-text">${escapeHtml(task.text)}</span>
        <button class="task-delete" type="button" aria-label="Delete task" title="Delete task">
          <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="M4.5 6.5h11"></path><path d="M8 3.8h4"></path><path d="M6 6.5l.7 9.1h6.6l.7-9.1"></path></svg>
        </button>
      </div>`).join("")
    : '<p class="empty-note task-empty">No tasks yet.</p>';
}

function createTask(account, text) {
  const id = String(account?.id ?? account?.account_id ?? "");
  const clean = String(text).trim().replace(/\s+/g, " ").slice(0, 180);
  if (!id || !clean) return null;
  const task = {
    id: `task-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    text: clean,
    done: false
  };
  state.tasksByAccount[id] = [...(state.tasksByAccount[id] ?? []), task];
  saveTasks();
  if (id === String(accountId())) renderAccountTasks();
  return task;
}

function deleteTask(id) {
  const account = String(accountId() ?? "");
  state.tasksByAccount[account] = tasksFor().filter((task) => task.id !== id);
  if (!state.tasksByAccount[account].length) delete state.tasksByAccount[account];
  saveTasks();
  renderAccountTasks();
}

function celebrateTask(row) {
  row.classList.add("just-completed");
  const note = document.createElement("span");
  note.className = "task-celebration";
  note.innerHTML = `<img src="${HENRY_IMAGE}" alt="" aria-hidden="true">Task complete!`;
  row.appendChild(note);
  window.setTimeout(() => {
    note.remove();
    row.classList.remove("just-completed");
  }, reduceMotionQuery.matches ? 500 : 1800);
}

function toggleTask(id, row) {
  const task = tasksFor().find((item) => item.id === id);
  if (!task) return;
  task.done = !task.done;
  saveTasks();
  renderAccountTasks();
  if (task.done) {
    const fresh = $("#account-tasks").querySelector(`[data-task-id="${CSS.escape(id)}"]`);
    if (fresh) celebrateTask(fresh);
  }
}

function showTaskForm() {
  if (!accountId()) return;
  const form = $("#task-form");
  form.hidden = false;
  $("#task-input").focus();
}

function hideTaskForm() {
  const form = $("#task-form");
  form.reset();
  form.hidden = true;
}

/* -------------------------------------------------- task chat commands */

function escapedPattern(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function accountMentionedIn(message) {
  const lower = message.toLowerCase();
  return state.accounts
    .slice()
    .sort((left, right) => accountNameFor(right).length - accountNameFor(left).length)
    .find((account) => lower.includes(accountNameFor(account).toLowerCase())) ?? null;
}

function accountNameFor(account) {
  return String(account?.name ?? account?.company ?? "");
}

function parseTaskCreation(message) {
  const createIntent = /^\s*(?:please\s+)?(?:create|add|make|set up)\s+(?:a\s+)?task\b/i;
  if (!createIntent.test(message)) return null;

  const mentioned = accountMentionedIn(message);
  const account = mentioned ?? state.account;
  if (!account) {
    return { error: "Tell me which account this task belongs to, or select one on the right." };
  }

  let text = message.replace(createIntent, "").trim();
  const name = accountNameFor(account);
  if (mentioned && name) {
    text = text.replace(
      new RegExp(`\\b(?:for|at|on)\\s+${escapedPattern(name)}\\b`, "i"),
      ""
    );
  }
  text = text
    .replace(/^\s*(?:for\s+)?(?:this|the selected|selected)\s+account\b/i, "")
    .replace(/^\s*(?:to|that says?|called|named|:|-)\s*/i, "")
    .replace(/\s+(?:please|thanks?|thank you)[.!]?\s*$/i, "")
    .trim()
    .replace(/[.!]\s*$/, "");

  if (!text) {
    return { error: `What should I add to ${name}'s task list?` };
  }
  return { account, text };
}

function handleTaskCreation(message) {
  const command = parseTaskCreation(message);
  if (!command) return false;

  addMessage("user", message);
  if (command.error) {
    addMessage("henry", command.error);
    return true;
  }

  const task = createTask(command.account, command.text);
  if (!task) {
    addMessage("henry", "I couldn't create that task. Please select an account and try again.");
    return true;
  }
  const name = accountNameFor(command.account);
  addMessage("henry", `Done — I added **${task.text}** to **${name}**.`);
  toast(`Task added to ${name}`);
  return true;
}

/* --------------------------------------------------------------- transport */

async function request(path, payload) {
  const options = payload === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  };
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data.result ?? data;
}

// Henry routes on the message, so a selected task can stop driving the answer.
// Drop the chip when that happens rather than leaving it lit and misleading.
function syncSelectedAsk(result) {
  if (!state.action) return;
  if ((result?.data?.ask?.action ?? null) !== state.action) clearAsk();
}

async function run(path, message, options = {}) {
  if (state.busy) {
    toast("Henry is still working on the last ask 🍌");
    return;
  }
  state.busy = true;
  $("#send").disabled = true;
  addMessage("user", message);
  startThinking();
  try {
    const context = state.account ? { account: state.account } : {};
    const board = taskBoard();
    if (board.length) context.tasks = board;
    if (options.ask) {
      context.ask = {
        id: options.ask.id,
        label: options.ask.label,
        category: options.ask.category.name,
        category_id: options.ask.category.id
      };
    }
    const payload = { message, account_id: accountId(), context };
    if (options.action) payload.action = options.action;
    // A locked action came from a menu click; anything else is only a default
    // that Henry may override when the typed message asks for something else.
    if (options.lock) payload.action_locked = true;
    const result = await request(path, payload);
    stopThinking();
    if (!options.lock) syncSelectedAsk(result);
    addMessage("henry", result?.markdown ?? result?.message ?? result?.response ?? result?.output ?? result);
  } catch (error) {
    stopThinking();
    addMessage("henry", `I hit a snag: **${error.message}**`);
  } finally {
    stopThinking();
    state.busy = false;
    $("#send").disabled = false;
    input.focus();
  }
}

/* -------------------------------------------------------------- task menu */

function matchesFilter(text, term) {
  return text.toLowerCase().includes(term);
}

function askButton(ask, hasAccount) {
  const locked = Boolean(ask.account) && !hasAccount;
  const classes = ["ask"];
  if (state.action === (ask.action ?? ask.id)) classes.push("active");
  if (locked) classes.push("locked");
  const badge = ask.account ? '<span class="req" aria-hidden="true">◆</span>' : "";
  const title = ask.account
    ? `${ask.label} — needs a selected account`
    : `${ask.label} — works without an account`;
  return `<button type="button" class="${classes.join(" ")}" data-ask="${escapeHtml(ask.id)}" title="${escapeHtml(title)}">
    <span class="ask-label">${escapeHtml(ask.label)}</span>${badge}
  </button>`;
}

function workflowButton(workflow) {
  const active = state.workflow === workflow.id && !state.ask ? " current" : "";
  return `<button type="button" class="ask${active}" data-workflow="${escapeHtml(workflow.id)}" title="${escapeHtml(workflow.label)} workflow">
    <span class="ask-label">${escapeHtml(workflow.label)}</span>
  </button>`;
}

function renderMenu() {
  if (!menuNode) return;
  const term = state.askFilter.trim().toLowerCase();
  const hasAccount = Boolean(accountId());

  const groups = [];

  const workflows = term
    ? WORKFLOWS.filter((item) => matchesFilter(`${item.label} ${item.keywords}`, term))
    : WORKFLOWS;
  if (workflows.length) {
    groups.push({ id: "workflows", name: "Workflows", body: workflows.map(workflowButton).join("") });
  }

  ASK_CATALOG.forEach((category) => {
    const asks = term
      ? category.asks.filter((ask) => matchesFilter(`${ask.label} ${ask.keywords ?? ""} ${category.name} ${category.blurb}`, term))
      : category.asks;
    if (!asks.length) return;
    groups.push({ id: category.id, name: category.name, body: asks.map((ask) => askButton(ask, hasAccount)).join("") });
  });

  if (!groups.length) {
    menuNode.innerHTML = `<p class="empty-note">Nothing matches “${escapeHtml(state.askFilter.trim())}”. Try “proposal”, “intel”, or “FAQ”.</p>`;
    return;
  }

  menuNode.innerHTML = groups.map((group) => {
    const open = term ? true : state.openGroups.has(group.id);
    return `<details class="menu-group" data-group="${escapeHtml(group.id)}"${open ? " open" : ""}>
      <summary><span class="menu-name">${escapeHtml(group.name)}</span>${ICONS.caret}</summary>
      <div class="menu-items">${group.body}</div>
    </details>`;
  }).join("");
}

function renderActiveAsk() {
  const node = $("#active-ask");
  if (!node) return;
  if (!state.ask) {
    node.hidden = true;
    node.innerHTML = "";
    return;
  }
  const needsAccount = Boolean(state.ask.account) && !accountId();
  node.hidden = false;
  node.innerHTML = `<span class="active-ask-copy"><strong>${escapeHtml(state.ask.label)}</strong> · ${escapeHtml(state.ask.category.name)}</span>
    ${needsAccount ? '<span class="active-ask-warn">Needs an account</span>' : ""}
    <button type="button" id="clear-ask" title="Clear selected task" aria-label="Clear selected task">${ICONS.close}</button>`;
  $("#clear-ask").addEventListener("click", clearAsk);
}

function clearAsk() {
  state.ask = null;
  state.action = null;
  renderActiveAsk();
  renderMenu();
  input.focus();
}

function selectAsk(id) {
  const ask = ASK_INDEX.get(id);
  if (!ask) return;
  state.ask = ask;
  state.action = ask.action ?? ask.id;
  renderMenu();
  renderActiveAsk();

  if (ask.account && !accountId()) {
    input.value = ask.prompt;
    autosize();
    toast("🍌 This task needs an account — pick one, then press Enter.");
    setDialog("tasks", false);
    setSidebar("right", true);
    $("#account-search")?.focus();
    return;
  }
  input.value = "";
  autosize();
  setDialog("tasks", false);
  run("/api/ask", ask.prompt, { action: state.action, ask, lock: true });
}

function selectWorkflow(id) {
  const workflow = WORKFLOWS.find((item) => item.id === id);
  if (!workflow) return;
  state.workflow = id;
  clearAsk();
  input.value = workflow.prompt;
  autosize();
  renderMenu();
  setDialog("tasks", false);
  input.focus();
}

/* ---------------------------------------------------------------- accounts */

function normalizeAccounts(result) {
  const candidate = result?.accounts ?? result?.items ?? result?.data ?? result;
  if (!Array.isArray(candidate)) return [];
  return candidate.map((item, index) => typeof item === "string"
    ? { id: item, name: item }
    : { id: item.id ?? item.account_id ?? String(index), ...item });
}

function renderAccounts(filter = "") {
  const term = String(filter).toLowerCase();
  const accounts = state.accounts.filter((account) =>
    String(account.name ?? account.company ?? "").toLowerCase().includes(term)
  );
  $("#accounts").innerHTML = accounts.length ? accounts.map((account) => {
    const name = account.name ?? account.company ?? "Unnamed account";
    const detail = account.industry ?? account.stage ?? account.territory ?? "Account";
    const score = account.score ?? account.priority_score ?? "";
    const selected = state.account?.id === account.id;
    return `<button type="button" class="filter-row" data-id="${escapeHtml(account.id)}" aria-pressed="${selected}">
      ${ICONS.check}<span class="filter-text">${escapeHtml(name)}<small>${escapeHtml(detail)}</small></span>
      ${score !== "" ? `<span class="score">${escapeHtml(score)}</span>` : ""}
    </button>`;
  }).join("") : '<p class="empty-note">No accounts found.</p>';
}

function selectAccount(id) {
  const account = state.accounts.find((item) => String(item.id) === id) ?? null;
  // Clicking the selected account again clears the context.
  state.account = state.account?.id === account?.id ? null : account;
  hideTaskForm();
  $("#selected-context").textContent = accountName() ?? "No account selected";
  renderAccounts($("#account-search").value);
  renderMenu();
  renderActiveAsk();
  renderAccountPanel();
  renderSelectedAccount();
  if (state.account) {
    focusAccountQuickView();
    loadAccountQuickView(state.account);
  }
  toast(state.account ? `Context: ${accountName()}` : "Account context cleared");
}

async function loadAccounts() {
  $("#accounts").innerHTML = '<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>';
  try {
    state.accounts = normalizeAccounts(await request("/api/accounts"));
    renderAccounts($("#account-search")?.value ?? "");
  } catch (error) {
    $("#accounts").innerHTML = `<p class="empty-note">${escapeHtml(error.message)}</p>`;
  }
}

function autosize() {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 168)}px`;
}

/* ------------------------------------------------------------------ events */

menuNode?.addEventListener("click", (event) => {
  const ask = event.target.closest("button.ask[data-ask]");
  if (ask) {
    selectAsk(ask.dataset.ask);
    return;
  }
  const workflow = event.target.closest("button.ask[data-workflow]");
  if (workflow) selectWorkflow(workflow.dataset.workflow);
});

menuNode?.addEventListener("toggle", (event) => {
  const group = event.target;
  if (!(group instanceof HTMLDetailsElement)) return;
  if (state.askFilter.trim()) return;
  if (group.open) state.openGroups.add(group.dataset.group);
  else state.openGroups.delete(group.dataset.group);
}, true);

historyNode?.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-chat]");
  if (!button) return;
  openChat(button.dataset.chat);
  if (mobileQuery.matches) setSidebar("left", false);
});

conversation.addEventListener("click", async (event) => {
  const prompt = event.target.closest("[data-prompt]");
  if (prompt) {
    clearAsk();
    input.value = prompt.dataset.prompt;
    autosize();
    input.focus();
    return;
  }
  const copy = event.target.closest("button.copy-answer");
  if (!copy) return;
  const source = answerSource.get(copy.closest(".message")) ?? "";
  try {
    await navigator.clipboard.writeText(source);
    toast("Answer copied");
  } catch (error) {
    toast("Copy blocked by the browser");
  }
});

$("#ask-search").addEventListener("input", (event) => {
  state.askFilter = event.target.value;
  renderMenu();
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;
  if (handleTaskCreation(message)) {
    input.value = "";
    input.style.height = "auto";
    return;
  }
  input.value = "";
  input.style.height = "auto";
  // Everything typed goes to the router so the message decides the answer, with
  // any selected task passed along only as a fallback.
  run("/api/chat", message, { action: state.action, ask: state.ask });
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});
input.addEventListener("input", autosize);

$("#account-search").addEventListener("input", (event) => renderAccounts(event.target.value));
$("#refresh").addEventListener("click", loadAccounts);

$("#accounts").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-id]");
  if (button) selectAccount(button.dataset.id);
});

$("#add-task").addEventListener("click", showTaskForm);
$("#cancel-task").addEventListener("click", hideTaskForm);
$("#task-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const task = createTask(state.account, $("#task-input").value);
  if (!task) return;
  hideTaskForm();
  toast("Task added");
});

$("#account-tasks").addEventListener("click", (event) => {
  const row = event.target.closest("[data-task-id]");
  if (!row) return;
  if (event.target.closest(".task-delete")) {
    deleteTask(row.dataset.taskId);
    toast("Task deleted");
    return;
  }
  if (event.target.closest(".task-check")) toggleTask(row.dataset.taskId, row);
});

$("#attach-account").addEventListener("click", () => {
  setSidebar("right", true);
  $("#account-search")?.focus();
});

$("#new-chat").addEventListener("click", startNewChat);

$("#toggle-left").addEventListener("click", () => toggleSidebar("left"));
$("#toggle-right").addEventListener("click", () => toggleSidebar("right"));
$("#open-tasks").addEventListener("click", () => setDialog("tasks", true));
$("#open-tasks-empty").addEventListener("click", () => setDialog("tasks", true));
$("#open-accounts-empty").addEventListener("click", () => setDialog("right", true));
$("#close-tasks").addEventListener("click", () => setDialog("tasks", false));
$("#close-right").addEventListener("click", () => setDialog("right", false));
$("#clear-account").addEventListener("click", () => {
  if (accountId()) selectAccount(String(accountId()));
});
$("#selected-account-chip").addEventListener("click", () => setDialog("right", true));

scrim?.addEventListener("click", () => {
  setDialog("tasks", false);
  setDialog("right", false);
  if (mobileQuery.matches) setSidebar("left", false);
});

themeButton?.addEventListener("click", () => {
  const current = root.dataset.themePref ?? "system";
  const next = THEME_CHOICES[(THEME_CHOICES.indexOf(current) + 1) % THEME_CHOICES.length];
  applyTheme(next, true);
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  if (root.dataset.tasks === "open") setDialog("tasks", false);
  if (root.dataset.right === "open") setDialog("right", false);
  if (mobileQuery.matches && root.dataset.left === "open") setSidebar("left", false);
});

const onSchemeChange = () => {
  if (root.dataset.themePref === "system") applyTheme("system", false);
};
if (typeof darkQuery.addEventListener === "function") darkQuery.addEventListener("change", onSchemeChange);
else if (typeof darkQuery.addListener === "function") darkQuery.addListener(onSchemeChange);

if (typeof mobileQuery.addEventListener === "function") mobileQuery.addEventListener("change", updateScrim);
else if (typeof mobileQuery.addListener === "function") mobileQuery.addListener(updateScrim);

/* -------------------------------------------------------------------- boot */

applyTheme(readStore(THEME_KEY) ?? "system", false);
state.tasksByAccount = readTasks();
setSidebar("left", root.dataset.left === "open", false);
setSidebar("right", root.dataset.right === "open", false);
renderMenu();
renderActiveAsk();
renderHistory();
renderAccountPanel();
renderSelectedAccount();
updateWelcome();
loadAccounts();

window.requestAnimationFrame(() => window.requestAnimationFrame(() => root.classList.remove("boot")));
