"""Export the last search with dataset and index metadata."""

from pathlib import Path
from typing import Any

from dna_retrieval_engine.storage.result_export import export_result_files

from .dataset_service import DatasetService
from .search_service import SearchService


class ReportService:
    def __init__(self, dataset_service: DatasetService, search_service: SearchService) -> None:
        self.dataset_service = dataset_service
        self.search_service = search_service

    def payload(self) -> dict[str, Any]:
        result = self.search_service.last_result()
        if result is None:
            raise ValueError("尚未完成检索，无法导出报告")
        return {
            "schema_version": 1,
            "dataset": self.dataset_service.state(),
            "index": self.search_service.index_state(),
            **result,
        }

    def export(self, output_directory: str | Path) -> list[str]:
        folder = Path(output_directory).expanduser().resolve()
        if not folder.is_dir():
            raise ValueError("导出目录不存在或不是文件夹")
        return [str(path) for path in export_result_files(folder, self.payload())]
