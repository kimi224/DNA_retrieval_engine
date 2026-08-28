(function () {
  "use strict";

  let modal = null;
  let popover = null;
  let navigationPending = false;
  let startupWatchdog = null;
  let stateReady = Boolean(window.DnaStore && window.DnaStore.snapshot().app);
  let viewsReady = !document.querySelector(".app-shell") || Boolean(window.DnaRouter && window.DnaRouter.isReady());
  let startupCompleted = false;

  function setStartupProgress(value, stage, detail) {
    const overlay = document.querySelector("#startup-overlay");
    const fill = document.querySelector("#startup-progress-fill");
    const stageNode = document.querySelector("#startup-stage");
    const detailNode = document.querySelector("#startup-detail");
    if (overlay) overlay.hidden = false;
    if (fill) fill.style.transform = "scaleX(" + Math.max(0, Math.min(1, value)) + ")";
    if (stageNode && stage) stageNode.textContent = stage;
    if (detailNode && detail) detailNode.textContent = detail;
  }

  function completeStartup() {
    if (!stateReady || !viewsReady || startupCompleted) return;
    startupCompleted = true;
    window.clearTimeout(startupWatchdog);
    setStartupProgress(1, "本地工作区已就绪", "正在进入应用");
    window.setTimeout(function () {
      const overlay = document.querySelector("#startup-overlay");
      if (overlay) overlay.hidden = true;
      document.body.classList.remove("app-booting");
    }, 260);
    if (window.DnaBridge && window.DnaBridge.isConnected()) {
      window.DnaBridge.call("notify_frontend_ready", { views: 4, protocol: window.location.protocol }).catch(function () {});
    }
  }

  function startNavigation(target) {
    if (navigationPending) return;
    navigationPending = true;
    document.body.classList.add("app-booting");
    setStartupProgress(.25, "正在切换工作区", "释放当前页面并恢复本地状态");
    window.setTimeout(function () { window.location.replace(target); }, 20);
  }

  function refreshIcons(root) {
    if (window.lucide && typeof window.lucide.createIcons === "function") {
      const host = root || document;
      if (host.querySelector("i[data-lucide]")) window.lucide.createIcons({ root: host });
    }
  }

  function showToast(message) {
    const target = document.querySelector("#toast");
    if (!target) return;
    target.textContent = message;
    target.classList.add("is-visible");
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(function () { target.classList.remove("is-visible"); }, 2800);
  }

  function closePopover() {
    if (popover) popover.remove();
    popover = null;
  }

  function closeModal() {
    if (!modal) return;
    modal.hidden = true;
    document.body.classList.remove("modal-open");
  }

  function openModal(title, body, labelledBy) {
    closePopover();
    if (!modal) {
      modal = document.createElement("div");
      modal.className = "ui-modal-shell";
      modal.hidden = true;
      modal.innerHTML = '<div class="ui-modal-backdrop" data-modal-close></div><section class="ui-modal" role="dialog" aria-modal="true"><header class="ui-modal-header"><h2></h2><button class="icon-button subtle" type="button" title="关闭" aria-label="关闭" data-modal-close><i data-lucide="x" aria-hidden="true"></i></button></header><div class="ui-modal-body"></div></section>';
      document.body.appendChild(modal);
      modal.addEventListener("click", function (event) {
        if (event.target.closest("[data-modal-close]")) closeModal();
      });
      refreshIcons(modal);
    }
    modal.querySelector("h2").textContent = title;
    modal.querySelector(".ui-modal-body").replaceChildren(body);
    modal.querySelector(".ui-modal").setAttribute("aria-labelledby", labelledBy || "ui-modal-title");
    modal.querySelector("h2").id = labelledBy || "ui-modal-title";
    modal.hidden = false;
    document.body.classList.add("modal-open");
    const closeButton = modal.querySelector("[data-modal-close].icon-button");
    if (closeButton) closeButton.focus();
    return modal;
  }

  function openHelp() {
    const body = document.createElement("div");
    body.innerHTML = '<p class="ui-modal-lede">NEXUS DNA Retrieval Engine 用于演示 K-mer 哈希索引和汉明距离容错检索。</p><div class="ui-help-grid"><article><strong>1. 准备数据</strong><span>可以生成 50 条可复现实验 Reads，也可以导入已有 FASTA / FASTQ 数据。</span></article><article><strong>2. 配置参数</strong><span>K-mer、最大错配数和提前剪枝可以在加载数据前设置。</span></article><article><strong>3. 运行检索</strong><span>加载数据后运行批量检索，蓝色表示命中，红色表示被阈值拒绝但存在近似对齐。</span></article><article><strong>4. 查看结果</strong><span>索引状态、Reads 列表和运行报告都来自同一次真实检索结果。</span></article></div><p class="ui-modal-note">任务运行或桥接未就绪时，依赖后端的按钮会暂时锁定；帮助和本地视图操作始终可用。</p>';
    openModal("项目使用说明", body);
  }

  function openTrace() {
    const rows = [
      ["当前 Read", document.querySelector("#inspector-title")],
      ["种子前缀", document.querySelector("#trace-seed")],
      ["哈希桶", document.querySelector("#trace-bucket")],
      ["候选位置", document.querySelector("#trace-candidates")],
      ["比较字符", document.querySelector("#trace-compared")],
      ["已剪枝", document.querySelector("#trace-pruned")],
      ["最终状态", document.querySelector("#inspector-status")]
    ];
    const body = document.createElement("div");
    body.innerHTML = '<p class="ui-modal-lede">种子前缀 → 哈希桶 → 候选位置 → 汉明距离比较 → 接受或拒绝。</p>';
    const table = document.createElement("dl");
    table.className = "ui-trace-list";
    rows.forEach(function (row) {
      const wrapper = document.createElement("div");
      const label = document.createElement("dt");
      const value = document.createElement("dd");
      label.textContent = row[0];
      value.textContent = row[1] ? row[1].textContent.trim() : "—";
      wrapper.append(label, value);
      table.appendChild(wrapper);
    });
    body.appendChild(table);
    openModal("算法追踪", body);
  }

  function openPopover(anchor, kind) {
    closePopover();
    popover = document.createElement("div");
    popover.className = "ui-popover";
    popover.setAttribute("role", "menu");
    if (kind === "user") {
      popover.innerHTML = '<strong>本地工作区</strong><span>数据只在本机处理</span><span>当前用户：课程设计实验室</span>';
    } else if (kind === "project") {
      popover.innerHTML = '<strong>项目操作</strong><button type="button" data-local-command="clear-selection">清除当前 Read 选择</button><button type="button" data-local-command="open-help">查看使用说明</button>';
    } else {
      popover.innerHTML = '<strong>视图选项</strong><button type="button" data-local-command="reset-view">重置序列缩放</button><button type="button" data-local-command="toggle-inspector">切换命中详情</button>';
    }
    document.body.appendChild(popover);
    const rect = anchor.getBoundingClientRect();
    const left = Math.min(window.innerWidth - popover.offsetWidth - 12, Math.max(12, rect.right - popover.offsetWidth));
    popover.style.left = left + "px";
    popover.style.top = Math.min(window.innerHeight - popover.offsetHeight - 12, rect.bottom + 8) + "px";
    refreshIcons(popover);
  }

  function copyCoordinate() {
    const value = (document.querySelector("#coordinate-readout") || {}).textContent || "";
    if (!value || value.indexOf("未加载") >= 0) {
      showToast("当前没有可复制的坐标");
      return;
    }
    if (navigator.clipboard) navigator.clipboard.writeText(value).catch(function () {});
    showToast("坐标已复制");
  }

  function runLocalCommand(command) {
    if (command === "clear-selection") {
      sessionStorage.removeItem("selected_read_id");
      showToast("已清除当前 Read 选择");
    } else if (command === "open-help") {
      openHelp();
    } else if (command === "reset-view") {
      window.dispatchEvent(new CustomEvent("dna:reset-view"));
      showToast("视图已重置");
    } else if (command === "toggle-inspector") {
      const button = document.querySelector("#toggle-inspector");
      if (button) button.click();
      else showToast("当前页面没有命中详情面板");
    }
    closePopover();
  }

  document.addEventListener("click", function (event) {
    const link = event.target.closest("a[href]");
    if (link && link.target !== "_blank" && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
      const target = new URL(link.href, window.location.href);
      if (target.origin === window.location.origin) {
        event.preventDefault();
        if (window.DnaRouter && window.DnaRouter.navigateHref(target.href)) return;
        startNavigation(target.href);
        return;
      }
    }
    const action = event.target.closest("[data-ui-action]");
    if (action) {
      const type = action.dataset.uiAction;
      if (type === "help") openHelp();
      else if (type === "user-menu") openPopover(action, "user");
      else if (type === "project-menu") openPopover(action, "project");
      else if (type === "view-menu") openPopover(action, "view");
      else if (type === "copy-coordinate") copyCoordinate();
      else if (type === "trace") openTrace();
      return;
    }
    const command = event.target.closest("[data-local-command]");
    if (command) {
      runLocalCommand(command.dataset.localCommand);
      return;
    }
    if (popover && !event.target.closest(".ui-popover")) closePopover();
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      closePopover();
      closeModal();
    }
  });

  window.addEventListener("pywebviewready", function () {
    setStartupProgress(.68, "本地服务已连接", "正在同步工作区状态");
  });
  window.addEventListener("dna:bridge", function (event) {
    const status = event.detail && event.detail.status;
    if (status === "booting") setStartupProgress(.42, "正在初始化本地服务", "等待安全通信通道");
    else if (status === "ready") setStartupProgress(.82, "通信通道已就绪", "正在读取当前数据状态");
    else if (status === "error") {
      setStartupProgress(.55, "本地服务连接异常", "可以重新连接，不会丢失已加载数据");
      const retry = document.querySelector("#startup-retry");
      if (retry) retry.hidden = false;
    }
  });
  window.addEventListener("dna:state", function () {
    stateReady = true;
    completeStartup();
  });
  window.addEventListener("dna:views-ready", function () {
    viewsReady = true;
    setStartupProgress(.9, "工作区视图已准备", "正在完成状态同步");
    completeStartup();
  });
  window.addEventListener("dna:views-error", function (event) {
    setStartupProgress(.55, "工作区视图加载失败", event.detail && event.detail.message || "请重新加载");
    const retryButton = document.querySelector("#startup-retry");
    if (retryButton) retryButton.hidden = false;
  });
  const retry = document.querySelector("#startup-retry");
  if (retry) retry.addEventListener("click", function () {
    retry.hidden = true;
    setStartupProgress(.35, "正在重新连接", "请稍候");
    if (window.DnaBridge && window.DnaBridge.retry) window.DnaBridge.retry();
    if (window.DnaRouter && !window.DnaRouter.isReady()) window.DnaRouter.retry().catch(function () {});
  });
  setStartupProgress(.2, "正在加载本地界面", "准备 WebView2 与本地服务");
  startupWatchdog = window.setTimeout(function () {
    if (!document.body.classList.contains("app-booting")) return;
    setStartupProgress(.5, "启动时间较长", "WebView2 仍在准备，可以尝试重新连接");
    if (retry) retry.hidden = false;
  }, 8000);

  window.DnaUiActions = { openHelp: openHelp, openTrace: openTrace, showToast: showToast };
}());
