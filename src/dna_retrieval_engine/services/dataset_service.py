"""Load and retain one validated dataset without corrupting prior good state."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from threading import RLock
from typing import Any

from dna_retrieval_engine.config import (
    READ_COUNT,
    READ_LENGTH_MAX,
    READ_LENGTH_MIN,
    REFERENCE_LENGTH_MAX,
    REFERENCE_LENGTH_MIN,
)
from dna_retrieval_engine.core.genome_buffer import GenomeBuffer
from dna_retrieval_engine.models import DatasetDescriptor, ReadRecord
from dna_retrieval_engine.storage.dataset_discovery import descriptor_from_files, discover_dataset
from dna_retrieval_engine.storage.fasta import read_fasta
from dna_retrieval_engine.storage.fastq import read_fastq
from dna_retrieval_engine.storage.truth import read_truth


@dataclass(slots=True)
class LoadedDataset:
    descriptor: DatasetDescriptor
    reference_id: str
    reference: GenomeBuffer
    reads: list[ReadRecord]
    truth: dict[str, Any] | None

    def truth_start(self, read_id: str) -> int | None:
        if self.truth is None:
            return None
        for item in self.truth["reads"]:
            if item.get("id") == read_id:
                value = item.get("reference_start_0")
                return value if isinstance(value, int) else None
        return None

    def to_dict(self) -> dict[str, Any]:
        truth = self.truth or {}
        return {
            "loaded": True,
            "dataset_id": truth.get("dataset_id")
            or (
                self.descriptor.dataset_directory.name
                if self.descriptor.dataset_directory
                else "external-data"
            ),
            "source_mode": self.descriptor.source_mode,
            "dataset_directory": (
                str(self.descriptor.dataset_directory)
                if self.descriptor.dataset_directory
                else None
            ),
            "reference_path": str(self.descriptor.reference_path),
            "reads_path": str(self.descriptor.reads_path),
            "truth_path": str(self.descriptor.truth_path) if self.descriptor.truth_path else None,
            "reference_id": self.reference_id,
            "reference_length": self.reference.length,
            "read_count": len(self.reads),
            "min_read_length": min(len(read.sequence) for read in self.reads),
            "max_read_length": max(len(read.sequence) for read in self.reads),
            "average_read_length": round(
                sum(len(read.sequence) for read in self.reads) / len(self.reads), 2
            ),
            "random_seed": truth.get("random_seed"),
            "has_truth": self.truth is not None,
            "coordinate_system": truth.get(
                "coordinate_system",
                {"internal": "0-based half-open", "display": "1-based inclusive"},
            ),
        }


class DatasetService:
    def __init__(self) -> None:
        self._lock = RLock()
        self._current: LoadedDataset | None = None

    @property
    def current(self) -> LoadedDataset | None:
        with self._lock:
            return self._current

    @staticmethod
    def _file_sha256(path: Path) -> str:
        digest = sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(64 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def load(self, descriptor: DatasetDescriptor) -> LoadedDataset:
        reference_id, sequence = read_fasta(descriptor.reference_path)
        if not REFERENCE_LENGTH_MIN <= len(sequence) <= REFERENCE_LENGTH_MAX:
            raise ValueError(
                f"参考序列长度必须为 {REFERENCE_LENGTH_MIN}-{REFERENCE_LENGTH_MAX} bp，"
                f"实际为 {len(sequence)} bp"
            )
        reads = read_fastq(descriptor.reads_path)
        if len(reads) != READ_COUNT:
            raise ValueError(
                f"课程数据集必须恰好包含 {READ_COUNT} 条 Reads，实际为 {len(reads)} 条"
            )
        for read in reads:
            if not READ_LENGTH_MIN <= len(read.sequence) <= READ_LENGTH_MAX:
                raise ValueError(
                    f"{read.id} 长度必须为 {READ_LENGTH_MIN}-{READ_LENGTH_MAX} bp，"
                    f"实际为 {len(read.sequence)} bp"
                )
        truth = read_truth(descriptor.truth_path) if descriptor.truth_path else None
        if truth is not None:
            checksums = truth.get("checksums", {})
            expected_reference = checksums.get("reference.fasta")
            expected_reads = checksums.get("reads.fastq")
            if expected_reference and expected_reference != self._file_sha256(
                descriptor.reference_path
            ):
                raise ValueError("reference.fasta 的 SHA-256 与真值文件不一致")
            if expected_reads and expected_reads != self._file_sha256(descriptor.reads_path):
                raise ValueError("reads.fastq 的 SHA-256 与真值文件不一致")
            truth_ids = [item.get("id") for item in truth["reads"]]
            if truth_ids != [read.id for read in reads]:
                raise ValueError("ground_truth.json 的 Reads 顺序或编号与 FASTQ 不一致")
        loaded = LoadedDataset(descriptor, reference_id, GenomeBuffer(sequence), reads, truth)
        with self._lock:
            self._current = loaded
        return loaded

    def load_folder(self, directory: str | Path) -> LoadedDataset:
        return self.load(discover_dataset(directory))

    def load_files(
        self,
        reference_path: str | Path,
        reads_path: str | Path,
        truth_path: str | Path | None = None,
    ) -> LoadedDataset:
        return self.load(descriptor_from_files(reference_path, reads_path, truth_path))

    def state(self) -> dict[str, Any]:
        current = self.current
        return current.to_dict() if current else {"loaded": False}

    def reference_window(self, start: int, length: int) -> dict[str, Any]:
        current = self.current
        if current is None:
            raise ValueError("尚未加载数据集")
        safe_start = max(0, min(start, current.reference.length - 1))
        safe_length = max(1, min(length, current.reference.length - safe_start, 300))
        return {
            "reference_id": current.reference_id,
            "reference_length": current.reference.length,
            "start_0": safe_start,
            "start_1": safe_start + 1,
            "end_1": safe_start + safe_length,
            "sequence": current.reference.text(safe_start, safe_length),
        }
