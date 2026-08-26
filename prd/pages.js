(function () {
  "use strict";

  function refreshIcons() {
    if (window.lucide && typeof window.lucide.createIcons === "function") window.lucide.createIcons();
  }

  function toast(message) {
    const node = document.querySelector("#toast");
    if (!node) return;
    node.textContent = message;
    node.classList.add("is-visible");
    window.clearTimeout(toast.timer);
    toast.timer = window.setTimeout(function () { node.classList.remove("is-visible"); }, 2400);
  }

  function wireToasts() {
    document.querySelectorAll("[data-toast]").forEach(function (node) {
      node.addEventListener("click", function () { toast(node.dataset.toast); });
    });
  }

  function buildReadData() {
    const alphabet = ["A", "T", "C", "G"];
    const exactIds = [7, 11, 50];
    const rejectedIds = [13, 29, 46];
    return Array.from({ length: 50 }, function (_, index) {
      const number = index + 1;
      const hamming = exactIds.includes(number) ? 0 : (rejectedIds.includes(number) ? 3 : (number % 2) + 1);
      const mismatchPositions = [7, 18, 25].slice(0, hamming);
      const bases = Array.from({ length: 30 }, function (__, baseIndex) {
        const base = alphabet[(number * 3 + baseIndex * 5 + Math.floor(baseIndex / 4)) % 4];
        if (!mismatchPositions.includes(baseIndex)) return base;
        return alphabet[(alphabet.indexOf(base) + 1) % 4];
      });
      return {
        number: number,
        id: "READ-" + String(number).padStart(3, "0"),
        sequence: bases.join(""),
        seed: bases.slice(0, 6).join(""),
        position: rejectedIds.includes(number) ? "未命中" : 390 + number * 37,
        hamming: hamming,
        mismatchPositions: mismatchPositions,
        result: exactIds.includes(number) ? "完全一致" : (rejectedIds.includes(number) ? "未命中" : "容错命中")
      };
    });
  }

  function sequenceMarkup(read) {
    return read.sequence.split("").map(function (base, index) {
      return read.mismatchPositions.includes(index) ? '<span class="mismatch-char">' + base + "</span>" : base;
    }).join("");
  }

  function initReadsExplorer() {
    const input = document.querySelector("#read-filter");
    const body = document.querySelector("#reads-table-body");
    const toolbar = document.querySelector(".reads-toolbar");
    const note = document.querySelector("#read-filter-note");
    const tableWrap = document.querySelector(".reads-table-wrap");
    if (!input || !body || !toolbar || !tableWrap) return;

    const reads = buildReadData();
    const view = { page: 1, pageSize: 10, sort: "match", query: "" };
    const sortControl = document.createElement("div");
    sortControl.className = "reads-sort-control";
    sortControl.innerHTML = '<span class="sort-label"><i data-lucide="arrow-up-down" aria-hidden="true"></i><span>排序方式</span></span><div class="segmented-control" data-active="match" role="group" aria-label="Reads 排序方式"><span class="segment-indicator" aria-hidden="true"></span><button type="button" class="sort-button is-active" data-sort="match" aria-pressed="true"><i data-lucide="badge-check" aria-hidden="true"></i><span>匹配优先</span></button><button type="button" class="sort-button" data-sort="id" aria-pressed="false"><i data-lucide="list-ordered" aria-hidden="true"></i><span>序号优先</span></button></div>';
    toolbar.insertBefore(sortControl, note);
    note.setAttribute("aria-live", "polite");

    const pagination = document.createElement("nav");
    pagination.className = "reads-pagination";
    pagination.setAttribute("aria-label", "Reads 分页");
    tableWrap.insertAdjacentElement("afterend", pagination);

    function filteredReads() {
      const query = view.query.toLowerCase();
      const filtered = reads.filter(function (read) {
        return !query || (read.id + read.sequence + read.seed + read.result).toLowerCase().includes(query);
      });
      return filtered.sort(function (a, b) {
        if (view.sort === "id") return a.number - b.number;
        const rank = { "完全一致": 0, "容错命中": 1, "未命中": 2 };
        return rank[a.result] - rank[b.result] || a.hamming - b.hamming || a.number - b.number;
      });
    }

    function renderPagination(totalPages) {
      pagination.hidden = totalPages <= 1;
      pagination.replaceChildren();
      if (totalPages <= 1) return;
      const previous = document.createElement("button");
      previous.type = "button";
      previous.className = "pagination-arrow";
      previous.disabled = view.page === 1;
      previous.setAttribute("aria-label", "上一页");
      previous.innerHTML = '<i data-lucide="chevron-left" aria-hidden="true"></i>';
      previous.addEventListener("click", function () { view.page -= 1; render(); });
      pagination.appendChild(previous);
      for (let page = 1; page <= totalPages; page += 1) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "pagination-page" + (page === view.page ? " is-active" : "");
        button.textContent = page;
        button.setAttribute("aria-label", "第 " + page + " 页");
        if (page === view.page) button.setAttribute("aria-current", "page");
        button.addEventListener("click", function () { view.page = page; render(); });
        pagination.appendChild(button);
      }
      const next = document.createElement("button");
      next.type = "button";
      next.className = "pagination-arrow";
      next.disabled = view.page === totalPages;
      next.setAttribute("aria-label", "下一页");
      next.innerHTML = '<i data-lucide="chevron-right" aria-hidden="true"></i>';
      next.addEventListener("click", function () { view.page += 1; render(); });
      pagination.appendChild(next);
    }

    function render(animateRows) {
      const filtered = filteredReads();
      const totalPages = Math.max(1, Math.ceil(filtered.length / view.pageSize));
      view.page = Math.min(view.page, totalPages);
      const start = (view.page - 1) * view.pageSize;
      const pageReads = filtered.slice(start, start + view.pageSize);
      body.replaceChildren();
      body.classList.toggle("is-reordering", Boolean(animateRows));
      pageReads.forEach(function (read, rowIndex) {
        const row = document.createElement("tr");
        row.style.setProperty("--row-index", rowIndex);
        const pillClass = read.result === "完全一致" ? " exact" : (read.result === "未命中" ? " rejected" : "");
        row.innerHTML = '<td>' + read.id + '</td><td><span class="read-string">' + sequenceMarkup(read) + '</span></td><td><code>' + read.seed + '</code></td><td>' + read.position + '</td><td>' + read.hamming + ' / 2</td><td><span class="result-pill' + pillClass + '">' + read.result + '</span></td>';
        body.appendChild(row);
      });
      const end = Math.min(start + view.pageSize, filtered.length);
      if (note) note.textContent = filtered.length ? "第 " + (start + 1) + "–" + end + " 条 · 共 " + filtered.length + " 条 Reads" : "没有符合条件的 Reads";
      renderPagination(totalPages);
      refreshIcons();
      window.clearTimeout(render.animationTimer);
      if (animateRows) render.animationTimer = window.setTimeout(function () { body.classList.remove("is-reordering"); }, 420);
    }

    input.addEventListener("input", function () { view.query = input.value.trim(); view.page = 1; render(); });
    sortControl.querySelectorAll(".sort-button").forEach(function (button) {
      button.addEventListener("click", function () {
        if (view.sort === button.dataset.sort) return;
        view.sort = button.dataset.sort;
        view.page = 1;
        const segmented = sortControl.querySelector(".segmented-control");
        if (segmented) segmented.dataset.active = view.sort;
        sortControl.querySelectorAll(".sort-button").forEach(function (item) {
          const isActive = item === button;
          item.classList.toggle("is-active", isActive);
          item.setAttribute("aria-pressed", String(isActive));
        });
        render(true);
      });
    });
    render();
  }

  function init() {
    refreshIcons();
    wireToasts();
    initReadsExplorer();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
}());
