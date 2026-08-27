(function () {
  "use strict";

  const page = location.pathname.split("/").pop();
  const state = { app: null, result: null };
  const node = function (selector) { return document.querySelector(selector); };
  const nodes = function (selector) { return Array.from(document.querySelectorAll(selector)); };
  const formatNumber = function (value) { return Number(value || 0).toLocaleString("zh-CN"); };
  const fileName = function (path) { return path ? path.split(/[\\/]/).pop() : "—"; };

  function refreshIcons() {
    if (window.lucide && typeof window.lucide.createIcons === "function") window.lucide.createIcons();
  }

  function toast(message) {
    const target = node("#toast");
    if (!target) return;
    target.textContent = message;
    target.classList.add("is-visible");
    window.clearTimeout(toast.timer);
    toast.timer = window.setTimeout(function () { target.classList.remove("is-visible"); }, 2800);
  }

  function setText(selector, value) {
    const target = node(selector);
    if (target) target.textContent = value;
  }

  function setCommonState() {
    const data = state.app && state.app.dataset && state.app.dataset.loaded ? state.app.dataset : null;
    nodes("[data-project-name]").forEach(function (target) { target.textContent = data ? data.dataset_id + " / " + data.reference_id : "尚未加载数据"; });
    nodes("[data-project-meta]").forEach(function (target) { target.textContent = data ? (data.source_mode === "generated" ? "生成数据 · 本地项目" : "导入数据 · 本地项目") : "课程设计 · 本地项目"; });
    nodes("[data-read-count]").forEach(function (target) { target.textContent = data ? data.read_count : 0; });
  }

  async function startTask(method, payload) {
    try {
      const response = await window.DnaBridge.call(method, payload);
      if (!response.ok) throw new Error(response.error);
      await window.DnaBridge.refreshState();
    } catch (error) { toast(error.message || String(error)); }
  }

  function renderIndexPage() {
    const data = state.app && state.app.dataset && state.app.dataset.loaded ? state.app.dataset : null;
    const index = state.app && state.app.index && state.app.index.built ? state.app.index : null;
    const task = state.app && state.app.task;
    const rebuild = node("#rebuild-index-button");
    if (rebuild) rebuild.disabled = !data || (task && task.status === "running");
    setText("#index-side-reference", data ? "连续字符数组 · " + formatNumber(data.reference_length) + " bp" : "连续字符数组 · 等待数据");
    setText("#index-k", index ? index.k : "—");
    setText("#index-windows", index ? formatNumber(index.window_count) : "0");
    setText("#index-reference-note", data ? "参考序列 " + formatNumber(data.reference_length) + " bp" : "等待参考序列");
    setText("#index-buckets", index ? formatNumber(index.bucket_count) : "0");
    setText("#index-bucket-note", index ? formatNumber(index.used_bucket_count) + " 个已用 · " + formatNumber(index.collision_count) + " 次冲突" : "尚未构建");
    setText("#index-nodes", index ? formatNumber(index.position_node_count) : "0");
    setText("#index-integrity-note", index ? (index.integrity_ok ? "完整 · 节点数等于窗口数" : "完整性检查失败") : "等待完整性检查");
    setText("#index-status-pill", index ? "构建完成" : "等待构建");
    setText("#flow-reference", data ? formatNumber(data.reference_length) + " bp" : "—");
    setText("#flow-window-note", index ? "K=" + index.k + " · 步长 1 · 覆盖全部窗口" : "步长 1 · 覆盖全部窗口");
    setText("#flow-windows", index ? formatNumber(index.window_count) + " 次" : "—");
    setText("#flow-buckets", index ? formatNumber(index.bucket_count) + " 桶" : "—");
    setText("#flow-integrity", index ? (index.integrity_ok ? "100%" : "失败") : "等待");
    nodes(".flow-step").forEach(function (step) { step.classList.toggle("done", Boolean(index)); });
    const body = node("#bucket-table-body");
    if (body) {
      body.replaceChildren();
      if (!index || !index.longest_buckets.length) {
        body.innerHTML = '<tr><td colspan="3">建立索引后显示真实桶链统计</td></tr>';
      } else {
        const maximum = Math.max.apply(null, index.longest_buckets.map(function (item) { return item.position_count; }));
        index.longest_buckets.forEach(function (bucket) {
          const row = document.createElement("tr");
          const positions = bucket.sample_positions_0.map(function (position) { return position + 1; }).join(", ");
          row.innerHTML = "<td><strong>#" + String(bucket.bucket_index).padStart(4, "0") + "</strong><br><code>" + bucket.sample_key + "</code></td><td>冲突链 " + bucket.chain_length + " · 位置节点 " + bucket.position_count + '<br><small title="1-based 位置">' + positions + (bucket.position_count > bucket.sample_positions_0.length ? "…" : "") + '</small></td><td><div class="bucket-bar"><span style="width:' + Math.max(8, bucket.position_count / maximum * 100) + '%"></span></div></td>';
          body.appendChild(row);
        });
      }
    }
    refreshIcons();
  }

  function initIndexPage() {
    node("#refresh-index-button").addEventListener("click", function () { window.DnaBridge.refreshState().then(function () { toast("索引状态已同步"); }).catch(function (error) { toast(error.message); }); });
    node("#rebuild-index-button").addEventListener("click", function () {
      const index = state.app && state.app.index;
      startTask("start_build_index", index && index.built ? index.k : 6);
    });
  }

  function initReadsPage() {
    const toolbar = node(".reads-toolbar");
    const note = node("#read-filter-note");
    const tableWrap = node(".reads-table-wrap");
    const body = node("#reads-table-body");
    const input = node("#read-filter");
    const view = { page: 1, pageSize: 10, sort: "match", query: "", filter: "all" };

    const filter = document.createElement("label");
    filter.className = "reads-filter-select";
    filter.innerHTML = '<span>筛选</span><select aria-label="Reads 结果筛选"><option value="all">全部 Reads</option><option value="matched">仅命中</option><option value="unmatched">仅未命中</option><option value="h0">0 个错配</option><option value="h1">1 个错配</option><option value="h2">2 个错配</option><option value="h3">3 个错配</option><option value="h4">4 个错配</option></select>';
    toolbar.insertBefore(filter, note);

    const sort = document.createElement("div");
    sort.className = "reads-sort-control";
    sort.innerHTML = '<span class="sort-label"><i data-lucide="arrow-up-down" aria-hidden="true"></i><span>排序方式</span></span><div class="segmented-control" data-active="match" role="group" aria-label="Reads 排序方式"><span class="segment-indicator" aria-hidden="true"></span><button type="button" class="sort-button is-active" data-sort="match" aria-pressed="true"><i data-lucide="badge-check" aria-hidden="true"></i><span>匹配优先</span></button><button type="button" class="sort-button" data-sort="id" aria-pressed="false"><i data-lucide="list-ordered" aria-hidden="true"></i><span>序号优先</span></button></div>';
    toolbar.insertBefore(sort, note);

    const pagination = document.createElement("nav");
    pagination.className = "reads-pagination";
    pagination.setAttribute("aria-label", "Reads 分页");
    tableWrap.insertAdjacentElement("afterend", pagination);

    function resultReads() { return state.result ? state.result.reads : []; }

    function readRank(read) {
      if (!read.matched) return 3;
      return read.best_hit.hamming_distance === 0 ? 0 : 1;
    }

    function filteredReads() {
      const query = view.query.toLowerCase();
      return resultReads().filter(function (read) {
        const hamming = read.best_hit && read.best_hit.hamming_distance;
        const statusMatch = view.filter === "all" || (view.filter === "matched" && read.matched) || (view.filter === "unmatched" && !read.matched) || (view.filter.charAt(0) === "h" && read.matched && hamming === Number(view.filter.slice(1)));
        return statusMatch && (!query || (read.id + read.sequence + read.seed).toLowerCase().includes(query));
      }).sort(function (left, right) {
        if (view.sort === "id") return left.id.localeCompare(right.id, undefined, { numeric: true });
        return readRank(left) - readRank(right) || ((left.best_hit && left.best_hit.hamming_distance) || 0) - ((right.best_hit && right.best_hit.hamming_distance) || 0) || left.id.localeCompare(right.id, undefined, { numeric: true });
      });
    }

    function sequenceMarkup(read) {
      const mismatchOffsets = read.best_hit ? read.best_hit.mismatches.map(function (item) { return item.read_offset_0; }) : [];
      const visible = read.sequence.slice(0, 52);
      const html = visible.split("").map(function (base, offset) { return mismatchOffsets.includes(offset) ? '<span class="mismatch-char">' + base + "</span>" : base; }).join("");
      return html + (read.sequence.length > visible.length ? "…" : "");
    }

    function renderPagination(totalPages) {
      pagination.hidden = totalPages <= 1;
      pagination.replaceChildren();
      if (totalPages <= 1) return;
      const add = function (label, disabled, active, action) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = typeof label === "number" ? "pagination-page" + (active ? " is-active" : "") : "pagination-arrow";
        button.disabled = disabled;
        button.innerHTML = typeof label === "number" ? String(label) : '<i data-lucide="' + label + '" aria-hidden="true"></i>';
        button.addEventListener("click", action);
        pagination.appendChild(button);
      };
      add("chevron-left", view.page === 1, false, function () { view.page -= 1; render(); });
      for (let pageNumber = 1; pageNumber <= totalPages; pageNumber += 1) add(pageNumber, false, pageNumber === view.page, function () { view.page = pageNumber; render(); });
      add("chevron-right", view.page === totalPages, false, function () { view.page += 1; render(); });
    }

    function render(animateRows) {
      const reads = filteredReads();
      const totalPages = Math.max(1, Math.ceil(reads.length / view.pageSize));
      view.page = Math.min(view.page, totalPages);
      const start = (view.page - 1) * view.pageSize;
      const pageReads = reads.slice(start, start + view.pageSize);
      body.replaceChildren();
      body.classList.toggle("is-reordering", Boolean(animateRows));
      if (!pageReads.length) body.innerHTML = '<tr><td colspan="6">' + (state.result ? "没有符合筛选条件的 Reads" : "请先在运行工作台完成检索") + "</td></tr>";
      pageReads.forEach(function (read, rowIndex) {
        const best = read.best_hit;
        const resultText = !best ? "未命中" : (best.hamming_distance === 0 ? "完全一致" : "容错命中");
        const pillClass = !best ? " rejected" : (best.hamming_distance === 0 ? " exact" : "");
        const row = document.createElement("tr");
        row.dataset.read = read.id;
        row.tabIndex = 0;
        row.style.setProperty("--row-index", rowIndex);
        row.title = "点击回到工作台定位 " + read.id;
        row.innerHTML = '<td>' + read.id + '</td><td><span class="read-string" title="' + read.sequence + '">' + sequenceMarkup(read) + '</span></td><td><code>' + read.seed + '</code></td><td>' + (best ? best.start_1 + (read.hits.length > 1 ? "（" + read.hits.length + " 个命中）" : "") : "未命中") + '</td><td>' + (best ? best.hamming_distance + " / " + state.result.parameters.max_mismatches : "—") + '</td><td><span class="result-pill' + pillClass + '">' + resultText + "</span></td>";
        const open = function () { sessionStorage.setItem("selected_read_id", read.id); location.href = "../index.html"; };
        row.addEventListener("click", open);
        row.addEventListener("keydown", function (event) { if (event.key === "Enter" || event.key === " ") open(); });
        body.appendChild(row);
      });
      const end = Math.min(start + view.pageSize, reads.length);
      note.textContent = reads.length ? "第 " + (start + 1) + "–" + end + " 条 · 共 " + reads.length + " 条 Reads" : "没有可显示的 Reads";
      renderPagination(totalPages);
      refreshIcons();
    }

    input.addEventListener("input", function () { view.query = input.value.trim(); view.page = 1; render(); });
    filter.querySelector("select").addEventListener("change", function (event) { view.filter = event.target.value; view.page = 1; render(); });
    sort.querySelectorAll(".sort-button").forEach(function (button) {
      button.addEventListener("click", function () {
        view.sort = button.dataset.sort;
        view.page = 1;
        sort.querySelector(".segmented-control").dataset.active = view.sort;
        sort.querySelectorAll(".sort-button").forEach(function (item) { item.classList.toggle("is-active", item === button); item.setAttribute("aria-pressed", String(item === button)); });
        render(true);
      });
    });
    node("#go-import-button").addEventListener("click", function () { sessionStorage.setItem("open_input_mode", "import"); location.href = "../index.html"; });
    node("#export-reads-button").addEventListener("click", exportReport);
    state.renderReads = render;
    render();
  }

  function renderReadsPage() {
    const data = state.app && state.app.dataset && state.app.dataset.loaded ? state.app.dataset : null;
    const summary = state.result && state.result.summary;
    setText("#reads-side-summary", data ? data.read_count + " 条 Reads · 平均 " + data.average_read_length + " bp" : "尚未加载 Reads");
    setText("#reads-side-result", summary ? summary.matched_read_count + " 条命中 · " + summary.unmatched_read_count + " 条未命中" : "运行检索后显示结果");
    setText("#reads-result-pill", summary ? summary.matched_read_count + " 条命中" : "0 条命中");
    node("#export-reads-button").disabled = !state.result;
    if (state.renderReads) state.renderReads();
  }

  async function exportReport() {
    try {
      const selected = await window.DnaBridge.call("choose_export_directory");
      if (!selected.ok) throw new Error(selected.error);
      if (!selected.cancelled) await startTask("start_export_results", { output_directory: selected.path });
    } catch (error) { toast(error.message || String(error)); }
  }

  function renderReportPage() {
    const data = state.app && state.app.dataset && state.app.dataset.loaded ? state.app.dataset : null;
    const result = state.result;
    const summary = result && result.summary;
    const parameters = result && result.parameters;
    setText("#report-run-id", result ? result.run_id : "尚未完成检索");
    setText("#report-hits", summary ? summary.matched_read_count + " / " + summary.read_count : "0 / 0");
    setText("#report-rate", summary ? summary.match_rate.toFixed(1) + "% · " + summary.unmatched_read_count + " 条未命中" : "等待检索");
    setText("#report-threshold", parameters ? parameters.max_mismatches + " bp" : "—");
    setText("#report-candidates", summary ? formatNumber(summary.candidate_count) : "0");
    setText("#report-elapsed", summary ? Number(summary.elapsed_ms).toFixed(3) + " ms" : "0 ms");
    setText("#report-k", parameters ? "本地 · K=" + parameters.k : "本地 · 等待运行");
    setText("#report-status-pill", result ? "已完成" : "等待运行");
    setText("#meta-dataset", data ? data.dataset_id + " · seed " + (data.random_seed === null ? "外部数据" : data.random_seed) : "—");
    setText("#meta-reference", data ? fileName(data.reference_path) + " · " + formatNumber(data.reference_length) + " bp" : "—");
    setText("#meta-reads", data ? fileName(data.reads_path) + " · " + data.read_count + " 条" : "—");
    setText("#meta-k", parameters ? parameters.k + " bp · 步长 1" : "—");
    setText("#meta-threshold", parameters ? parameters.max_mismatches + " 个错配 · " + (parameters.early_prune ? "提前剪枝" : "完整比较") : "—");
    setText("#method-seed", parameters ? "从每条 Read 截取前 " + parameters.k + " 个碱基，作为哈希表键。" : "从每条 Read 截取前 K 个碱基，作为哈希表键。");
    setText("#method-candidates", summary ? "沿位置单链表遍历 " + formatNumber(summary.candidate_count) + " 个种子候选位置。" : "沿单链表读取该 K-mer 的所有参考位置。");
    setText("#method-compare", summary ? "比较 " + formatNumber(summary.compared_base_count) + " 个字符，提前剪枝 " + formatNumber(summary.pruned_candidate_count) + " 个候选。" : "逐字符计算汉明距离，超过阈值即剪枝。");
    const distribution = node("#report-distribution");
    if (distribution) {
      const values = summary ? summary.mismatch_distribution : [0, 0, 0, 0, 0];
      const maximum = Math.max(1, Math.max.apply(null, values));
      Array.from(distribution.children).forEach(function (item, index) {
        item.querySelector(".distribution-bar span").style.height = values[index] / maximum * 100 + "%";
        item.querySelector("strong").textContent = values[index];
      });
    }
    node("#export-report-button").disabled = !result;
  }

  function initReportPage() {
    node("#print-report-button").addEventListener("click", function () { window.print(); });
    node("#export-report-button").addEventListener("click", exportReport);
  }

  function render() {
    setCommonState();
    if (page === "index-state.html") renderIndexPage();
    else if (page === "reads.html") renderReadsPage();
    else if (page === "report.html") renderReportPage();
    refreshIcons();
  }

  function init() {
    nodes("[data-toast]").forEach(function (target) { target.addEventListener("click", function () { toast(target.dataset.toast); }); });
    if (page === "index-state.html") initIndexPage();
    else if (page === "reads.html") initReadsPage();
    else if (page === "report.html") initReportPage();
    window.DnaStore.subscribe(function (snapshot) {
      state.app = snapshot.app;
      state.result = snapshot.result;
      render();
    });
    render();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
}());
