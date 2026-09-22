(() => {
  const ARTIFACTS_KEY = "gru-artifacts";
  const ARTIFACTS_LIMIT = 80;
  const KIND_LABELS = {
    email: "Email",
    talking_points: "Talking points",
    merge_instruction: "Merge",
    ask: "Ask",
    work_order: "Work order",
    other: "Note",
  };

  let tab = "all";
  let query = "";
  let kindFilter = "";
  let layout = "list";
  let openMenuId = "";
  let paneId = "";
  let paneVersion = 0;
  let paneMode = "preview";
  let paneExpanded = false;
  const PANE_W_KEY = "gru-artifact-pane-w";
  const PANE_MIN = 320;

  function loadStored() {
    try {
      const raw = JSON.parse(localStorage.getItem(ARTIFACTS_KEY) || "[]");
      return Array.isArray(raw) ? raw.map(normalize).filter((item) => item.id) : [];
    } catch {
      return [];
    }
  }

  function saveStored(items) {
    localStorage.setItem(ARTIFACTS_KEY, JSON.stringify(items.slice(0, ARTIFACTS_LIMIT)));
  }

  function fingerprint(title, kind, body) {
    return `${title || ""}|${kind || "other"}|${String(body || "").slice(0, 24)}`;
  }

  function normalize(item) {
    if (!item || typeof item !== "object") return { id: "" };
    const title = item.title || "Untitled";
    const kind = item.kind || "other";
    const body = item.body || "";
    const created = item.created || new Date().toISOString();
    const versions =
      Array.isArray(item.versions) && item.versions.length
        ? item.versions.map((row, index) => ({
            n: row.n || index + 1,
            body: row.body || "",
            created: row.created || created,
          }))
        : [{ n: 1, body, created }];
    const latest = versions[versions.length - 1];
    return {
      id: item.id || fingerprint(title, kind, latest.body),
      kind,
      title,
      body: latest.body,
      created,
      updated: item.updated || latest.created || created,
      source: item.source || "chat",
      chatId: item.chatId || "",
      versions,
    };
  }

  function mergeSeed(seed) {
    const seen = new Set();
    const items = [];
    for (const item of [...loadStored(), ...(seed || []).map(normalize)]) {
      if (!item.id || seen.has(item.id)) continue;
      seen.add(item.id);
      items.push(item);
    }
    return items.slice(0, ARTIFACTS_LIMIT);
  }

  function matchExisting(list, item) {
    if (item.id) {
      const byId = list.find((row) => row.id === item.id);
      if (byId) return byId;
    }
    return list.find((row) => row.title === item.title && row.kind === (item.kind || "other"));
  }

  function upsertFromChat(artifacts, chatId) {
    if (!artifacts?.length) return [];
    const list = loadStored();
    const stored = [];
    for (const raw of artifacts) {
      const title = raw.title || "Untitled";
      const kind = raw.kind || "other";
      const body = raw.body || "";
      const now = new Date().toISOString();
      const incoming = {
        id: raw.id || "",
        kind,
        title,
        body,
        created: now,
        updated: now,
        source: "chat",
        chatId: chatId || raw.chatId || "",
        versions: [{ n: 1, body, created: now }],
      };
      const existing = matchExisting(list, incoming);
      if (existing) {
        if (existing.body !== body) {
          const n = existing.versions.length + 1;
          existing.versions.push({ n, body, created: now });
          existing.body = body;
          existing.updated = now;
          if (chatId) existing.chatId = chatId;
          list.splice(list.indexOf(existing), 1);
          list.unshift(existing);
        }
        stored.push(existing);
        continue;
      }
      incoming.id = incoming.id || fingerprint(title, kind, body);
      list.unshift(incoming);
      stored.push(incoming);
    }
    saveStored(list);
    renderLibrary();
    if (paneId) paintPane();
    return stored;
  }

  function deleteArtifact(id) {
    saveStored(loadStored().filter((item) => item.id !== id));
    if (paneId === id) closePane();
    renderLibrary();
  }

  function findArtifact(id) {
    return loadStored().find((item) => item.id === id) || null;
  }

  function monthLabel(iso) {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "Unknown";
    return date.toLocaleDateString("en-US", { month: "long", year: "numeric" });
  }

  function editedLabel(iso) {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "Edited";
    return `Edited ${date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    })}`;
  }

  function kindIcon(kind) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "2");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    svg.setAttribute("aria-hidden", "true");
    const paths =
      kind === "email"
        ? ["M4 6h16v12H4z", "M4 6l8 7 8-7"]
        : kind === "talking_points"
          ? ["M8 6h13", "M8 12h13", "M8 18h13", "M3 6h.01", "M3 12h.01", "M3 18h.01"]
          : ["M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z", "M14 3v5h5", "M8 13h8", "M8 17h6"];
    for (const d of paths) {
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", d);
      svg.append(path);
    }
    return svg;
  }

  function looksHtmlDocument(body) {
    const text = String(body || "").trim();
    if (!text) return false;
    if (/^Subject:\s/im.test(text)) return false;
    return /^<!DOCTYPE html/i.test(text) || /^<html[\s>]/i.test(text);
  }

  function parentChatMissing(item) {
    if (!item?.chatId) return true;
    if (typeof window.JamesChat?.hasChat !== "function") return false;
    return !window.JamesChat.hasChat(item.chatId);
  }

  function narrowOverlay() {
    return window.matchMedia("(max-width: 980px)").matches;
  }

  function workspaceEl() {
    return document.getElementById("workspace");
  }

  function applyPaneWidth(px) {
    const shell = workspaceEl();
    if (!shell) return;
    if (!px) {
      shell.style.removeProperty("--artifact-pane-w");
      return;
    }
    shell.style.setProperty("--artifact-pane-w", `${Math.round(px)}px`);
  }

  function loadPaneWidth() {
    try {
      const raw = Number(localStorage.getItem(PANE_W_KEY));
      return Number.isFinite(raw) && raw >= PANE_MIN ? raw : 0;
    } catch {
      return 0;
    }
  }

  function savePaneWidth(px) {
    try {
      localStorage.setItem(PANE_W_KEY, String(Math.round(px)));
    } catch {
      /* quota */
    }
  }

  function paneBounds() {
    const shell = workspaceEl();
    const sidebar = document.getElementById("sidebar");
    const width = shell?.clientWidth || window.innerWidth;
    const side = sidebar?.offsetWidth || 0;
    const max = Math.max(PANE_MIN, Math.min(width * 0.7, width - side - 280));
    return { min: PANE_MIN, max };
  }

  function setExpanded(open) {
    paneExpanded = Boolean(open);
    const shell = workspaceEl();
    const btn = document.getElementById("artifact-pane-expand");
    shell?.classList.toggle("is-artifact-expanded", paneExpanded);
    if (btn) {
      btn.setAttribute("aria-label", paneExpanded ? "Collapse artifact" : "Expand artifact");
      btn.title = paneExpanded ? "Collapse" : "Expand";
      btn.setAttribute("aria-pressed", paneExpanded ? "true" : "false");
      const expandIcon = btn.querySelector(".artifact-icon-expand");
      const collapseIcon = btn.querySelector(".artifact-icon-collapse");
      if (expandIcon) expandIcon.hidden = paneExpanded;
      if (collapseIcon) collapseIcon.hidden = !paneExpanded;
    }
    const handle = document.getElementById("artifact-resize");
    if (handle) handle.hidden = paneExpanded || narrowOverlay();
  }

  function setMode(mode) {
    paneMode = mode === "source" ? "source" : "preview";
    document.querySelectorAll("[data-artifact-mode]").forEach((node) => {
      const on = node.dataset.artifactMode === paneMode;
      node.classList.toggle("is-active", on);
      node.setAttribute("aria-pressed", on ? "true" : "false");
    });
    paintPane();
  }

  async function copyText(text, button) {
    try {
      await navigator.clipboard.writeText(text || "");
      if (button) {
        const prior = button.textContent;
        button.textContent = "Copied";
        setTimeout(() => {
          button.textContent = prior;
        }, 1100);
      }
    } catch {
      /* clipboard blocked */
    }
  }

  function filteredItems() {
    if (tab === "shared") return [];
    const q = query.trim().toLowerCase();
    return loadStored().filter((item) => {
      if (kindFilter && item.kind !== kindFilter) return false;
      if (!q) return true;
      return (
        item.title.toLowerCase().includes(q) ||
        item.body.toLowerCase().includes(q) ||
        (KIND_LABELS[item.kind] || "").toLowerCase().includes(q)
      );
    });
  }

  function grouped(items) {
    const groups = [];
    const index = new Map();
    for (const item of items) {
      const label = monthLabel(item.updated || item.created);
      if (!index.has(label)) {
        index.set(label, []);
        groups.push({ label, items: index.get(label) });
      }
      index.get(label).push(item);
    }
    return groups;
  }

  function closeMenus() {
    openMenuId = "";
    document.querySelectorAll(".artifact-row-menu").forEach((node) => {
      node.hidden = true;
    });
  }

  function renderLibrary() {
    const body = document.getElementById("artifact-library-body");
    if (!body) return;
    body.replaceChildren();
    body.classList.toggle("is-grid", layout === "grid");
    if (tab === "shared") {
      const empty = document.createElement("p");
      empty.className = "artifact-library-empty";
      empty.textContent = "Nothing has been shared with you yet.";
      body.append(empty);
      return;
    }
    const items = filteredItems();
    if (!items.length) {
      const empty = document.createElement("p");
      empty.className = "artifact-library-empty";
      empty.textContent = query || kindFilter
        ? "No artifacts match those filters."
        : "Paste-ready blocks from chat land here.";
      body.append(empty);
      return;
    }
    for (const group of grouped(items)) {
      const heading = document.createElement("h2");
      heading.className = "artifact-library-month";
      heading.textContent = group.label;
      body.append(heading);
      const list = document.createElement("div");
      list.className = layout === "grid" ? "artifact-library-grid" : "artifact-library-list";
      for (const item of group.items) {
        list.append(renderRow(item));
      }
      body.append(list);
    }
  }

  function renderRow(item) {
    const row = document.createElement("article");
    row.className = "artifact-row";
    row.dataset.id = item.id;
    const main = document.createElement("button");
    main.type = "button";
    main.className = "artifact-row-main";
    const icon = document.createElement("span");
    icon.className = "artifact-row-icon";
    icon.append(kindIcon(item.kind));
    const copy = document.createElement("span");
    copy.className = "artifact-row-copy";
    copy.append(Object.assign(document.createElement("strong"), { textContent: item.title }));
    copy.append(Object.assign(document.createElement("span"), { textContent: editedLabel(item.updated) }));
    main.append(icon, copy);
    main.addEventListener("click", () => openPane(item.id));
    const more = document.createElement("button");
    more.type = "button";
    more.className = "artifact-row-more";
    more.setAttribute("aria-label", "Artifact actions");
    more.textContent = "⋮";
    const menu = document.createElement("div");
    menu.className = "artifact-row-menu";
    menu.hidden = openMenuId !== item.id;
    for (const [action, label] of [
      ["copy", "Copy"],
      ["open", "Open"],
      ["delete", "Delete"],
    ]) {
      const option = document.createElement("button");
      option.type = "button";
      option.dataset.action = action;
      option.textContent = label;
      option.addEventListener("click", (event) => {
        event.stopPropagation();
        closeMenus();
        if (action === "copy") copyText(item.body, option);
        else if (action === "open") openPane(item.id);
        else deleteArtifact(item.id);
      });
      menu.append(option);
    }
    more.addEventListener("click", (event) => {
      event.stopPropagation();
      const next = openMenuId === item.id ? "" : item.id;
      closeMenus();
      openMenuId = next;
      menu.hidden = !next;
    });
    row.append(main, more, menu);
    return row;
  }

  function setLibraryOpen(open, options = {}) {
    const library = document.getElementById("artifact-library");
    const workspace = document.getElementById("workspace");
    const nav = document.getElementById("nav-artifacts");
    if (!library || !workspace) return;
    const instant = Boolean(options.instant) || window.JamesMotion?.reducedMotion();
    const params = new URLSearchParams(location.search);
    const syncUrl = () => {
      const queryString = params.toString();
      const next = queryString ? `/chat?${queryString}` : "/chat";
      if (`${location.pathname}${location.search}` !== next) {
        history.replaceState(null, "", next);
      }
    };
    if (open) {
      library.hidden = false;
      workspace.classList.add("is-library-view");
      window.JamesChat?.hideRecents?.();
      nav?.classList.toggle("is-active", true);
      params.set("view", "artifacts");
      params.delete("artifact");
      renderLibrary();
      syncUrl();
      if (instant) {
        library.classList.remove("is-closing");
        library.classList.add("is-open");
      } else {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            if (window.JamesMotion) window.JamesMotion.openSurface(library);
            else library.classList.add("is-open");
          });
        });
      }
      return;
    }
    nav?.classList.toggle("is-active", false);
    if (params.get("view") === "artifacts") params.delete("view");
    const hide = () => {
      library.classList.remove("is-open", "is-closing");
      library.hidden = true;
      workspace.classList.remove("is-library-view");
      syncUrl();
    };
    if (library.hidden || instant || !window.JamesMotion) {
      hide();
      return;
    }
    window.JamesMotion.closeSurface(library, hide);
  }

  function showLibrary(options = {}) {
    closePane({ instant: true });
    setLibraryOpen(true, options);
  }

  function hideLibrary(options = {}) {
    setLibraryOpen(false, options);
  }

  function versionLabel(item, index) {
    const version = item.versions[index];
    const latest = index === item.versions.length - 1;
    const name = `v${version?.n || index + 1}`;
    return latest ? `${name} · Latest` : name;
  }

  function closeVersionMenu() {
    const menu = document.getElementById("artifact-pane-version-menu");
    const btn = document.getElementById("artifact-pane-version-btn");
    btn?.setAttribute("aria-expanded", "false");
    if (!menu || menu.hidden) return;
    const hide = (node) => {
      node.hidden = true;
      node.classList.remove("is-open", "is-closing");
    };
    if (window.JamesMotion?.closeSurface) window.JamesMotion.closeSurface(menu, hide);
    else hide(menu);
  }

  function openVersionMenu() {
    const menu = document.getElementById("artifact-pane-version-menu");
    const btn = document.getElementById("artifact-pane-version-btn");
    if (!menu) return;
    menu.hidden = false;
    btn?.setAttribute("aria-expanded", "true");
    requestAnimationFrame(() => {
      if (window.JamesMotion?.openSurface) window.JamesMotion.openSurface(menu);
      else menu.classList.add("is-open");
    });
  }

  function paintPane() {
    const pane = document.getElementById("artifact-pane");
    const titleEl = document.getElementById("artifact-pane-title");
    const preview = document.getElementById("artifact-pane-preview");
    const item = findArtifact(paneId);
    if (!pane || !item) return;
    titleEl.textContent = item.title;
    const index = Math.min(Math.max(paneVersion, 0), item.versions.length - 1);
    paneVersion = index;
    const version = item.versions[index];
    const btn = document.getElementById("artifact-pane-version-btn");
    const menu = document.getElementById("artifact-pane-version-menu");
    if (btn) {
      btn.textContent = versionLabel(item, index);
      btn.hidden = item.versions.length < 2;
    }
    if (menu) {
      menu.replaceChildren();
      item.versions.forEach((row, i) => {
        const option = document.createElement("button");
        option.type = "button";
        option.role = "menuitem";
        option.className = "artifact-version-option";
        option.textContent = versionLabel(item, i);
        if (i === index) option.setAttribute("aria-current", "true");
        option.addEventListener("click", (event) => {
          event.stopPropagation();
          paneVersion = i;
          closeVersionMenu();
          paintPane();
        });
        menu.append(option);
      });
    }
    preview.replaceChildren();
    if (paneMode === "source") {
      preview.className = "artifact-pane-preview is-code";
      const pre = document.createElement("pre");
      pre.textContent = version.body || "";
      preview.append(pre);
      return;
    }
    preview.className = "artifact-pane-preview is-preview";
    if (window.JamesChat?.renderPreview) {
      window.JamesChat.renderPreview(preview, version.body || "", item.kind);
      return;
    }
    if (looksHtmlDocument(version.body)) {
      const frame = document.createElement("iframe");
      frame.className = "artifact-pane-frame";
      frame.setAttribute("sandbox", "allow-scripts");
      frame.setAttribute("referrerpolicy", "no-referrer");
      frame.title = item.title;
      frame.srcdoc = version.body || "";
      preview.append(frame);
      return;
    }
    const pre = document.createElement("pre");
    pre.textContent = version.body || "";
    preview.append(pre);
  }

  function resolveItem(idOrItem) {
    if (idOrItem && typeof idOrItem === "object") {
      return (idOrItem.id && findArtifact(idOrItem.id)) || normalize(idOrItem);
    }
    return findArtifact(idOrItem);
  }

  function openPane(idOrItem, versionIndex, options = {}) {
    const item = resolveItem(idOrItem);
    if (!item?.id) return;
    hideLibrary({ instant: true });
    paneId = item.id;
    paneVersion = versionIndex == null ? item.versions.length - 1 : versionIndex;
    paneMode = options.mode || "preview";
    const missing = parentChatMissing(item);
    setExpanded(Boolean(options.expanded) || missing);
    const saved = loadPaneWidth();
    if (saved && !paneExpanded) applyPaneWidth(saved);
    document.getElementById("workspace")?.classList.add("is-artifact-open");
    const pane = document.getElementById("artifact-pane");
    if (pane) {
      pane.hidden = false;
      pane.classList.remove("is-closing");
      pane.classList.add("is-open");
    }
    setMode(paneMode);
    if (item.chatId && !missing) window.JamesChat?.openChat(item.chatId);
  }

  function closePane(options = {}) {
    const pane = document.getElementById("artifact-pane");
    const workspace = document.getElementById("workspace");
    const instant = Boolean(options.instant) || window.JamesMotion?.reducedMotion();
    const hide = () => {
      paneId = "";
      paneVersion = 0;
      paneMode = "preview";
      paneExpanded = false;
      workspace?.classList.remove("is-artifact-open", "is-artifact-expanded");
      if (pane) {
        pane.classList.remove("is-open", "is-closing");
        pane.hidden = true;
      }
    };
    if (!pane || pane.hidden || instant || !window.JamesMotion) {
      hide();
      return;
    }
    window.JamesMotion.closeSurface(pane, hide);
  }

  function bindResize() {
    const handle = document.getElementById("artifact-resize");
    if (!handle) return;
    let drag = null;
    handle.addEventListener("pointerdown", (event) => {
      if (event.button !== 0 || paneExpanded || narrowOverlay()) return;
      const pane = document.getElementById("artifact-pane");
      const shell = workspaceEl();
      if (!pane || !shell) return;
      event.preventDefault();
      handle.setPointerCapture(event.pointerId);
      drag = { startX: event.clientX, startW: pane.getBoundingClientRect().width };
      shell.classList.add("is-resizing-artifact");
    });
    handle.addEventListener("pointermove", (event) => {
      if (!drag) return;
      const { min, max } = paneBounds();
      const next = Math.min(max, Math.max(min, drag.startW - (event.clientX - drag.startX)));
      applyPaneWidth(next);
    });
    const stop = (event) => {
      if (!drag) return;
      const pane = document.getElementById("artifact-pane");
      const width = pane?.getBoundingClientRect().width;
      if (width) savePaneWidth(width);
      drag = null;
      workspaceEl()?.classList.remove("is-resizing-artifact");
      try {
        handle.releasePointerCapture(event.pointerId);
      } catch {
        /* already released */
      }
    };
    handle.addEventListener("pointerup", stop);
    handle.addEventListener("pointercancel", stop);
    handle.addEventListener("dblclick", () => {
      applyPaneWidth(0);
      try {
        localStorage.removeItem(PANE_W_KEY);
      } catch {
        /* private mode */
      }
    });
  }

  function chipKind(chip) {
    if (chip?.dataset?.artifactKind) return chip.dataset.artifactKind;
    const named = [...(chip?.classList || [])].find(
      (name) => name.startsWith("artifact-") && name !== "artifact-chip"
    );
    return named ? named.slice("artifact-".length) : "other";
  }

  function itemFromChip(chip) {
    if (!chip) return null;
    const list = loadStored();
    const id = chip.dataset.artifactId;
    if (id) {
      const hit = list.find((row) => row.id === id);
      if (hit) return hit;
    }
    const title = chip.querySelector("strong")?.textContent?.trim() || "";
    if (!title) return null;
    const kind = chipKind(chip);
    return (
      list.find((row) => row.title === title && row.kind === kind) ||
      list.find((row) => row.title === title) ||
      null
    );
  }

  function downloadItem(item) {
    const body = String(item?.body || "");
    if (!body) return;
    const slug =
      String(item.title || "artifact")
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

  function refreshChatChips(root = document) {
    root.querySelectorAll(".artifact-chip").forEach((chip) => {
      const item = itemFromChip(chip);
      const kind = chipKind(chip) || item?.kind || "other";
      chip.dataset.artifactKind = kind;
      if (item?.id) chip.dataset.artifactId = item.id;
      const icon = chip.querySelector(".artifact-chip-icon");
      if (icon) icon.replaceChildren(kindIcon(kind));
    });
  }

  function bindLibrary() {
    const search = document.getElementById("artifact-search");
    const type = document.getElementById("artifact-type-filter");
    const listBtn = document.getElementById("artifact-view-list");
    const gridBtn = document.getElementById("artifact-view-grid");
    document.querySelectorAll("[data-artifact-tab]").forEach((button) => {
      button.addEventListener("click", () => {
        tab = button.dataset.artifactTab;
        document.querySelectorAll("[data-artifact-tab]").forEach((node) => {
          node.classList.toggle("is-active", node === button);
          node.setAttribute("aria-selected", node === button ? "true" : "false");
        });
        renderLibrary();
      });
    });
    search?.addEventListener("input", () => {
      query = search.value;
      renderLibrary();
    });
    type?.addEventListener("change", () => {
      kindFilter = type.value;
      renderLibrary();
    });
    listBtn?.addEventListener("click", () => {
      layout = "list";
      listBtn.setAttribute("aria-pressed", "true");
      listBtn.setAttribute("aria-selected", "true");
      gridBtn?.setAttribute("aria-pressed", "false");
      gridBtn?.setAttribute("aria-selected", "false");
      const bar = listBtn.closest(".artifact-view-toggle");
      window.JamesMotion?.moveTabPill?.(bar, listBtn, true);
      renderLibrary();
    });
    gridBtn?.addEventListener("click", () => {
      layout = "grid";
      gridBtn.setAttribute("aria-pressed", "true");
      gridBtn.setAttribute("aria-selected", "true");
      listBtn?.setAttribute("aria-pressed", "false");
      listBtn?.setAttribute("aria-selected", "false");
      const bar = gridBtn.closest(".artifact-view-toggle");
      window.JamesMotion?.moveTabPill?.(bar, gridBtn, true);
      renderLibrary();
    });
    document.getElementById("nav-artifacts")?.addEventListener("click", (event) => {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      showLibrary();
    });
    document.getElementById("artifact-pane-close")?.addEventListener("click", () => closePane());
    document.getElementById("artifact-pane-expand")?.addEventListener("click", () => {
      setExpanded(!paneExpanded);
    });
    document.querySelectorAll("[data-artifact-mode]").forEach((button) => {
      button.addEventListener("click", () => setMode(button.dataset.artifactMode));
    });
    document.getElementById("artifact-pane-copy")?.addEventListener("click", (event) => {
      const item = findArtifact(paneId);
      const version = item?.versions[paneVersion];
      copyText(version?.body || item?.body || "", event.currentTarget);
    });
    document.getElementById("artifact-pane-version-btn")?.addEventListener("click", (event) => {
      event.stopPropagation();
      const menu = document.getElementById("artifact-pane-version-menu");
      if (!menu || menu.hidden) openVersionMenu();
      else closeVersionMenu();
    });
    bindResize();
    document.addEventListener(
      "click",
      (event) => {
        const download = event.target.closest(".artifact-chip-download");
        if (download) {
          event.preventDefault();
          const rowChip = download.closest(".artifact-chip-row")?.querySelector(".artifact-chip");
          const stored = itemFromChip(rowChip);
          if (stored) downloadItem(stored);
          return;
        }
        const openChip = event.target.closest(".artifact-chip");
        if (!openChip || openChip.closest("#artifact-library")) return;
        event.preventDefault();
        const stored = itemFromChip(openChip);
        if (stored) openPane(stored, undefined, { instant: true });
      },
      true
    );
    const viewBar = document.querySelector(".artifact-view-toggle.t-tabs");
    if (viewBar) window.JamesMotion?.bindTabs?.(viewBar);
    document.addEventListener("click", () => {
      closeMenus();
      closeVersionMenu();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeMenus();
        closeVersionMenu();
        if (paneId) closePane();
        else if (document.getElementById("workspace")?.classList.contains("is-library-view")) {
          hideLibrary();
        }
      }
    });
  }

  function bootFromUrl() {
    const params = new URLSearchParams(location.search);
    const artifact = params.get("artifact");
    if (artifact) openPane(artifact, undefined, { instant: true });
    else if (params.get("view") === "artifacts") showLibrary({ instant: true });
  }

  window.JamesArtifacts = {
    load: loadStored,
    upsertFromChat,
    deleteArtifact,
    kindIcon,
    refreshChatChips,
    openPane,
    closePane,
    showLibrary,
    hideLibrary,
    renderLibrary,
    resyncPane() {
      if (!paneId) return;
      const item = findArtifact(paneId);
      if (!item) return;
      const missing = parentChatMissing(item);
      if (missing) setExpanded(true);
      else if (item.chatId) window.JamesChat?.openChat(item.chatId);
      paintPane();
    },
  };
  window.renderSidebarArtifacts = () => renderLibrary();

  const seeded = mergeSeed(window.__artifactSeed || []);
  if (seeded.length) saveStored(seeded);
  bindLibrary();
  renderLibrary();
  bootFromUrl();
})();
