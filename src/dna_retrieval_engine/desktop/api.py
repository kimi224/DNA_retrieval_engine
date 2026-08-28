"""Small pywebview API boundary; business logic stays in shared services."""

import json
import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from dna_retrieval_engine.config import DEFAULT_K, K_MAX, K_MIN, MISMATCH_MAX, MISMATCH_MIN
from dna_retrieval_engine.services.dataset_generator import DatasetGenerator
from dna_retrieval_engine.services.dataset_service import DatasetService
from dna_retrieval_engine.services.report_service import ReportService
from dna_retrieval_engine.services.search_service import SearchService

from .task_controller import TaskContext, TaskController


class DesktopApi:
    def __init__(self) -> None:
        # pywebview recursively inspects public attributes on js_api objects.
        # Keep every internal service private so only the explicit methods
        # below are exposed to JavaScript.
        self._window: Any = None
        self._datasets = DatasetService()
        self._search = SearchService(self._datasets)
        self._generator = DatasetGenerator(self._datasets)
        self._reports = ReportService(self._datasets, self._search)
        self._frontend_ready = False
        # Task progress is read by the serialized frontend poller.  Avoid
        # calling evaluate_js from worker threads because WebView2 operations
        # belong to the GUI message-pump thread.
        self._tasks = TaskController()

    def _close(self, *_args: Any) -> None:
        self._tasks.close()
        self._window = None

    def _bind_window(self, window: Any) -> None:
        self._window = window

    @staticmethod
    def _response(action: Callable[[], Any]) -> dict[str, Any]:
        try:
            return {"ok": True, "value": action()}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def get_state(self) -> dict[str, Any]:
        result = self._search.result_summary()
        task = self._tasks.snapshot()
        dataset = self._datasets.state()
        index = self._search.index_state()
        has_dataset = bool(dataset.get("loaded"))
        has_result = result is not None
        task_running = task["status"] == "running"
        return {
            "bridge_ready": True,
            "task": task,
            "dataset": dataset,
            "index": index,
            "has_result": has_result,
            "result_summary": result["summary"] if result else None,
            "run_id": result["run_id"] if result else None,
            # Keep permission decisions server-authoritative so every page
            # applies the same no-data/running/result rules.
            "capabilities": {
                "can_choose_input": not task_running,
                "can_load_dataset": not task_running,
                "can_configure": not task_running,
                "can_run_search": has_dataset and not task_running,
                "can_export": has_result and not task_running,
                "can_cancel": task_running,
            },
        }

    def notify_frontend_ready(self, details: dict[str, Any] | None = None) -> dict[str, Any]:
        """Record the full UI/bridge/router handshake for startup diagnostics."""
        self._frontend_ready = True
        payload = {
            "ready": True,
            "timestamp": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "details": details if isinstance(details, dict) else {},
        }
        probe_path = os.environ.get("DNA_FRONTEND_READY_FILE")
        if probe_path:
            path = Path(probe_path).resolve()
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            os.replace(temporary, path)
        return {"ok": True, "ready": True}

    def _choose_dialog(self, kind: str, file_types: tuple[str, ...] = ()) -> dict[str, Any]:
        if self._window is None:
            return {"ok": False, "error": "窗口尚未初始化"}
        if self._tasks.is_running():
            return {"ok": False, "error": "当前任务正在运行，请等待完成"}
        try:
            import webview

            dialog_type = webview.FOLDER_DIALOG if kind == "folder" else webview.OPEN_DIALOG
            selected = self._window.create_file_dialog(
                dialog_type,
                allow_multiple=False,
                file_types=file_types,
            )
            path = selected[0] if selected else None
            return {"ok": True, "cancelled": path is None, "path": path}
        except Exception as exc:
            return {"ok": False, "error": f"无法打开系统文件对话框：{exc}"}

    def choose_output_directory(self) -> dict[str, Any]:
        return self._choose_dialog("folder")

    def choose_dataset_directory(self) -> dict[str, Any]:
        return self._choose_dialog("folder")

    def choose_export_directory(self) -> dict[str, Any]:
        return self._choose_dialog("folder")

    def choose_reference_file(self) -> dict[str, Any]:
        return self._choose_dialog("file", ("FASTA files (*.fa;*.fasta)", "All files (*.*)"))

    def choose_reads_file(self) -> dict[str, Any]:
        return self._choose_dialog("file", ("FASTQ files (*.fq;*.fastq)", "All files (*.*)"))

    def choose_truth_file(self) -> dict[str, Any]:
        return self._choose_dialog("file", ("JSON files (*.json)", "All files (*.*)"))

    def _load_task(self, loader: Callable[[], Any], context: TaskContext) -> dict[str, Any]:
        context.update(15, "正在解析并校验数据文件")
        loaded = loader()
        context.check_cancelled()
        self._search.clear()
        context.update(60, "正在构建默认 K-mer 索引")
        index = self._search.build_index(DEFAULT_K)
        context.update(95, "数据与索引已就绪")
        return {"dataset": loaded.to_dict(), "index": index}

    def start_generate_dataset(self, options: dict[str, Any]) -> dict[str, Any]:
        options = options if isinstance(options, dict) else {}
        output = str(options.get("output_directory", "")).strip()
        seed_value = options.get("seed")
        reference_length = options.get("reference_length")
        if not output:
            return {"ok": False, "error": "请先选择生成数据的保存位置"}

        def worker(context: TaskContext) -> dict[str, Any]:
            context.update(8, "正在生成可复现实验数据")
            loaded = self._generator.generate(
                output,
                seed=None if seed_value in (None, "") else int(seed_value),
                reference_length=None if reference_length in (None, "") else int(reference_length),
            )
            context.check_cancelled()
            self._search.clear()
            context.update(65, "生成数据已自检，正在建立默认索引")
            index = self._search.build_index(DEFAULT_K)
            return {"dataset": loaded.to_dict(), "index": index}

        return self._tasks.start("generate_dataset", worker)

    def start_load_dataset_folder(self, directory: str) -> dict[str, Any]:
        if not str(directory).strip():
            return {"ok": False, "error": "请选择数据集文件夹"}
        return self._tasks.start(
            "load_dataset",
            lambda context: self._load_task(lambda: self._datasets.load_folder(directory), context),
        )

    def start_load_dataset_files(self, paths: dict[str, Any]) -> dict[str, Any]:
        paths = paths if isinstance(paths, dict) else {}
        reference = str(paths.get("reference_path", "")).strip()
        reads = str(paths.get("reads_path", "")).strip()
        truth = str(paths.get("truth_path", "")).strip() or None
        if not reference or not reads:
            return {"ok": False, "error": "参考序列与 Reads 文件必须都已选择"}
        return self._tasks.start(
            "load_dataset",
            lambda context: self._load_task(
                lambda: self._datasets.load_files(reference, reads, truth), context
            ),
        )

    def start_search(self, options: dict[str, Any]) -> dict[str, Any]:
        options = options if isinstance(options, dict) else {}
        if self._datasets.current is None:
            return {"ok": False, "error": "请先生成或加载数据集"}
        try:
            k = int(options.get("k", DEFAULT_K))
            mismatches = int(options.get("max_mismatches", 2))
        except (TypeError, ValueError):
            return {"ok": False, "error": "检索参数格式无效"}
        if not K_MIN <= k <= K_MAX:
            return {"ok": False, "error": f"K-mer 长度必须为 {K_MIN}-{K_MAX}"}
        if not MISMATCH_MIN <= mismatches <= MISMATCH_MAX:
            return {"ok": False, "error": f"最大错配数必须为 {MISMATCH_MIN}-{MISMATCH_MAX}"}
        early_prune = bool(options.get("early_prune", True))

        def worker(context: TaskContext) -> dict[str, Any]:
            context.update(15, "正在检查 K-mer 索引")
            self._search.ensure_index(k)
            context.check_cancelled()
            context.update(45, "正在检索 50 条 Reads")
            result = self._search.search(k, mismatches, early_prune)
            context.update(95, "正在汇总候选与剪枝统计")
            return {"run_id": result["run_id"], "summary": result["summary"]}

        return self._tasks.start("search", worker)

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        return self._tasks.cancel(str(task_id))

    def get_last_result(self) -> dict[str, Any]:
        result = self._search.last_result()
        return {
            "ok": result is not None,
            "result": result,
            "error": None if result else "尚未完成检索",
        }

    def get_read_detail(self, read_id: str) -> dict[str, Any]:
        return self._response(lambda: self._search.read_detail(read_id))

    def get_reference_window(self, start: int, length: int) -> dict[str, Any]:
        return self._response(lambda: self._datasets.reference_window(int(start), int(length)))

    def start_export_results(self, options: dict[str, Any]) -> dict[str, Any]:
        options = options if isinstance(options, dict) else {}
        output = str(options.get("output_directory", "")).strip()
        if not output:
            return {"ok": False, "error": "请选择报告导出目录"}
        if self._search.last_result() is None:
            return {"ok": False, "error": "尚未完成检索，无法导出报告"}

        def worker(context: TaskContext) -> dict[str, Any]:
            context.update(35, "正在生成 JSON 与 CSV 报告")
            files = self._reports.export(Path(output))
            return {"files": files}

        return self._tasks.start("export_results", worker)
