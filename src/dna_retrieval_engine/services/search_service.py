"""Own the current hand-built index and latest batch result."""

from copy import deepcopy
from datetime import datetime
from threading import RLock
from time import perf_counter
from typing import Any

from dna_retrieval_engine.config import K_MAX, K_MIN, MISMATCH_MAX
from dna_retrieval_engine.core.kmer_index import KmerIndex
from dna_retrieval_engine.core.matcher import TolerantMatcher
from dna_retrieval_engine.models import BatchResult

from .dataset_service import DatasetService, LoadedDataset


class SearchService:
    def __init__(self, dataset_service: DatasetService) -> None:
        self.dataset_service = dataset_service
        self._lock = RLock()
        self._index: KmerIndex | None = None
        self._indexed_dataset: LoadedDataset | None = None
        self._last_result: BatchResult | None = None
        self._index_snapshot: dict[str, Any] | None = None
        self._last_result_payload: dict[str, Any] | None = None

    def clear(self) -> None:
        with self._lock:
            self._index = None
            self._indexed_dataset = None
            self._last_result = None
            self._index_snapshot = None
            self._last_result_payload = None

    def build_index(self, k: int) -> dict[str, Any]:
        if not K_MIN <= k <= K_MAX:
            raise ValueError(f"K-mer 长度必须为 {K_MIN}-{K_MAX}")
        dataset = self.dataset_service.current
        if dataset is None:
            raise ValueError("请先生成或加载数据集")
        index = KmerIndex.build(dataset.reference, k)
        snapshot = {"built": True, **index.to_dict()}
        with self._lock:
            self._index = index
            self._indexed_dataset = dataset
            self._last_result = None
            self._index_snapshot = snapshot
            self._last_result_payload = None
        return deepcopy(snapshot)

    def ensure_index(self, k: int) -> KmerIndex:
        dataset = self.dataset_service.current
        if dataset is None:
            raise ValueError("请先生成或加载数据集")
        with self._lock:
            current = self._index
            valid = current is not None and self._indexed_dataset is dataset and current.k == k
        if not valid:
            self.build_index(k)
        assert self._index is not None
        return self._index

    def search(self, k: int, max_mismatches: int, early_prune: bool = True) -> dict[str, Any]:
        if not 0 <= max_mismatches <= MISMATCH_MAX:
            raise ValueError(f"最大错配数必须为 0-{MISMATCH_MAX}")
        dataset = self.dataset_service.current
        if dataset is None:
            raise ValueError("请先生成或加载数据集")
        index = self.ensure_index(k)
        matcher = TolerantMatcher(index)
        started = perf_counter()
        results = [
            matcher.search_read(
                read,
                max_mismatches,
                early_prune=early_prune,
                truth_start_0=dataset.truth_start(read.id),
            )
            for read in dataset.reads
        ]
        elapsed_ms = (perf_counter() - started) * 1000
        run_id = f"run-{datetime.now():%Y%m%d-%H%M%S-%f}"
        batch = BatchResult(
            run_id=run_id,
            parameters={"k": k, "max_mismatches": max_mismatches, "early_prune": early_prune},
            reference_id=dataset.reference_id,
            reference_length=dataset.reference.length,
            reads=results,
            elapsed_ms=elapsed_ms,
        )
        with self._lock:
            self._last_result = batch
            self._last_result_payload = batch.to_dict()
        return deepcopy(self._last_result_payload)

    def index_state(self) -> dict[str, Any]:
        with self._lock:
            snapshot = self._index_snapshot
        return {"built": False} if snapshot is None else deepcopy(snapshot)

    def last_result(self) -> dict[str, Any] | None:
        with self._lock:
            payload = self._last_result_payload
        return deepcopy(payload) if payload else None

    def result_summary(self) -> dict[str, Any] | None:
        with self._lock:
            payload = self._last_result_payload
        if payload is None:
            return None
        return {"run_id": payload["run_id"], "summary": deepcopy(payload["summary"])}

    def read_detail(self, read_id: str) -> dict[str, Any]:
        result = self.last_result()
        if result is None:
            raise ValueError("尚未完成检索")
        for read in result["reads"]:
            if read["id"] == read_id:
                return read
        raise ValueError(f"未找到 Read：{read_id}")
