(() => {
  let activeRole = "bob";
  const artifactsKey = () => `gru-artifacts-${activeRole}`;
  const KINDS = {
    email: "Email",
    talking_points: "Talking points",
    merge_instruction: "Merge",
    ask: "Ask",
    work_order: "Work order",
    other: "Note",
  };

  const state = {
    tab: "all",
    query: "",
    kind: "",
    grid: false,
    openId: "",
    panelTab: "preview",
    expanded: false,
  };

  function loadArtifacts() {
    try {
      const raw = JSON.parse(localStorage.getItem(artifactsKey()) || "[]");
      return Array.isArray(raw) ? raw : [];
    } catch {
      return [];
    }
  }

  function saveArtifacts(list) {
    localStorage.setItem(artifactsKey(), JSON.stringify(list.slice(0, 40)));
  }

  function upsertArtifacts(incoming, chatId) {
    if (!incoming?.length) return [];
    const list = loadArtifacts();
    const saved = [];
    for (const item of incoming) {
      const title = item.title || "Untitled";
      const body = item.body || "";
      const kind = item.kind || "other";
      const same = list.find((row) => row.title === title && row.kind === kind);
      if (same && same.body === body) {
        if (chatId) same.chatId = chatId;
        saved.push(same);
        continue;
      }
      if (same && same.body !== body) {
        same.versions = [{ body: same.body, created: same.updated || same.created }, ...(same.versions || [])].slice(0, 8);
        same.body = body;
        same.updated = new Date().toISOString();
        same.chatId = chatId || same.chatId || "";
        list.splice(list.indexOf(same), 1);
        list.unshift(same);
        saved.push(same);
        continue;
      }
      const row = {
        id: item.id || crypto.randomUUID(),
        kind,
        title,
        body,
        created: new Date().toISOString(),
        updated: new Date().toISOString(),
        source: "chat",
        chatId: chatId || "",
        versions: [],
      };
      list.unshift(row);
      saved.push(row);
    }
    saveArtifacts(list);
    renderLibrary();
    return saved;
  }

  function deleteArtifact(id) {
    saveArtifacts(loadArtifacts().filter((item) => item.id !== id));
    if (state.openId === id) closePanel();
    renderLibrary();
  }

  function monthLabel(iso) {
    const date = new Date(iso || Date.now());
    if (Number.isNaN(date.getTime())) return "Earlier";
    return date.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  }

  function filtered() {
    if (state.tab === "shared") return [];
    const q = state.query.trim().toLowerCase();
    return loadArtifacts().filter((item) => {
      if (state.kind && item.kind !== state.kind) return false;
      if (!q) return true;
      return `${item.title} ${item.body} ${item.kind}`.toLowerCase().includes(q);
    });
  }

  function grouped(items) {
    const map = new Map();
    for (const item of items) {
      const key = monthLabel(item.updated || item.created);
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(item);
    }
    return [...map.entries()];
  }

  function renderLibrary() {
    const root = document.getElementById("library-body");
    if (!root) return;
    const items = filtered();
    root.classList.toggle("is-grid", state.grid);
    root.replaceChildren();
    if (state.tab === "shared") {
      root.append(emptyLine("Nothing has been shared with you yet."));
      return;
    }
    if (!items.length) {
      root.append(emptyLine("Paste-ready blocks from chat land here."));
      return;
    }
    for (const [label, rows] of grouped(items)) {
      const group = document.createElement("section");
      group.className = "library-month";
      const heading = document.createElement("h2");
      heading.textContent = label;
      group.append(heading);
      const list = document.createElement("div");
      list.className = "library-rows";
      for (const item of rows) list.append(rowEl(item));
      group.append(list);
      root.append(group);
    }
  }

  function emptyLine(text) {
    const p = document.createElement("p");
    p.className = "library-empty";
    p.textContent = text;
    return p;
  }

  function rowEl(item) {
    const row = document.createElement("article");
    row.className = "library-card";
    const kind = document.createElement("p");
    kind.className = "library-kind";
    kind.textContent = KINDS[item.kind] || "Note";
    const title = document.createElement("h3");
    title.textContent = item.title || "Untitled";
    const preview = document.createElement("p");
    preview.className = "library-preview";
    preview.textContent = String(item.body || "").replace(/\s+/g, " ").slice(0, 140);
    const actions = document.createElement("div");
    actions.className = "library-card-actions";
    actions.append(
      actionBtn("Copy", async (event) => {
        event.stopPropagation();
        try {
          await navigator.clipboard.writeText(item.body || "");
        } catch {
          /* blocked */
        }
      }),
      actionBtn("Open", (event) => {
        event.stopPropagation();
        openPanel(item.id);
      }),
      actionBtn("Delete", (event) => {
        event.stopPropagation();
        deleteArtifact(item.id);
      })
    );
    row.append(kind, title, preview, actions);
    row.addEventListener("click", () => openPanel(item.id));
    return row;
  }

  function actionBtn(label, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "library-card-btn";
    button.textContent = label;
    button.addEventListener("click", onClick);
    return button;
  }

  function openPanel(id, options = {}) {
    const item = loadArtifacts().find((row) => row.id === id);
    const panel = document.getElementById("artifact-panel");
    if (!item || !panel) return;
    state.openId = id;
    state.panelTab = "preview";
    state.expanded = Boolean(options.expanded);
    panel.hidden = false;
    panel.classList.toggle("is-wide", state.expanded);
    document.getElementById("artifact-panel-title").textContent = item.title || "Artifact";
    paintPanelBody(item);
    const versions = document.getElementById("artifact-versions");
    const versionList = document.getElementById("artifact-version-list");
    const older = item.versions || [];
    versions.hidden = !older.length;
    versionList.replaceChildren();
    older.forEach((entry, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "library-card-btn";
      button.textContent = `Version ${older.length - index}`;
      button.addEventListener("click", () => {
        document.getElementById("artifact-panel-body").textContent = entry.body || "";
      });
      versionList.append(button);
    });
    for (const tab of panel.querySelectorAll("[data-panel-tab]")) {
      tab.classList.toggle("is-on", tab.dataset.panelTab === "preview");
    }
    window.__onOpenArtifact?.(item, state.expanded);
  }

  function paintPanelBody(item) {
    const body = document.getElementById("artifact-panel-body");
    if (!body) return;
    body.classList.toggle("is-source", state.panelTab === "source");
    body.textContent = item.body || "";
  }

  function closePanel() {
    const panel = document.getElementById("artifact-panel");
    if (panel) {
      panel.hidden = true;
      panel.classList.remove("is-wide");
    }
    state.openId = "";
    state.expanded = false;
  }

  function bindLibrary() {
    const search = document.getElementById("library-search");
    const kind = document.getElementById("library-kind");
    const layout = document.getElementById("library-layout");
    search?.addEventListener("input", () => {
      state.query = search.value;
      renderLibrary();
    });
    kind?.addEventListener("change", () => {
      state.kind = kind.value;
      renderLibrary();
    });
    layout?.addEventListener("click", () => {
      state.grid = !state.grid;
      layout.textContent = state.grid ? "List" : "Grid";
      renderLibrary();
    });
    document.querySelectorAll("[data-lib-tab]").forEach((tab) => {
      tab.addEventListener("click", () => {
        state.tab = tab.dataset.libTab;
        document.querySelectorAll("[data-lib-tab]").forEach((node) => {
          const on = node === tab;
          node.classList.toggle("is-on", on);
          node.setAttribute("aria-selected", String(on));
        });
        renderLibrary();
      });
    });
    document.getElementById("close-artifact-panel")?.addEventListener("click", closePanel);
    document.getElementById("artifact-copy")?.addEventListener("click", async () => {
      const item = loadArtifacts().find((row) => row.id === state.openId);
      if (!item) return;
      try {
        await navigator.clipboard.writeText(item.body || "");
      } catch {
        /* blocked */
      }
    });
    document.getElementById("artifact-expand")?.addEventListener("click", () => {
      const item = loadArtifacts().find((row) => row.id === state.openId);
      if (!item) return;
      openPanel(item.id, { expanded: !state.expanded });
    });
    document.querySelectorAll("[data-panel-tab]").forEach((tab) => {
      tab.addEventListener("click", () => {
        state.panelTab = tab.dataset.panelTab;
        document.querySelectorAll("[data-panel-tab]").forEach((node) => {
          node.classList.toggle("is-on", node === tab);
        });
        const item = loadArtifacts().find((row) => row.id === state.openId);
        if (!item) return;
        const body = document.getElementById("artifact-panel-body");
        body.classList.toggle("is-source", state.panelTab === "source");
        body.textContent = item.body || "";
      });
    });
    const handle = document.getElementById("artifact-panel-resize");
    handle?.addEventListener("mousedown", (event) => {
      event.preventDefault();
      const panel = document.getElementById("artifact-panel");
      if (!panel) return;
      const startX = event.clientX;
      const startW = panel.getBoundingClientRect().width;
      const move = (next) => {
        const width = Math.min(Math.max(280, startW + (startX - next.clientX)), Math.round(window.innerWidth * 0.8));
        panel.style.width = `${width}px`;
      };
      const up = () => {
        window.removeEventListener("mousemove", move);
        window.removeEventListener("mouseup", up);
      };
      window.addEventListener("mousemove", move);
      window.addEventListener("mouseup", up);
    });
    renderLibrary();
  }

  window.BobArtifacts = {
    setRole(role) {
      activeRole = ["bob", "james", "stuart", "henry"].includes(role) ? role : "bob";
      if (activeRole === "bob" && !localStorage.getItem(artifactsKey())) {
        const legacy = localStorage.getItem("gru-artifacts");
        if (legacy) localStorage.setItem(artifactsKey(), legacy);
      }
      state.openId = "";
      closePanel();
      renderLibrary();
    },
    load: loadArtifacts,
    upsert: upsertArtifacts,
    remove: deleteArtifact,
    render: renderLibrary,
    open: openPanel,
    close: closePanel,
    kinds: KINDS,
  };
  window.renderSidebarArtifacts = () => renderLibrary();
  bindLibrary();
})();
