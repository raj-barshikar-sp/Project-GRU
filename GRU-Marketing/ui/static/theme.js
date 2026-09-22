const THEME_KEY = "gru-theme";
let themeReady = false;

function readTheme() {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    /* private mode */
  }
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function paintTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    /* private mode */
  }
  const next = theme === "dark" ? "light" : "dark";
  for (const button of document.querySelectorAll("[data-theme-toggle]")) {
    button.setAttribute("aria-label", `Switch to ${next} mode`);
    button.title = `Switch to ${next} mode`;
    button.dataset.state = theme === "dark" ? "b" : "a";
  }
  document.dispatchEvent(new CustomEvent("james-theme", { detail: theme }));
}

function applyTheme(theme, options = {}) {
  const animate = Boolean(options.animate);
  const allowMotion =
    animate &&
    themeReady &&
    typeof document.startViewTransition === "function" &&
    !matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!allowMotion) {
    paintTheme(theme);
    return;
  }
  const root = document.documentElement;
  root.classList.add("theme-vt");
  const update = () => paintTheme(theme);
  const done = () => root.classList.remove("theme-vt");
  let transition;
  try {
    transition = document.startViewTransition({ types: ["theme"], update });
  } catch {
    transition = document.startViewTransition(update);
  }
  if (transition?.finished?.finally) transition.finished.finally(done);
  else done();
}

function bootTheme() {
  applyTheme(readTheme(), { animate: false });
  themeReady = true;
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-theme-toggle]");
    if (!button) return;
    applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark", {
      animate: true,
    });
  });
}

bootTheme();
