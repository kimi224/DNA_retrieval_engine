(function () {
  "use strict";

  const zoomWindows = [100, 70, 45];
  const zoomBaseWidths = [14, 18, 25];
  const view = {
    app: null,
    result: null,
    selectedId: sessionStorage.getItem("selected_read_id") || null,
    kmer: 6,
    threshold: 2,
    zoom: 1,
    overviewZoom: 1,
    windowSize: 70,
    windowStart: 0,
    referenceSequence: "",
    showMismatches: true,
    inspectorCollapsed: sessionStorage.getItem("inspector_collapsed") === "1",
    paths: { output: null, dataset: null, reference: null, reads: null, truth: null },
    lastTaskSignature: "",
    referenceRequest: 0
  };

  const node = function (selector) { return document.querySelector(selector); };
  const nodes = function (selector) { return Array.from(document.querySelectorAll(selector)); };
  const formatNumber = function (value) { return Number(value || 0).toLocaleString("zh-CN"); };
  const fileName = function (path) { return path ? path.split(/[\\/]/).pop() : ""; };
  const dataset = function () { return view.app && view.app.dataset && view.app.dataset.loaded ? view.app.dataset : null; };
  const indexState = function () { return view.app && view.app.index && view.app.index.built ? view.app.index : null; };
  const genomeLength = function () { return dataset() ? dataset().reference_length : 0; };
  const windowEnd = function () { return Math.min(genomeLength(), view.windowStart + view.windowSize); };
  const currentBaseWidth = function () { return zoomBaseWidths[view.zoom]; };

  function refreshIcons() {
    if (window.lucide && typeof window.lucide.createIcons === "function") window.lucide.createIcons();
  }

  function showToast(message) {
    const toast = node("#toast");
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add("is-visible");
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(function () { toast.classList.remove("is-visible"); }, 3000);
  }

  function setText(selector, value) {
    const target = node(selector);
    if (target) target.textContent = value;
  }

  function syncRangeVisual(input) {
    if (!input) return;
    const min = Number(input.min || 0);
    const max = Number(input.max || 100);
    const progress = max === min ? 0 : (Number(input.value) - min) / (max - min) * 100;
    input.style.setProperty("--range-progress", progress + "%");
  }

  function baseSpan(base, mismatch, displayPosition) {
    const span = document.createElement("span");
    span.className = "base" + (mismatch ? " mismatch" : "");
    span.textContent = base;
    span.setAttribute("aria-label", "位置 " + displayPosition + "，碱基 " + base + (mismatch ? "，错配" : ""));
    return span;
  }

  function renderSequence(container, sequence, mismatchOffsets, startPosition) {
    if (!container) return;
    container.replaceChildren();
    const mismatchSet = mismatchOffsets || [];
    sequence.split("").forEach(function (base, offset) {
      container.appendChild(baseSpan(base, mismatchSet.includes(offset), (startPosition || 1) + offset));
    });
  }

  function selectedRead() {
    const reads = view.result ? view.result.reads : [];
    if (!reads.length) return null;
    let selected = reads.find(function (read) { return read.id === view.selectedId; });
    if (!selected) selected = reads.find(function (read) { return read.matched; }) || reads[0];
    view.selectedId = selected.id;
    sessionStorage.setItem("selected_read_id", selected.id);
    return selected;
  }

  function displayHit(read) {
    return read && (read.best_hit || read.nearest_hit) || null;
  }

  function displayHits(read) {
    if (!read) return [];
    return read.matched ? read.hits : (read.nearest_hit ? [read.nearest_hit] : []);
  }

  function setInspectorCollapsed(collapsed) {
    view.inspectorCollapsed = Boolean(collapsed);
    sessionStorage.setItem("inspector_collapsed", view.inspectorCollapsed ? "1" : "0");
    const grid = node(".workspace-grid");
    const inspector = node(".inspector");
    const closeButton = node("#toggle-inspector");
    const openButton = node("#open-inspector-button");
    if (grid) grid.classList.toggle("inspector-collapsed", view.inspectorCollapsed);
    if (inspector) inspector.classList.toggle("is-collapsed", view.inspectorCollapsed);
    if (closeButton) {
      closeButton.setAttribute("aria-expanded", String(!view.inspectorCollapsed));
      closeButton.title = view.inspectorCollapsed ? "打开详情" : "收起详情";
      closeButton.setAttribute("aria-label", closeButton.title);
      const icon = closeButton.querySelector("[data-lucide]");
      if (icon) icon.setAttribute("data-lucide", view.inspectorCollapsed ? "panel-right-open" : "panel-right-close");
    }
    if (openButton) openButton.hidden = !view.inspectorCollapsed;
    refreshIcons();
  }

  function renderAppState() {
    const data = dataset();
    const index = indexState();
    const task = view.app && view.app.task;
    const running = task && task.status === "running";
    const bridgeReady = Boolean(view.app && view.app.bridge_ready);
    const runButton = node("#run-button");
    const exportButton = node("#export-button");
    if (runButton) runButton.disabled = !bridgeReady || !data || running;
    if (exportButton) exportButton.disabled = !bridgeReady || !view.result || running;
    nodes(".input-action, .file-field, .truth-file-button").forEach(function (button) {
      button.disabled = running || !bridgeReady || (button.id === "load-folder-button" && !view.paths.dataset) || (button.id === "load-files-button" && !(view.paths.reference && view.paths.reads));
    });
    nodes("[data-step-target], #mismatch-range, #prune-toggle").forEach(function (control) {
      control.disabled = running || !bridgeReady || !data;
    });
    nodes("#window-range, #zoom-in, #zoom-out, #overview-zoom-in, #overview-zoom-out, #center-view, #copy-result").forEach(function (control) {
      control.disabled = running || !bridgeReady || !data;
    });
    if (running || !bridgeReady) {
      // Keep only the local Inspector toggle available while the bridge or a
      // long-running task is unavailable; every API-backed action is locked.
      nodes("button").forEach(function (button) {
        if (button.id !== "toggle-inspector" && button.id !== "open-inspector-button") button.disabled = true;
      });
    }
    setInspectorCollapsed(view.inspectorCollapsed);

    if (data) {
      setText("#project-name", data.dataset_id + " / " + data.reference_id);
      setText("#project-meta", data.source_mode === "generated" ? "生成数据 · 本地项目" : "导入数据 · 本地项目");
      setText("#nav-read-count", data.read_count);
      setText("#input-state-label", "已加载");
      setText("#workspace-reference-id", data.reference_id);
      setText("#alignment-reference-id", data.reference_id);
      setText("#metric-read-count", data.read_count);
      setText("#metric-read-note", data.min_read_length + "–" + data.max_read_length + " bp · 平均 " + data.average_read_length);
      const loaded = node("#loaded-file-summary");
      if (loaded) loaded.innerHTML = '<i data-lucide="circle-check" aria-hidden="true"></i><span><strong>' + fileName(data.reference_path) + '</strong> · ' + formatNumber(data.reference_length) + ' bp<br><strong>' + fileName(data.reads_path) + '</strong> · ' + data.read_count + ' 条 Reads' + (data.has_truth ? " · 含真值" : "") + "</span>";
      const live = node("#workspace-live");
      if (live) live.lastChild.textContent = index ? " 索引就绪" : " 数据已加载";
    } else {
      setText("#project-name", "尚未加载数据");
      setText("#input-state-label", bridgeReady ? "未加载" : "连接中");
      setText("#nav-read-count", "0");
      setText("#metric-read-count", "0");
      setText("#metric-read-note", "等待数据集");
    }
    setText("#metric-window-note", index ? "本地 · " + formatNumber(index.window_count) + " 个窗口" : "本地 · 尚未构建索引");

    const status = node("#run-status-text");
    const statusWrap = status && status.parentElement;
    if (statusWrap) statusWrap.classList.toggle("is-error", Boolean(task && task.status === "error"));
    if (!bridgeReady) setText("#run-status-text", "正在连接本地服务…");
    else if (task && task.status === "running") setText("#run-status-text", task.message + " · " + task.progress + "%");
    else if (task && task.status === "error") setText("#run-status-text", task.error || "任务失败");
    else if (task && task.status === "cancelled") setText("#run-status-text", "任务已取消");
    else if (index) setText("#run-status-text", "索引就绪 · K=" + index.k + " · " + formatNumber(index.position_node_count) + " 个节点");
    else setText("#run-status-text", "本地服务已就绪 · 请生成或导入数据");

    if (task && ["completed", "error", "cancelled"].includes(task.status)) {
      const signature = task.task_id + ":" + task.status;
      if (signature !== view.lastTaskSignature) {
        view.lastTaskSignature = signature;
        showToast(task.status === "completed" ? task.message : (task.error || task.message));
      }
    }
    renderAxis();
    refreshIcons();
  }

  function renderMetrics() {
    const summary = view.result && view.result.summary;
    if (!summary) {
      setText("#hit-count", "0");
      setText("#metric-hit-note", "尚未运行");
      setText("#metric-prune-rate", "0.0");
      setText("#metric-prune-note", "等待检索");
      setText("#metric-elapsed", "0.0");
      return;
    }
    setText("#hit-count", summary.matched_read_count);
    setText("#metric-hit-note", summary.match_rate.toFixed(1) + "% 命中率");
    setText("#metric-prune-rate", summary.prune_rate.toFixed(1));
    setText("#metric-prune-note", formatNumber(summary.pruned_candidate_count) + " / " + formatNumber(summary.candidate_count) + " 个候选");
    setText("#metric-elapsed", Number(summary.elapsed_ms).toFixed(3));
  }

  function renderAxis() {
    const length = genomeLength();
    const labels = node("#map-axis");
    if (!labels) return;
    const values = [0, .25, .5, .75, 1].map(function (ratio) { return Math.round(length * ratio); });
    Array.from(labels.children).forEach(function (label, index) {
      label.textContent = formatNumber(values[index]) + (index === 4 ? " bp" : "");
    });
  }

  function renderRuler() {
    const ruler = node("#position-ruler");
    if (!ruler) return;
    ruler.replaceChildren();
    const first = Math.ceil(view.windowStart / 5) * 5;
    for (let position = first; position < windowEnd(); position += 5) {
      const tick = document.createElement("span");
      tick.textContent = position + 1;
      tick.style.left = (((position - view.windowStart) * currentBaseWidth()) + currentBaseWidth() / 2) + "px";
      ruler.appendChild(tick);
    }
  }

  async function loadReferenceWindow() {
    if (!dataset() || !window.DnaBridge.isConnected()) {
      view.referenceSequence = "";
      renderReference();
      return;
    }
    const requestId = ++view.referenceRequest;
    try {
      const response = await window.DnaBridge.call("get_reference_window", view.windowStart, view.windowSize);
      if (requestId !== view.referenceRequest) return;
      if (!response.ok) throw new Error(response.error);
      view.referenceSequence = response.value.sequence;
      renderReference();
    } catch (error) {
      showToast(error.message || String(error));
    }
  }

  function renderReference() {
    const container = node("#reference-sequence");
    if (!container) return;
    if (!view.referenceSequence) {
      container.textContent = dataset() ? "正在读取参考序列…" : "请先生成或导入数据";
      return;
    }
    renderSequence(container, view.referenceSequence, [], view.windowStart + 1);
  }

  function renderHitMap() {
    const track = node("#hit-track");
    if (!track) return;
    nodes("#hit-track .hit-band").forEach(function (band) { band.remove(); });
    const length = genomeLength();
    if (!view.result || !length) return;
    view.result.reads.forEach(function (read) {
      displayHits(read).forEach(function (hit) {
        const band = document.createElement("button");
        band.type = "button";
        band.className = "hit-band" + (!read.matched ? " is-rejected" : "") + (read.id === view.selectedId ? " is-selected" : "");
        band.dataset.readId = read.id;
        band.title = read.id + " · 位置 " + hit.start_1 + " · 错配 " + hit.hamming_distance + (!read.matched ? " · 匹配失败" : "");
        band.style.left = (hit.start_0 / length * 100) + "%";
        band.style.width = Math.max(.55, read.length / length * 100) + "%";
        band.addEventListener("click", function () { focusRead(read.id, hit.start_0, true); });
        track.appendChild(band);
      });
    });
  }

  function renderReadList() {
    const list = node("#read-list");
    if (!list) return;
    list.replaceChildren();
    const visible = [];
    if (view.result) {
      view.result.reads.forEach(function (read) {
        displayHits(read).forEach(function (hit) {
          if (hit.start_0 < windowEnd() && hit.end_1 > view.windowStart + 1) visible.push({ read: read, hit: hit });
        });
      });
    }
    visible.slice(0, 12).forEach(function (item) {
      const read = item.read;
      const hit = item.hit;
      const visibleStart = Math.max(hit.start_0, view.windowStart);
      const visibleEnd = Math.min(hit.start_0 + read.length, windowEnd());
      const sequenceStart = visibleStart - hit.start_0;
      const sequenceEnd = visibleEnd - hit.start_0;
      const mismatchOffsets = hit.mismatches.filter(function (mismatch) {
        return mismatch.read_offset_0 >= sequenceStart && mismatch.read_offset_0 < sequenceEnd;
      }).map(function (mismatch) { return mismatch.read_offset_0 - sequenceStart; });
      const row = document.createElement("div");
      row.className = "read-row" + (!read.matched ? " is-rejected" : "") + (read.id === view.selectedId ? " is-selected" : "");
      row.dataset.readId = read.id;
      row.tabIndex = 0;
      row.setAttribute("role", "button");
      row.innerHTML = '<div class="row-label"><div class="read-label-line"><strong>' + read.id + '</strong><i data-lucide="scan-search" aria-hidden="true"></i></div><span class="read-position">位置 ' + hit.start_1 + '</span></div>';
      const sequence = document.createElement("div");
      sequence.className = "read-sequence sequence";
      sequence.style.paddingLeft = ((visibleStart - view.windowStart) * currentBaseWidth()) + "px";
      renderSequence(sequence, read.sequence.slice(sequenceStart, sequenceEnd), mismatchOffsets, visibleStart + 1);
      const score = document.createElement("div");
      score.className = "row-score";
      score.innerHTML = '<span class="status-label' + (!read.matched ? " mismatch-status" : "") + '">错配' + hit.hamming_distance + "</span>";
      row.appendChild(sequence);
      row.appendChild(score);
      row.addEventListener("click", function () { selectRead(read.id); });
      row.addEventListener("keydown", function (event) { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectRead(read.id); } });
      list.appendChild(row);
    });
    if (!visible.length) {
      const empty = document.createElement("div");
      empty.className = "read-empty";
      empty.innerHTML = '<i data-lucide="scan-line" aria-hidden="true"></i><strong>' + (view.result ? "当前窗口没有比对 Read" : "尚未产生检索结果") + '</strong><span>' + (view.result ? "拖动上方滑杆查看参考序列的其他区段。" : "加载数据后运行批量检索。") + "</span>";
      list.appendChild(empty);
    }
    setText("#alignment-summary", "当前窗口显示 " + visible.length + " 个比对区间 · 点击行查看详情");
    refreshIcons();
  }

  function renderInspector() {
    const read = selectedRead();
    if (!read) {
      setText("#inspector-title", "等待结果");
      setText("#inspector-status", "尚未运行");
      setText("#inspector-position", "位置 —");
      setText("#distance-value", "— / " + view.threshold);
      setText("#distance-reject-label", "> " + view.threshold + " 拒绝");
      const emptySequence = node("#inspector-sequence");
      renderSequence(emptySequence, "", []);
      if (emptySequence) emptySequence.classList.remove("is-rejected");
      [node("#inspector-status"), node("#distance-value"), node("#inspector-mismatch-count")].forEach(function (element) {
        if (element) element.classList.remove("mismatch-status");
      });
      const mismatchList = node("#mismatch-list");
      if (mismatchList) mismatchList.innerHTML = '<div class="empty-mismatch">运行检索后显示错配明细</div>';
      return;
    }
    const hit = displayHit(read);
    const accepted = Boolean(read.best_hit);
    const mismatches = hit ? hit.mismatches : [];
    setText("#inspector-title", read.id);
    setText("#inspector-status", hit ? (accepted ? (hit.hamming_distance === 0 ? "完全一致" : "容错命中") : "匹配失败") : "未命中");
    setText("#inspector-position", hit ? "位置 " + hit.start_1 + (read.hits.length > 1 ? " · 共 " + read.hits.length + " 个命中" : "") : "无合法位置");
    setText("#distance-value", hit ? hit.hamming_distance + " / " + view.threshold : "> " + view.threshold);
    setText("#distance-reject-label", "> " + view.threshold + " 拒绝");
    const statusLabel = node("#inspector-status");
    const distanceValue = node("#distance-value");
    const mismatchCount = node("#inspector-mismatch-count");
    [statusLabel, distanceValue, mismatchCount].forEach(function (element) {
      if (element) element.classList.toggle("mismatch-status", !accepted);
    });
    const fill = node("#distance-fill");
    if (fill) {
      fill.style.width = hit ? Math.min(100, Math.max(8, hit.hamming_distance / Math.max(1, view.threshold) * 100)) + "%" : "100%";
      fill.style.background = accepted ? "var(--amber)" : "var(--red)";
    }
    const inspectorSequence = node("#inspector-sequence");
    renderSequence(inspectorSequence, read.sequence, mismatches.map(function (item) { return item.read_offset_0; }), 1);
    if (inspectorSequence) inspectorSequence.classList.toggle("is-rejected", !accepted);
    const note = node("#inspector-sequence") && node("#inspector-sequence").nextElementSibling;
    if (note && note.firstElementChild) note.firstElementChild.textContent = read.length + " bp";
    setText("#inspector-mismatch-count", hit ? "错配" + hit.hamming_distance : "未通过阈值");
    setText("#trace-seed", read.seed);
    setText("#trace-bucket", "#" + String(read.bucket_index).padStart(4, "0"));
    setText("#trace-candidates", read.candidate_count + " 个位置");
    setText("#trace-compared", formatNumber(read.compared_base_count) + " 个字符");
    setText("#trace-pruned", read.pruned_candidate_count + " 次提前退出");
    const mismatchList = node("#mismatch-list");
    if (mismatchList) {
      mismatchList.replaceChildren();
      if (!mismatches.length) mismatchList.innerHTML = '<div class="empty-mismatch">' + (hit ? "完全一致 · 没有错配碱基" : "未命中 · 无可展示的接受位置") + "</div>";
      mismatches.forEach(function (mismatch) {
        const item = document.createElement("div");
        item.className = "mismatch-item";
        item.innerHTML = '<span class="mismatch-pos">Read ' + mismatch.read_offset_1 + '</span><span class="mismatch-pair"><span class="ref-base">' + mismatch.reference_base + '</span><span class="arrow">→</span><span class="read-base">' + mismatch.read_base + '</span></span><span class="mismatch-kind">参考 ' + mismatch.reference_position_1 + "</span>";
        mismatchList.appendChild(item);
      });
      mismatchList.classList.toggle("is-collapsed", !view.showMismatches);
    }
    refreshIcons();
  }

  function syncWindowLabels() {
    const length = genomeLength();
    const end = windowEnd();
    const display = length ? (view.windowStart + 1) + "–" + end : "—";
    const referenceId = dataset() ? dataset().reference_id : "未加载";
    setText("#coordinate-readout", referenceId + " : " + display);
    setText("#window-location", referenceId + ":" + display);
    setText("#window-range-value", display);
    setText("#window-size-label", (end - view.windowStart || view.windowSize) + " bp 窗口");
    const range = node("#window-range");
    if (range) {
      range.max = Math.max(0, length - view.windowSize);
      range.value = view.windowStart;
      range.disabled = !length;
      syncRangeVisual(range);
    }
    const viewport = node("#window-viewport");
    if (viewport) {
      viewport.style.left = length ? (view.windowStart / length * 100) + "%" : "0";
      viewport.style.width = length ? (view.windowSize / length * 100) + "%" : "0";
      viewport.setAttribute("aria-valuenow", String(view.windowStart));
      viewport.setAttribute("aria-valuemax", String(Math.max(0, length - view.windowSize)));
    }
    const scroll = node("#alignment-scroll");
    if (scroll) {
      scroll.style.setProperty("--sequence-width", (view.windowSize * currentBaseWidth()) + "px");
      scroll.style.setProperty("--base-width", currentBaseWidth() + "px");
    }
  }

  function updateWindowStart(next) {
    view.windowStart = Math.max(0, Math.min(Math.max(0, genomeLength() - view.windowSize), Math.round(Number(next))));
    syncWindowLabels();
    renderRuler();
    renderReadList();
    loadReferenceWindow();
  }

  function selectRead(id) {
    view.selectedId = id;
    sessionStorage.setItem("selected_read_id", id);
    nodes(".read-row, .hit-band").forEach(function (item) { item.classList.toggle("is-selected", item.dataset.readId === id); });
    renderInspector();
  }

  function focusRead(id, position, scrollToSandbox) {
    const read = view.result && view.result.reads.find(function (item) { return item.id === id; });
    if (!read) return;
    const hit = Number.isInteger(position) ? displayHits(read).find(function (item) { return item.start_0 === position; }) : displayHit(read);
    if (hit) updateWindowStart(hit.start_0 - Math.max(0, Math.floor((view.windowSize - read.length) / 2)));
    selectRead(id);
    if (scrollToSandbox) node(".alignment-panel").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderResult() {
    if (view.result && view.result.parameters) {
      view.kmer = view.result.parameters.k;
      view.threshold = view.result.parameters.max_mismatches;
      setText("#kmer-output", view.kmer);
      setText("#mismatch-output", view.threshold);
      const mismatchRange = node("#mismatch-range");
      if (mismatchRange) { mismatchRange.value = view.threshold; syncRangeVisual(mismatchRange); }
    }
    const selected = selectedRead();
    if (selected && displayHit(selected) && !view.referenceSequence) view.windowStart = Math.max(0, displayHit(selected).start_0 - 10);
    renderMetrics();
    renderHitMap();
    renderReadList();
    renderInspector();
    syncWindowLabels();
    renderRuler();
    loadReferenceWindow();
  }

  async function choosePath(method, key, nameSelector, pathSelector) {
    try {
      const response = await window.DnaBridge.call(method);
      if (!response.ok) throw new Error(response.error);
      if (response.cancelled) return;
      view.paths[key] = response.path;
      if (nameSelector) setText(nameSelector, fileName(response.path));
      if (pathSelector) setText(pathSelector, response.path);
      renderAppState();
    } catch (error) { showToast(error.message || String(error)); }
  }

  async function startTask(method, payload) {
    try {
      if (!window.DnaBridge.isConnected()) throw new Error("本地服务尚未就绪，请稍后重试");
      const response = await window.DnaBridge.call(method, payload);
      if (!response.ok) throw new Error(response.error);
      await window.DnaBridge.refreshState();
    } catch (error) { showToast(error.message || String(error)); }
  }

  function wireInput() {
    nodes("[data-input-mode]").forEach(function (tab) {
      tab.addEventListener("click", function () {
        const generate = tab.dataset.inputMode === "generate";
        nodes("[data-input-mode]").forEach(function (item) { item.classList.toggle("is-active", item === tab); item.setAttribute("aria-selected", String(item === tab)); });
        node("#generate-panel").classList.toggle("is-hidden", !generate);
        node("#import-panel").classList.toggle("is-hidden", generate);
      });
    });
    nodes("[data-import-mode]").forEach(function (tab) {
      tab.addEventListener("click", function () {
        const folder = tab.dataset.importMode === "folder";
        nodes("[data-import-mode]").forEach(function (item) { item.classList.toggle("is-active", item === tab); item.setAttribute("aria-selected", String(item === tab)); });
        node("#folder-import-panel").classList.toggle("is-hidden", !folder);
        node("#files-import-panel").classList.toggle("is-hidden", folder);
      });
    });
    node("#choose-output-button").addEventListener("click", function () { choosePath("choose_output_directory", "output", "#output-directory-name", "#output-directory-path"); });
    node("#choose-dataset-button").addEventListener("click", function () { choosePath("choose_dataset_directory", "dataset", "#dataset-directory-name", "#dataset-directory-path"); });
    node("#choose-reference-button").addEventListener("click", function () { choosePath("choose_reference_file", "reference", "#reference-file-name"); });
    node("#choose-reads-button").addEventListener("click", function () { choosePath("choose_reads_file", "reads", "#reads-file-name"); });
    node("#choose-truth-button").addEventListener("click", function () { choosePath("choose_truth_file", "truth", "#truth-file-name"); });
    node("#generate-button").addEventListener("click", function () {
      startTask("start_generate_dataset", { output_directory: view.paths.output, seed: node("#seed-input").value.trim() });
    });
    node("#load-folder-button").addEventListener("click", function () { startTask("start_load_dataset_folder", view.paths.dataset); });
    node("#load-files-button").addEventListener("click", function () { startTask("start_load_dataset_files", { reference_path: view.paths.reference, reads_path: view.paths.reads, truth_path: view.paths.truth }); });
  }

  function wireControls() {
    nodes("[data-step-target]").forEach(function (button) {
      button.addEventListener("click", function () {
        view.kmer = Math.max(4, Math.min(12, view.kmer + Number(button.dataset.step)));
        setText("#kmer-output", view.kmer);
      });
    });
    node("#mismatch-range").addEventListener("input", function (event) { view.threshold = Number(event.target.value); setText("#mismatch-output", view.threshold); syncRangeVisual(event.target); });
    node("#mismatch-toggle").addEventListener("change", function (event) { view.showMismatches = event.target.checked; renderInspector(); });
    node("#run-button").addEventListener("click", function () { startTask("start_search", { k: view.kmer, max_mismatches: view.threshold, early_prune: node("#prune-toggle").checked }); });
    node("#window-range").addEventListener("input", function (event) { updateWindowStart(event.target.value); });
    node("#zoom-in").addEventListener("click", function () { view.zoom = Math.min(2, view.zoom + 1); view.windowSize = zoomWindows[view.zoom]; setText("#zoom-label", ["0.75×", "1×", "1.5×"][view.zoom]); node("#alignment-scroll").className = "alignment-scroll zoom-" + view.zoom; updateWindowStart(view.windowStart); });
    node("#zoom-out").addEventListener("click", function () { view.zoom = Math.max(0, view.zoom - 1); view.windowSize = zoomWindows[view.zoom]; setText("#zoom-label", ["0.75×", "1×", "1.5×"][view.zoom]); node("#alignment-scroll").className = "alignment-scroll zoom-" + view.zoom; updateWindowStart(view.windowStart); });
    node("#overview-zoom-in").addEventListener("click", function () { view.overviewZoom = Math.min(4, view.overviewZoom * 2); node("#overview-map").style.width = view.overviewZoom * 100 + "%"; setText("#overview-zoom-label", view.overviewZoom + "×"); });
    node("#overview-zoom-out").addEventListener("click", function () { view.overviewZoom = Math.max(1, view.overviewZoom / 2); node("#overview-map").style.width = view.overviewZoom * 100 + "%"; setText("#overview-zoom-label", view.overviewZoom + "×"); });
    node("#center-view").addEventListener("click", function () { const read = selectedRead(); if (read) focusRead(read.id, null, false); });
    node("#copy-result").addEventListener("click", function () { const read = selectedRead(); if (!read) return; const hit = displayHit(read); const summary = read.id + (hit ? " @ " + hit.start_1 + " · 错配" + hit.hamming_distance + "/" + view.threshold : " · 未命中") + " · 种子 " + read.seed; if (navigator.clipboard) navigator.clipboard.writeText(summary).catch(function () {}); showToast("命中摘要已复制"); });
    node("#toggle-inspector").addEventListener("click", function () { setInspectorCollapsed(!view.inspectorCollapsed); });
    node("#open-inspector-button").addEventListener("click", function () { setInspectorCollapsed(false); });
    node("#export-button").addEventListener("click", async function () { try { const response = await window.DnaBridge.call("choose_export_directory"); if (!response.ok) throw new Error(response.error); if (!response.cancelled) startTask("start_export_results", { output_directory: response.path }); } catch (error) { showToast(error.message || String(error)); } });
    document.addEventListener("keydown", function (event) { if ((event.ctrlKey || event.metaKey) && event.key === "Enter") { event.preventDefault(); node("#run-button").click(); } });
    nodes("[data-toast]").forEach(function (button) { button.addEventListener("click", function () { showToast(button.dataset.toast); }); });
  }

  function init() {
    wireInput();
    wireControls();
    syncRangeVisual(node("#mismatch-range"));
    renderAppState();
    renderResult();
    window.DnaStore.subscribe(function (snapshot) {
      view.app = snapshot.app;
      view.result = snapshot.result;
      renderAppState();
      renderResult();
    });
    if (sessionStorage.getItem("open_input_mode") === "import") {
      sessionStorage.removeItem("open_input_mode");
      const importTab = node('[data-input-mode="import"]');
      if (importTab) importTab.click();
    }
    refreshIcons();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
}());
