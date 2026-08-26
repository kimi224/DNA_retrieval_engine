(function () {
  "use strict";

  const referenceWindow = "GCTACCGTATCGATGCTAGCTAGGCTAACGTATCGGATCCTAGGCTTACGATCGATGCAATCGGATCGTA";
  const referenceStart = 400;
  const genomeLength = 3200;
  const zoomWindows = [100, 70, 45];
  const zoomBaseWidths = [14, 18, 25];
  const baseAlphabet = ["A", "T", "C", "G"];
  const state = {
    selectedId: "READ-024",
    kmer: 6,
    threshold: 2,
    zoom: 1,
    windowSize: zoomWindows[1],
    overviewZoom: 1,
    windowStart: referenceStart,
    running: false,
    showMismatches: true
  };

  const reads = [
    { id: "READ-024", position: 412, mismatchPositions: [5, 18], candidateCount: 6, pruned: 4, compared: 30, bucket: "#0842" },
    { id: "READ-031", position: 418, mismatchPositions: [12], candidateCount: 9, pruned: 7, compared: 30, bucket: "#0842" },
    { id: "READ-007", position: 426, mismatchPositions: [], candidateCount: 3, pruned: 2, compared: 30, bucket: "#03A7" },
    { id: "READ-042", position: 434, mismatchPositions: [3, 24], candidateCount: 11, pruned: 9, compared: 28, bucket: "#1B90" },
    { id: "READ-018", position: 440, mismatchPositions: [15], candidateCount: 5, pruned: 4, compared: 30, bucket: "#1B90" },
    { id: "READ-049", position: 440, mismatchPositions: [9, 27], candidateCount: 8, pruned: 6, compared: 26, bucket: "#1B90" }
  ].map(function (read) {
    const offset = read.position - referenceStart;
    const refSeq = referenceWindow.slice(offset, offset + 30);
    const readSeq = refSeq.split("").map(function (base, index) {
      if (!read.mismatchPositions.includes(index)) return base;
      return baseAlphabet[(baseAlphabet.indexOf(base) + 1 + (index % 2)) % baseAlphabet.length];
    }).join("");
    return Object.assign({}, read, {
      offset: offset,
      refSeq: refSeq,
      readSeq: readSeq,
      hamming: read.mismatchPositions.length,
      seed: readSeq.slice(0, 6)
    });
  });

  const byId = function (id) { return reads.find(function (read) { return read.id === id; }) || reads[0]; };
  const el = function (selector) { return document.querySelector(selector); };
  const all = function (selector) { return Array.prototype.slice.call(document.querySelectorAll(selector)); };

  function syncRangeVisual(input) {
    if (!input) return;
    const min = Number(input.min || 0);
    const max = Number(input.max || 100);
    const progress = max === min ? 0 : ((Number(input.value) - min) / (max - min)) * 100;
    input.style.setProperty("--range-progress", Math.max(0, Math.min(100, progress)) + "%");
  }

  function pulseValue(output) {
    if (!output) return;
    output.classList.remove("value-pop");
    void output.offsetWidth;
    output.classList.add("value-pop");
  }

  function initRangeMotion() {
    all('input[type="range"]').forEach(function (input) {
      syncRangeVisual(input);
      input.addEventListener("input", function () { syncRangeVisual(input); });
      input.addEventListener("pointerdown", function () { input.classList.add("is-sliding"); });
      ["pointerup", "pointercancel", "blur", "change"].forEach(function (eventName) {
        input.addEventListener(eventName, function () { input.classList.remove("is-sliding"); });
      });
    });
  }

  function genomeBase(position) {
    if (position >= referenceStart && position < referenceStart + referenceWindow.length) return referenceWindow[position - referenceStart];
    return baseAlphabet[Math.abs((position * 17 + 3) % baseAlphabet.length)];
  }

  function genomeSequence(start, length) {
    let result = "";
    for (let index = 0; index < length; index += 1) result += genomeBase(start + index);
    return result;
  }

  function windowEnd() { return state.windowStart + state.windowSize; }
  function currentBaseWidth() { return zoomBaseWidths[state.zoom]; }

  function iconRefresh() {
    if (window.lucide && typeof window.lucide.createIcons === "function") window.lucide.createIcons();
  }

  function showToast(message) {
    const toast = el("#toast");
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add("is-visible");
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(function () { toast.classList.remove("is-visible"); }, 2600);
  }

  function baseSpan(base, mismatch, index) {
    const span = document.createElement("span");
    span.className = "base" + (mismatch ? " mismatch" : "");
    span.textContent = base || "·";
    span.setAttribute("aria-label", mismatch ? "position " + (index + 1) + ", mismatch base " + base : "position " + (index + 1) + ", base " + base);
    if (mismatch) span.title = "Mismatch at read position " + (index + 1);
    return span;
  }

  function renderSequence(container, sequence, mismatchPositions) {
    if (!container) return;
    container.replaceChildren();
    const mismatches = mismatchPositions || [];
    sequence.split("").forEach(function (base, index) {
      container.appendChild(baseSpan(base, mismatches.includes(index), index));
    });
  }

  function renderRuler() {
    const ruler = el("#position-ruler");
    if (!ruler) return;
    ruler.replaceChildren();
    const firstTick = Math.ceil(state.windowStart / 5) * 5;
    for (let position = firstTick; position < windowEnd(); position += 5) {
      const tick = document.createElement("span");
      tick.textContent = position;
      tick.style.left = (((position - state.windowStart) * currentBaseWidth()) + currentBaseWidth() / 2) + "px";
      ruler.appendChild(tick);
    }
  }

  function renderReference() {
    renderSequence(el("#reference-sequence"), genomeSequence(state.windowStart, state.windowSize), []);
  }

  function statusFor(read) {
    return read.hamming <= state.threshold ? "容错命中" : "超过阈值";
  }

  function renderReadList() {
    const list = el("#read-list");
    if (!list) return;
    list.replaceChildren();
    const visibleReads = reads.filter(function (read) {
      return read.position < windowEnd() && read.position + read.readSeq.length > state.windowStart;
    });
    visibleReads.forEach(function (read) {
      const visibleStart = Math.max(read.position, state.windowStart);
      const visibleEnd = Math.min(read.position + read.readSeq.length, windowEnd());
      const sequenceStart = visibleStart - read.position;
      const sequenceEnd = visibleEnd - read.position;
      const visibleSequence = read.readSeq.slice(sequenceStart, sequenceEnd);
      const visibleMismatches = read.mismatchPositions.filter(function (position) {
        return position >= sequenceStart && position < sequenceEnd;
      }).map(function (position) { return position - sequenceStart; });
      const row = document.createElement("div");
      row.className = "read-row" + (read.id === state.selectedId ? " is-selected" : "");
      row.dataset.readId = read.id;
      row.setAttribute("role", "button");
      row.setAttribute("tabindex", "0");
      row.setAttribute("aria-label", "Inspect " + read.id);

      const label = document.createElement("div");
      label.className = "row-label";
      label.innerHTML = '<div class="read-label-line"><strong>' + read.id + '</strong><i data-lucide="scan-search" aria-hidden="true"></i></div><span class="read-position">位置 ' + read.position + '</span>';

      const sequence = document.createElement("div");
      sequence.className = "read-sequence sequence";
      sequence.style.paddingLeft = ((visibleStart - state.windowStart) * currentBaseWidth()) + "px";
      renderSequence(sequence, visibleSequence, visibleMismatches);

      const score = document.createElement("div");
      score.className = "row-score";
      const status = document.createElement("span");
      status.className = "status-label" + (read.hamming > state.threshold ? " mismatch-status" : "");
      status.textContent = read.hamming <= state.threshold ? "命中" : "拒绝";
      score.appendChild(status);

      row.appendChild(label);
      row.appendChild(sequence);
      row.appendChild(score);
      row.addEventListener("click", function () { selectRead(read.id); });
      row.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectRead(read.id); }
      });
      list.appendChild(row);
    });
    if (!visibleReads.length) {
      const empty = document.createElement("div");
      empty.className = "read-empty";
      empty.innerHTML = '<i data-lucide="scan-line" aria-hidden="true"></i><strong>当前窗口没有命中 Read</strong><span>拖动上方滑杆，或点击“定位当前命中”返回结果区域。</span>';
      list.appendChild(empty);
    }
    const summary = el("#alignment-summary");
    if (summary) summary.innerHTML = '<i data-lucide="info" aria-hidden="true"></i> 当前窗口显示 ' + visibleReads.length + ' 条匹配 · 点击行查看详情';
    iconRefresh();
  }

  function renderHitMap() {
    const track = el("#hit-track");
    if (!track) return;
    all(".hit-band").forEach(function (band) { band.remove(); });
    reads.forEach(function (read, index) {
      const band = document.createElement("button");
      band.type = "button";
      band.className = "hit-band" + (read.id === state.selectedId ? " is-selected" : "");
      band.dataset.readId = read.id;
      band.title = read.id + " · position " + read.position;
      band.style.left = (read.position / 3200 * 100) + "%";
      band.style.width = Math.max(0.55, 30 / 3200 * 100) + "%";
      band.addEventListener("click", function () { focusRead(read.id, true); });
      track.appendChild(band);
    });
  }

  function renderCandidateTable() {
    const table = el("#candidate-table");
    if (!table) return;
    table.replaceChildren();
    reads.slice(0, 5).forEach(function (read) {
      const row = document.createElement("tr");
      row.dataset.readId = read.id;
      if (read.id === state.selectedId) row.classList.add("is-selected");
      row.innerHTML = "<td>" + read.id + "</td><td>" + read.seed + "</td><td>" + read.candidateCount + " 个位置</td><td class=\"hit-value\">" + (read.hamming <= state.threshold ? "是" : "否") + "</td><td class=\"pruned-value\">" + read.pruned + "</td>";
      row.addEventListener("click", function () { selectRead(read.id); });
      table.appendChild(row);
    });
  }

  function renderInspector() {
    const read = byId(state.selectedId);
    const isMatch = read.hamming <= state.threshold;
    const title = el("#inspector-title");
    if (title) title.textContent = read.id;
    const status = el("#inspector-status");
    if (status) {
      status.textContent = statusFor(read);
      status.style.color = isMatch ? "var(--green)" : "var(--red)";
    }
    const position = el("#inspector-position");
    if (position) position.textContent = "位置 " + read.position;
    const distance = el("#distance-value");
    if (distance) distance.textContent = read.hamming + " / " + state.threshold;
    const fill = el("#distance-fill");
    if (fill) {
      fill.style.width = Math.min(100, Math.max(10, read.hamming / Math.max(1, state.threshold) * 100)) + "%";
      fill.style.background = isMatch ? "var(--amber)" : "var(--red)";
    }
    renderSequence(el("#inspector-sequence"), read.readSeq, read.mismatchPositions);
    const count = el("#inspector-mismatch-count");
    if (count) count.textContent = read.hamming + " 个错配碱基";
    const seed = read.readSeq.slice(0, state.kmer);
    ["#trace-seed", "#seed-caption"].forEach(function (selector) { const node = el(selector); if (node) node.textContent = seed; });
    const bucket = el("#trace-bucket");
    if (bucket) bucket.textContent = read.bucket;
    const candidates = el("#trace-candidates");
    if (candidates) candidates.textContent = read.candidateCount + " 个位置";
    const compared = el("#trace-compared");
    if (compared) compared.textContent = read.compared + " / 30";
    const pruned = el("#trace-pruned");
    if (pruned) pruned.textContent = read.pruned + " 次提前退出";
    const mismatchList = el("#mismatch-list");
    if (mismatchList) {
      mismatchList.replaceChildren();
      if (!read.mismatchPositions.length) {
        const empty = document.createElement("div");
        empty.className = "empty-mismatch";
        empty.textContent = "完全一致 · 没有错配碱基";
        mismatchList.appendChild(empty);
      } else {
        read.mismatchPositions.forEach(function (index) {
          const item = document.createElement("div");
          item.className = "mismatch-item";
          item.innerHTML = '<span class="mismatch-pos">位置 ' + (index + 1) + '</span><span class="mismatch-pair"><span class="ref-base">' + read.refSeq[index] + '</span><span class="arrow">→</span><span class="read-base">' + read.readSeq[index] + '</span></span><span class="mismatch-kind">允许</span>';
          mismatchList.appendChild(item);
        });
      }
    }
    const mismatchToggle = el("#mismatch-toggle");
    if (mismatchToggle) mismatchToggle.checked = state.showMismatches;
    if (mismatchList) mismatchList.classList.toggle("is-collapsed", !state.showMismatches);
  }

  function updateHitCount() {
    const visibleHits = reads.filter(function (read) { return read.hamming <= state.threshold; }).length;
    const hitCount = el("#hit-count");
    if (hitCount) hitCount.textContent = 41 + visibleHits;
  }

  function selectRead(id) {
    state.selectedId = id;
    all(".read-row").forEach(function (row) { row.classList.toggle("is-selected", row.dataset.readId === id); });
    all(".hit-band").forEach(function (band) { band.classList.toggle("is-selected", band.dataset.readId === id); });
    all("#candidate-table tr").forEach(function (row) { row.classList.toggle("is-selected", row.dataset.readId === id); });
    renderInspector();
    syncWindowLabels();
  }

  function focusRead(id, scrollToSandbox) {
    const read = byId(id);
    const centeredStart = read.position - Math.max(0, Math.floor((state.windowSize - read.readSeq.length) / 2));
    updateWindowStart(centeredStart);
    selectRead(id);
    const sandbox = el(".alignment-panel");
    if (scrollToSandbox && sandbox) sandbox.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function syncWindowLabels() {
    const start = state.windowStart;
    const end = windowEnd();
    const text = start + "–" + end;
    const rangeText = start + "–" + end;
    const coordinate = el("#coordinate-readout");
    const location = el("#window-location");
    const range = el("#window-range");
    const rangeValue = el("#window-range-value");
    const viewport = el("#window-viewport");
    if (coordinate) coordinate.textContent = "chr-demo-01 : " + text;
    if (location) location.textContent = "chr-demo-01:" + start + "-" + end;
    if (range) {
      range.max = genomeLength - state.windowSize;
      range.value = state.windowStart;
      syncRangeVisual(range);
    }
    if (rangeValue) rangeValue.textContent = rangeText;
    if (viewport) {
      viewport.style.left = (state.windowStart / genomeLength * 100) + "%";
      viewport.style.width = (state.windowSize / genomeLength * 100) + "%";
      viewport.setAttribute("aria-valuemin", "0");
      viewport.setAttribute("aria-valuemax", String(genomeLength - state.windowSize));
      viewport.setAttribute("aria-valuenow", String(state.windowStart));
      viewport.setAttribute("aria-valuetext", "坐标 " + rangeText);
    }
    const sizeLabel = el("#window-size-label");
    if (sizeLabel) sizeLabel.textContent = state.windowSize + " bp 窗口";
    syncAlignmentGeometry();
  }

  function syncAlignmentGeometry() {
    const scroll = el("#alignment-scroll");
    if (!scroll) return;
    scroll.style.setProperty("--sequence-width", (state.windowSize * currentBaseWidth()) + "px");
    scroll.style.setProperty("--base-width", currentBaseWidth() + "px");
  }

  function updateWindowStart(next) {
    state.windowStart = Math.max(0, Math.min(genomeLength - state.windowSize, Math.round(Number(next))));
    renderRuler();
    renderReference();
    renderReadList();
    syncWindowLabels();
  }

  function updateKmer(next) {
    state.kmer = Math.max(4, Math.min(10, next));
    const output = el("#kmer-output");
    output.textContent = state.kmer;
    pulseValue(output);
    renderInspector();
    renderCandidateTable();
  }

  function updateThreshold(next) {
    state.threshold = Number(next);
    const output = el("#mismatch-output");
    output.textContent = state.threshold;
    pulseValue(output);
    syncRangeVisual(el("#mismatch-range"));
    updateHitCount();
    renderReadList();
    renderHitMap();
    renderCandidateTable();
    renderInspector();
  }

  function addRunEvent(text, tone) {
    const list = el("#event-list");
    if (!list) return;
    const event = document.createElement("div");
    event.className = "event-item";
    const now = new Date();
    const time = now.toTimeString().slice(0, 8) + "." + String(now.getMilliseconds()).padStart(3, "0");
    event.innerHTML = '<span class="event-time">' + time + '</span><span class="event-dot ' + (tone || "done") + '"></span><span>' + text + '</span>';
    list.appendChild(event);
  }

  async function runSearch() {
    if (state.running) return;
    state.running = true;
    const button = el("#run-button");
    const status = el("#run-status-text");
    const label = button.querySelector("span");
    button.disabled = true;
    button.classList.add("is-running");
    if (label) label.textContent = "扫描中…";
    if (status) status.textContent = "正在扫描 50 条 Reads · 检查哈希桶…";
    el("#hit-track").classList.add("scan-active");
    addRunEvent("开始批量扫描 · K=" + state.kmer + "，最大错配 " + state.threshold, "done");
    try {
      if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.run_search === "function") {
        await window.pywebview.api.run_search({ kmer: state.kmer, max_mismatches: state.threshold });
      } else {
        await new Promise(function (resolve) { window.setTimeout(resolve, 1250); });
      }
    } catch (error) {
      addRunEvent("Python bridge 不可用 · 保留本地样例结果", "warn");
    }
    state.running = false;
    button.disabled = false;
    button.classList.remove("is-running");
    el("#hit-track").classList.remove("scan-active");
    if (label) label.textContent = "再次运行";
    if (status) status.textContent = "索引就绪 · 上次耗时 18.4 ms";
    addRunEvent("批量扫描完成 · " + el("#hit-count").textContent + " 条容错命中", "done");
    showToast("批量检索完成 · 结果已刷新");
  }

  function updateZoom(delta) {
    state.zoom = Math.max(0, Math.min(2, state.zoom + delta));
    state.windowSize = zoomWindows[state.zoom];
    el("#zoom-label").textContent = ["0.75×", "1×", "1.5×"][state.zoom];
    const scroll = el("#alignment-scroll");
    if (scroll) {
      scroll.classList.remove("zoom-0", "zoom-1", "zoom-2");
      scroll.classList.add("zoom-" + state.zoom);
    }
    updateWindowStart(state.windowStart);
  }

  function updateOverviewZoom(delta) {
    const levels = [1, 2, 4];
    const currentIndex = levels.indexOf(state.overviewZoom);
    const nextIndex = Math.max(0, Math.min(levels.length - 1, currentIndex + delta));
    state.overviewZoom = levels[nextIndex];
    const map = el("#overview-map");
    const label = el("#overview-zoom-label");
    if (map) map.style.width = (state.overviewZoom * 100) + "%";
    if (label) label.textContent = state.overviewZoom + "×";
  }

  function wireWindowControls() {
    const range = el("#window-range");
    const track = el("#map-track");
    const viewport = el("#window-viewport");
    if (range) range.addEventListener("input", function (event) { updateWindowStart(event.target.value); });
    if (!track || !viewport) return;
    let dragging = false;
    const setFromPointer = function (event, centerWindow) {
      const rect = track.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
      const target = ratio * genomeLength - (centerWindow ? state.windowSize / 2 : 0);
      updateWindowStart(target);
    };
    track.addEventListener("pointerdown", function (event) {
      dragging = event.target === viewport;
      viewport.classList.toggle("is-dragging", dragging);
      setFromPointer(event, dragging);
      track.setPointerCapture(event.pointerId);
    });
    track.addEventListener("pointermove", function (event) { if (dragging) setFromPointer(event, true); });
    track.addEventListener("pointerup", function () { dragging = false; viewport.classList.remove("is-dragging"); });
    viewport.addEventListener("keydown", function (event) {
      if (event.key === "ArrowLeft") { event.preventDefault(); updateWindowStart(state.windowStart - 10); }
      if (event.key === "ArrowRight") { event.preventDefault(); updateWindowStart(state.windowStart + 10); }
    });
  }

  function wireEvents() {
    all("[data-toast]").forEach(function (node) {
      node.addEventListener("click", function () { showToast(node.dataset.toast); });
      if (node.getAttribute("role") === "button") node.addEventListener("keydown", function (event) { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); showToast(node.dataset.toast); } });
    });
    all(".nav-tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        all(".nav-tab").forEach(function (item) { item.classList.remove("is-active"); });
        tab.classList.add("is-active");
        if (tab.dataset.view !== "run") showToast((tab.querySelector("span") || tab).textContent.trim() + " 页面将在完整版本中展开");
      });
    });
    all("[data-step-target]").forEach(function (button) {
      button.addEventListener("click", function () { updateKmer(state.kmer + Number(button.dataset.step)); });
    });
    el("#mismatch-range").addEventListener("input", function (event) { updateThreshold(event.target.value); });
    el("#mismatch-toggle").addEventListener("change", function (event) {
      state.showMismatches = event.target.checked;
      const list = el("#mismatch-list");
      if (list) list.classList.toggle("is-collapsed", !state.showMismatches);
    });
    el("#run-button").addEventListener("click", runSearch);
    el("#zoom-in").addEventListener("click", function () { updateZoom(1); });
    el("#zoom-out").addEventListener("click", function () { updateZoom(-1); });
    el("#overview-zoom-in").addEventListener("click", function () { updateOverviewZoom(1); });
    el("#overview-zoom-out").addEventListener("click", function () { updateOverviewZoom(-1); });
    el("#center-view").addEventListener("click", function () {
      focusRead(state.selectedId, false);
      showToast("已定位到 " + state.selectedId);
    });
    el("#copy-result").addEventListener("click", function () {
      const read = byId(state.selectedId);
      const summary = read.id + " @ " + read.position + " · 汉明距离 " + read.hamming + "/" + state.threshold + " · 种子 " + read.readSeq.slice(0, state.kmer);
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(summary).catch(function () {});
      showToast("命中摘要已复制");
    });
    document.addEventListener("keydown", function (event) {
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") { event.preventDefault(); runSearch(); }
    });
    wireWindowControls();
  }

  function init() {
    renderRuler();
    renderReference();
    renderReadList();
    renderHitMap();
    renderCandidateTable();
    renderInspector();
    updateHitCount();
    syncWindowLabels();
    updateOverviewZoom(0);
    initRangeMotion();
    wireEvents();
    iconRefresh();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
}());
