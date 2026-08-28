"""Small pywebview API boundary; business logic stays in shared services."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from dna_retrieval_engine.config import DEFAULT_K, K_MAX, K_MIN, MISMATCH_MAX, MISMATCH_MIN
from dna_retrieval_engine.services.dataset_generator import DatasetGenerator
from dna_retrieval_engine.services.dataset_service import DatasetService
from dna_retrieval_engine.services.report_service import ReportService
from dna_retrieval_engine.services.search_service import SearchService

from .task_controller import TaskContext, TaskController, task_event_script


class DesktopApi:
    def __init__(self) -> None:
        self.window: Any = None
        self.datasets = DatasetService()
        self.search = SearchService(self.datasets)
        self.generator = DatasetGenerator(self.datasets)
        self.reports = ReportService(self.datasets, self.search)
        self.tasks = TaskController(self._push_task_state)

    def bind_window(self, window: Any) -> None:
        self.window = window

    def _push_task_state(self, task_state: dict[str, Any]) -> None:
        if self.window is not None:
            # A window can close while a daemon worker is finishing.  UI push
            # is best-effort; polling get_state() remains authoritative.
            try:
                self.window.evaluate_js(task_event_script(task_state))
            except Exception:
                pass

    @staticmethod
    def _response(action: Callable[[], Any]) -> dict[str, Any]:
        try:
            return {"ok": True, "value": action()}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def get_state(self) -> dict[str, Any]:
        result = self.search.last_result()
        return {
            "bridge_ready": True,
            "task": self.tasks.snapshot(),
            "dataset": self.datasets.state(),
            "index": self.search.index_state(),
            "has_result": result is not None,
            "result_summary": result["summary"] if result else None,
            "run_id": result["run_id"] if result else None,
        }

    def _choose_dialog(self, kind: str, file_types: tuple[str, ...] = ()) -> dict[str, Any]:
        if self.window is None:
            return {"ok": False, "error": "窗口尚未初始化"}
        try:
            import webview

            dialog_type = webview.FOLDER_DIALOG if kind == "folder" else webview.OPEN_DIALOG
            selected = self.window.create_file_dialog(
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
        self.search.clear()
        context.update(60, "正在构建默认 K-mer 索引")
        index = self.search.build_index(DEFAULT_K)
        context.update(95, "数据与索引已就绪")
        return {"dataset": loaded.to_dict(), "index": index}

    def start_generate_dataset(self, options: dict[str, Any]) -> dict[str, Any]:
        output = str(options.get("output_directory", "")).strip()
        seed_value = options.get("seed")
        reference_length = options.get("reference_length")
        if not output:
            return {"ok": False, "error": "请先选择生成数据的保存位置"}

        def worker(context: TaskContext) -> dict[str, Any]:
            context.update(8, "正在生成可复现实验数据")
            loaded = self.generator.generate(
                output,
                seed=None if seed_value in (None, "") else int(seed_value),
                reference_length=None if reference_length in (None, "") else int(reference_length),
            )
            context.check_cancelled()
            self.search.clear()
            context.update(65, "生成数据已自检，正在建立默认索引")
            index = self.search.build_index(DEFAULT_K)
            return {"dataset": loaded.to_dict(), "index": index}

        return self.tasks.start("generate_dataset", worker)

    def start_load_dataset_folder(self, directory: str) -> dict[str, Any]:
        if not str(directory).strip():
            return {"ok": False, "error": "请选择数据集文件夹"}
        return self.tasks.start(
            "load_dataset",
            lambda context: self._load_task(lambda: self.datasets.load_folder(directory), context),
        )

    def start_load_dataset_files(self, paths: dict[str, Any]) -> dict[str, Any]:
        reference = str(paths.get("reference_path", "")).strip()
        reads = str(paths.get("reads_path", "")).strip()
        truth = str(paths.get("truth_path", "")).strip() or None
        if not reference or not reads:
            return {"ok": False, "error": "参考序列与 Reads 文件必须都已选择"}
        return self.tasks.start(
            "load_dataset",
            lambda context: self._load_task(
                lambda: self.datasets.load_files(reference, reads, truth), context
            ),
        )

    def start_build_index(self, k: int) -> dict[str, Any]:
        if self.datasets.current is None:
            return {"ok": False, "error": "请先生成或加载数据集"}
        try:
            k = int(k)
        except (TypeError, ValueError):
            return {"ok": False, "error": f"K-mer 长度必须为 {K_MIN}-{K_MAX}"}
        if not K_MIN <= k <= K_MAX:
            return {"ok": False, "error": f"K-mer 长度必须为 {K_MIN}-{K_MAX}"}

        def worker(context: TaskContext) -> dict[str, Any]:
            context.update(20, "正在滑动参考序列窗口")
            result = self.search.build_index(k)
            context.update(90, "正在校验节点数与窗口数")
            return result

        return self.tasks.start("build_index", worker)

    def start_search(self, options: dict[str, Any]) -> dict[str, Any]:
        if self.datasets.current is None:
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
            self.search.ensure_index(k)
            context.check_cancelled()
            context.update(45, "正在检索 50 条 Reads")
            result = self.search.search(k, mismatches, early_prune)
            context.update(95, "正在汇总候选与剪枝统计")
            return {"run_id": result["run_id"], "summary": result["summary"]}

        return self.tasks.start("search", worker)

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        return self.tasks.cancel(str(task_id))

    def get_last_result(self) -> dict[str, Any]:
        result = self.search.last_result()
        return {
            "ok": result is not None,
            "result": result,
            "error": None if result else "尚未完成检索",
        }

    def get_read_detail(self, read_id: str) -> dict[str, Any]:
        return self._response(lambda: self.search.read_detail(read_id))

    def get_reference_window(self, start: int, length: int) -> dict[str, Any]:
        return self._response(lambda: self.datasets.reference_window(int(start), int(length)))

    def start_export_results(self, options: dict[str, Any]) -> dict[str, Any]:
        output = str(options.get("output_directory", "")).strip()
        if not output:
            return {"ok": False, "error": "请选择报告导出目录"}
        if self.search.last_result() is None:
            return {"ok": False, "error": "尚未完成检索，无法导出报告"}

        def worker(context: TaskContext) -> dict[str, Any]:
            context.update(35, "正在生成 JSON 与 CSV 报告")
            files = self.reports.export(Path(output))
            return {"files": files}

        return self.tasks.start("export_results", worker)
