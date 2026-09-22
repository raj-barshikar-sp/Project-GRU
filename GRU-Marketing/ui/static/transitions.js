(() => {
  const root = document.documentElement;

  function tokenMs(name, fallback) {
    const value = parseFloat(getComputedStyle(root).getPropertyValue(name));
    return Number.isFinite(value) ? value : fallback;
  }

  function tokenEase(name, fallback) {
    return getComputedStyle(root).getPropertyValue(name).trim() || fallback;
  }

  function reducedMotion() {
    return matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function closeMs(node, fallback) {
    if (node?.classList.contains("t-modal")) return tokenMs("--modal-close-dur", fallback);
    if (node?.classList.contains("t-dropdown")) return tokenMs("--dropdown-close-dur", fallback);
    if (node?.classList.contains("t-panel")) return tokenMs("--panel-close-dur", fallback);
    if (node?.classList.contains("t-banner")) return tokenMs("--duration-quick", 180);
    return fallback;
  }

  function openSurface(node) {
    if (!node) return;
    node.classList.remove("is-closing");
    node.classList.add("is-open");
  }

  function closeSurface(node, hide) {
    if (!node) return;
    node.classList.remove("is-open");
    node.classList.add("is-closing");
    const wait = reducedMotion() ? 0 : closeMs(node, 150);
    window.setTimeout(() => {
      node.classList.remove("is-closing");
      hide?.(node);
    }, wait);
  }

  function setDigits(group, str) {
    if (!group) return;
    group.classList.remove("is-animating");
    group.replaceChildren();
    const chars = String(str).split("");
    chars.forEach((ch, i) => {
      const span = document.createElement("span");
      span.className = "t-digit";
      span.textContent = ch;
      if (i === chars.length - 2) span.dataset.stagger = "1";
      else if (i === chars.length - 1) span.dataset.stagger = "2";
      group.append(span);
    });
    void group.offsetHeight;
    group.classList.add("is-animating");
  }

  function swapText(el, next) {
    if (!el) return;
    if (el.textContent === next) return;
    if (reducedMotion() || !el.classList.contains("t-text-swap")) {
      el.textContent = next;
      return;
    }
    const dur = tokenMs("--text-swap-dur", 150);
    el.classList.add("is-exit");
    window.setTimeout(() => {
      el.textContent = next;
      el.classList.remove("is-exit");
      el.classList.add("is-enter-start");
      void el.offsetHeight;
      el.classList.remove("is-enter-start");
    }, dur);
  }

  function shake(input) {
    if (!input) return;
    input.classList.add("is-error");
    input.classList.remove("is-shaking");
    void input.offsetWidth;
    input.classList.add("is-shaking");
    const shakeMs = tokenMs("--shake-dur-a", 80) * 2 + tokenMs("--shake-dur-b", 60) * 2;
    window.setTimeout(() => input.classList.remove("is-shaking"), shakeMs + 20);
    window.setTimeout(() => input.classList.remove("is-error"), shakeMs + tokenMs("--revert-hold", 3000));
  }

  let toastTimer = 0;
  function showToast(message) {
    const toast = document.getElementById("app-toast");
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add("is-open");
    toast.dataset.open = "true";
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => {
      toast.classList.remove("is-open");
      toast.dataset.open = "false";
    }, 3200);
  }

  function bindAvatarGroup(rootEl) {
    if (!rootEl) return;
    const avatars = [...rootEl.querySelectorAll(".t-avatar")];
    if (!avatars.length) return;
    const num = (name, fb) => tokenMs(name, fb);
    function setShifts(activeIdx, phase) {
      const lift = parseFloat(getComputedStyle(root).getPropertyValue("--avatar-lift")) || -4;
      const falloff = num("--avatar-falloff", 0.45);
      const scale = num("--avatar-scale", 1.05);
      const tf =
        phase === "out"
          ? tokenEase("--avatar-ease-out", "cubic-bezier(0.34, 3.85, 0.64, 1)")
          : tokenEase("--avatar-ease-in", "cubic-bezier(0.22, 1, 0.36, 1)");
      avatars.forEach((el, i) => {
        el.style.transitionTimingFunction = tf;
        if (activeIdx == null) {
          el.style.setProperty("--shift", "0px");
          el.style.setProperty("--scale-active", "1");
          return;
        }
        const d = Math.abs(i - activeIdx);
        el.style.setProperty("--shift", (lift * Math.pow(falloff, d)).toFixed(3) + "px");
        el.style.setProperty("--scale-active", i === activeIdx ? String(scale) : "1");
      });
    }
    avatars.forEach((el, i) => el.addEventListener("mouseenter", () => setShifts(i, "in")));
    rootEl.addEventListener("mouseleave", () => setShifts(null, "out"));
  }

  function moveTabPill(bar, tab, animate) {
    const pill = bar?.querySelector(".t-tabs-pill");
    if (!bar || !pill || !tab) return;
    if (!animate) {
      const prev = pill.style.transition;
      pill.style.transition = "none";
      pill.style.transform = `translateX(${tab.offsetLeft}px)`;
      pill.style.width = `${tab.offsetWidth}px`;
      void pill.offsetWidth;
      pill.style.transition = prev;
    } else {
      pill.style.transform = `translateX(${tab.offsetLeft}px)`;
      pill.style.width = `${tab.offsetWidth}px`;
    }
  }

  function bindTabs(bar) {
    if (!bar) return;
    const tabs = [...bar.querySelectorAll(".t-tab")];
    const active = () => tabs.find((t) => t.getAttribute("aria-selected") === "true") || tabs[0];
    requestAnimationFrame(() => moveTabPill(bar, active(), false));
    window.addEventListener("resize", () => moveTabPill(bar, active(), false));
    return { moveTo: (tab, animate) => moveTabPill(bar, tab, animate) };
  }

  function setThinkLine(box, text, { shimmer = true } = {}) {
    if (!box) return;
    let live = box.querySelector(".t-think-text:not(.is-exit)");
    if (!live) {
      live = document.createElement("span");
      live.className = "t-think-text";
      box.append(live);
    }
    live.textContent = text;
    live.setAttribute("data-text", text);
    box.classList.toggle("is-done", !shimmer);
  }

  function swapThinkLine(box, text) {
    if (!box) return;
    const live = box.querySelector(".t-think-text:not(.is-exit)");
    if (!live || reducedMotion()) {
      setThinkLine(box, text, { shimmer: box.dataset.cycle === "true" });
      return;
    }
    const swap = tokenMs("--think-swap", 150);
    const gap = tokenMs("--think-gap", 50);
    live.classList.add("is-exit");
    const next = document.createElement("span");
    next.className = "t-think-text is-enter-start";
    next.textContent = text;
    next.setAttribute("data-text", text);
    box.append(next);
    const release = () => {
      void next.offsetWidth;
      next.classList.remove("is-enter-start");
    };
    if (gap > 0) window.setTimeout(release, gap);
    else release();
    window.setTimeout(() => live.remove(), swap + gap);
  }

  function startThinking(box, text = "Thinking") {
    if (!box) return;
    box.dataset.cycle = "true";
    box.classList.remove("is-done");
    window.clearTimeout(box._thinkTimer);
    setThinkLine(box, text, { shimmer: true });
  }

  function stopThinking(box, text) {
    if (!box) return;
    box.dataset.cycle = "false";
    window.clearTimeout(box._thinkTimer);
    box.classList.add("is-done");
    if (text) swapThinkLine(box, text);
    else {
      const live = box.querySelector(".t-think-text:not(.is-exit)");
      if (live) live.setAttribute("data-text", live.textContent || "");
    }
    window.setTimeout(() => {
      box.querySelectorAll(".t-think-text.is-exit").forEach((node) => node.remove());
    }, tokenMs("--think-swap", 150) + tokenMs("--think-gap", 50));
  }

  function followReasoning(box) {
    const scroller = box?.classList.contains("reasoning-body")
      ? box
      : box?.querySelector(".reasoning-body") || box;
    if (!scroller) return;
    scroller.scrollTop = scroller.scrollHeight;
  }

  function paintStreamWords(container, shown, caret) {
    const parts = shown.match(/\S+\s*/g) || (shown ? [shown] : []);
    const existing = [...container.querySelectorAll(".t-stream-w")];
    if (existing.length > parts.length) {
      container.replaceChildren();
      existing.length = 0;
    }
    for (let i = 0; i < parts.length; i += 1) {
      let span = existing[i];
      if (!span) {
        span = document.createElement("span");
        span.className = "t-stream-w";
        container.append(span);
        void span.offsetWidth;
        span.classList.add("is-in");
      }
      span.textContent = parts[i];
    }
    if (caret) container.append(caret);
  }

  function showStagger(block) {
    if (!block) return;
    block.classList.remove("is-hiding");
    block.classList.remove("is-shown");
    void block.offsetHeight;
    block.classList.add("is-shown");
  }

  function enter(node, cls) {
    if (!node) return;
    node.classList.add(cls || "t-pop");
    if (reducedMotion()) {
      node.classList.add("is-in");
      return;
    }
    node.classList.remove("is-in", "is-out");
    void node.offsetWidth;
    node.classList.add("is-in");
  }

  function leave(node, hide) {
    if (!node) return;
    if (reducedMotion()) {
      hide?.(node);
      return;
    }
    node.classList.add("is-out");
    node.classList.remove("is-in");
    window.setTimeout(() => hide?.(node), tokenMs("--duration-quick", 150));
  }

  function revealRows(nodes, options = {}) {
    const list = [...(nodes || [])];
    const stagger = Boolean(options.stagger);
    list.forEach((node, i) => {
      if (!node) return;
      node.classList.add("t-row");
      if (reducedMotion()) {
        node.classList.add("is-in");
        return;
      }
      node.classList.remove("is-in");
      const wait = stagger ? Math.min(i, 7) * 28 : 0;
      window.requestAnimationFrame(() => {
        window.setTimeout(() => node.classList.add("is-in"), wait);
      });
    });
  }

  function enterSeen(container, nodes) {
    if (!container) return;
    const seen = container._tSeen || new Set();
    const next = new Set();
    for (const node of nodes || []) {
      const id = node.dataset.id || node.dataset.turn || "";
      if (id) next.add(id);
      if (!id || !seen.has(id)) enter(node, "t-row");
      else {
        node.classList.add("t-row", "is-in");
      }
    }
    container._tSeen = next;
  }

  function crossFade(container, nextFn) {
    if (!container) {
      nextFn?.();
      return;
    }
    if (reducedMotion()) {
      nextFn?.();
      return;
    }
    const dur = tokenMs("--duration-quick", 180);
    container.classList.add("t-cross-fade", "is-out");
    window.setTimeout(() => {
      nextFn?.();
      container.classList.remove("is-out");
      void container.offsetWidth;
      container.classList.add("is-in");
      window.setTimeout(() => {
        container.classList.remove("t-cross-fade", "is-in");
      }, dur);
    }, dur);
  }

  function bindPageOpen() {
    if (reducedMotion()) return;
    if (typeof document.startViewTransition === "function") return;
    document.documentElement.classList.add("t-page-enter");
  }

  function withViewTransition(fn) {
    if (!fn) return;
    if (
      reducedMotion() ||
      typeof document.startViewTransition !== "function"
    ) {
      fn();
      return;
    }
    document.startViewTransition(fn);
  }

  function bootLanding() {
    bindPageOpen();
    const stagger = document.querySelector(".landing-hero-copy.t-stagger");
    if (stagger) requestAnimationFrame(() => showStagger(stagger));
    bindAvatarGroup(document.querySelector(".landing-cap-grid.t-avatar-group"));
    document.querySelectorAll(".landing-faq.t-acc").forEach((item) => {
      const trigger = item.querySelector(".t-acc-head, .landing-faq-trigger");
      if (!trigger) return;
      trigger.addEventListener("click", () => {
        const open = item.getAttribute("data-open") === "true";
        item.setAttribute("data-open", String(!open));
        item.classList.toggle("is-open", !open);
        trigger.setAttribute("aria-expanded", String(!open));
      });
    });
  }

  document.addEventListener("DOMContentLoaded", bootLanding);

  window.JamesMotion = {
    tokenMs,
    tokenEase,
    reducedMotion,
    openSurface,
    closeSurface,
    setDigits,
    swapText,
    shake,
    showToast,
    bindAvatarGroup,
    bindTabs,
    moveTabPill,
    startThinking,
    stopThinking,
    setThinkLine,
    followReasoning,
    paintStreamWords,
    showStagger,
    enter,
    leave,
    revealRows,
    enterSeen,
    crossFade,
    bindPageOpen,
    withViewTransition,
  };
})();
