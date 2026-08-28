(function () {
  "use strict";

  const sources = [
    ["index", "pages/index-state.html"],
    ["reads", "pages/reads.html"],
    ["report", "pages/report.html"]
  ];
  const views = {};
  let ready = false;
  let readyPromise = null;

  function viewFromHref(href) {
    const value = String(href || "").toLowerCase();
    if (value.includes("index-state")) return "index";
    if (value.includes("reads")) return "reads";
    if (value.includes("report")) return "report";
    return "workspace";
  }

  function refreshIcons(root) {
    if (window.lucide && typeof window.lucide.createIcons === "function" && root.querySelector("i[data-lucide]")) {
      window.lucide.createIcons({ root: root });
    }
  }

  async function loadViews() {
    const workspace = document.querySelector(".app-shell");
    if (!workspace) {
      ready = true;
      return;
    }
    workspace.classList.add("app-view");
    workspace.dataset.view = "workspace";
    views.workspace = workspace;
    for (const item of sources) {
      const response = await fetch(item[1], { cache: "no-store" });
      if (!response.ok) throw new Error("无法加载视图资源：" + item[1]);
      const parsed = new DOMParser().parseFromString(await response.text(), "text/html");
      const shell = parsed.querySelector(".secondary-shell");
      if (!shell) throw new Error("视图资源结构无效：" + item[1]);
      shell.classList.add("app-view");
      shell.dataset.view = item[0];
      shell.hidden = true;
      document.body.insertBefore(shell, document.querySelector("#toast"));
      views[item[0]] = shell;
      refreshIcons(shell);
    }
    ready = true;
    window.dispatchEvent(new CustomEvent("dna:views-ready"));
  }

  function navigate(viewName) {
    if (!ready || !views[viewName]) return false;
    Object.keys(views).forEach(function (name) { views[name].hidden = name !== viewName; });
    document.body.classList.toggle("run-page", viewName === "workspace");
    history.replaceState({ view: viewName }, "", viewName === "workspace" ? "#workspace" : "#" + viewName);
    window.scrollTo(0, 0);
    window.dispatchEvent(new CustomEvent("dna:view-change", { detail: { view: viewName } }));
    return true;
  }

  function start() {
    if (readyPromise) return readyPromise;
    readyPromise = loadViews().catch(function (error) {
      ready = false;
      window.dispatchEvent(new CustomEvent("dna:views-error", { detail: { message: error.message || String(error) } }));
      throw error;
    });
    return readyPromise;
  }

  window.DnaRouter = {
    start: start,
    retry: function () { readyPromise = null; return start(); },
    navigate: navigate,
    navigateHref: function (href) { return navigate(viewFromHref(href)); },
    isReady: function () { return ready; }
  };

  start().catch(function () {});
}());
