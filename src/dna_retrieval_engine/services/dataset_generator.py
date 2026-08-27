"""Reproducible synthetic dataset generation with protected exact seeds."""

import os
import random
import secrets
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from dna_retrieval_engine.config import (
    PROTECTED_PREFIX_LENGTH,
    READ_COUNT,
    READ_LENGTH_MAX,
    READ_LENGTH_MIN,
    REFERENCE_LENGTH_MAX,
    REFERENCE_LENGTH_MIN,
)
from dna_retrieval_engine.core.genome_buffer import GenomeBuffer
from dna_retrieval_engine.core.kmer_index import KmerIndex
from dna_retrieval_engine.core.matcher import TolerantMatcher
from dna_retrieval_engine.models import DatasetDescriptor, ReadRecord
from dna_retrieval_engine.storage.fasta import write_fasta
from dna_retrieval_engine.storage.fastq import write_fastq
from dna_retrieval_engine.storage.truth import write_truth

from .dataset_service import DatasetService, LoadedDataset


def _sha256(path: Path) -> str:
    digest = sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


class DatasetGenerator:
    def __init__(self, dataset_service: DatasetService) -> None:
        self.dataset_service = dataset_service

    @staticmethod
    def _unique_directory(parent: Path, stem: str) -> Path:
        for suffix in range(100):
            name = stem if suffix == 0 else f"{stem}_{suffix:02d}"
            candidate = parent / name
            try:
                candidate.mkdir()
            except FileExistsError:
                continue
            return candidate
        raise ValueError("同名数据集目录过多，请稍后重试")

    @staticmethod
    def _mismatch_offsets(rng: random.Random, length: int, count: int) -> list[int]:
        if count == 0:
            return []
        candidates = list(range(PROTECTED_PREFIX_LENGTH, length))
        for _ in range(100):
            offsets = sorted(rng.sample(candidates, count))
            if all(right - left >= 5 for left, right in zip(offsets, offsets[1:], strict=False)):
                return offsets
        return sorted(rng.sample(candidates, count))

    def generate(
        self,
        output_parent: str | Path,
        *,
        seed: int | None = None,
        reference_length: int | None = None,
    ) -> LoadedDataset:
        parent = Path(output_parent).expanduser().resolve()
        if not parent.is_dir():
            raise ValueError("保存父目录不存在或不是文件夹")
        seed = secrets.randbits(32) if seed is None else int(seed)
        if seed < 0 or seed > 0xFFFFFFFF:
            raise ValueError("随机种子必须是 0 到 4294967295 之间的整数")
        rng = random.Random(seed)
        length = reference_length or rng.randint(REFERENCE_LENGTH_MIN, REFERENCE_LENGTH_MAX)
        if not REFERENCE_LENGTH_MIN <= length <= REFERENCE_LENGTH_MAX:
            raise ValueError("参考序列长度超出课程要求范围")

        now = datetime.now().astimezone()
        stem = f"dna_demo_{now:%Y%m%d_%H%M%S}_seed_{seed}"
        directory = self._unique_directory(parent, stem)
        temp_paths = [
            directory / "reference.fasta.tmp",
            directory / "reads.fastq.tmp",
            directory / "ground_truth.json.tmp",
        ]
        final_paths = [
            directory / "reference.fasta",
            directory / "reads.fastq",
            directory / "ground_truth.json",
        ]
        try:
            reference = "".join(rng.choice("ACGT") for _ in range(length))
            read_lengths = [
                rng.randint(READ_LENGTH_MIN, READ_LENGTH_MAX) for _ in range(READ_COUNT)
            ]
            mismatch_counts = [value for value in range(5) for _ in range(READ_COUNT // 5)]
            rng.shuffle(mismatch_counts)
            generated: list[tuple[ReadRecord, dict[str, Any]]] = []
            for index in range(READ_COUNT):
                read_length = read_lengths[index]
                available = length - read_length + 1
                low = index * available // READ_COUNT
                high = max(low, ((index + 1) * available // READ_COUNT) - 1)
                start = rng.randint(low, high)
                sequence = list(reference[start : start + read_length])
                mutations: list[dict[str, Any]] = []
                offsets = self._mismatch_offsets(rng, read_length, mismatch_counts[index])
                for read_offset in offsets:
                    original = sequence[read_offset]
                    replacement = rng.choice([base for base in "ACGT" if base != original])
                    sequence[read_offset] = replacement
                    mutations.append(
                        {
                            "read_offset_0": read_offset,
                            "reference_position_0": start + read_offset,
                            "from": original,
                            "to": replacement,
                        }
                    )
                identifier = f"READ-{index + 1:03d}"
                read = ReadRecord(identifier, "".join(sequence).encode("ascii"), "I" * read_length)
                generated.append(
                    (
                        read,
                        {
                            "id": identifier,
                            "length": read_length,
                            "reference_start_0": start,
                            "reference_start_1": start + 1,
                            "mismatch_offsets_0": offsets,
                            "mutations": mutations,
                        },
                    )
                )

            reads = [item[0] for item in generated]
            write_fasta(
                temp_paths[0],
                f"chr-demo-01 synthetic_reference length={length} seed={seed}",
                reference,
            )
            write_fastq(temp_paths[1], reads)
            truth: dict[str, Any] = {
                "schema_version": 1,
                "dataset_id": stem,
                "created_at": now.isoformat(timespec="seconds"),
                "random_seed": seed,
                "coordinate_system": {
                    "internal": "0-based half-open",
                    "display": "1-based inclusive",
                },
                "generator": {
                    "reference_length": length,
                    "read_count": READ_COUNT,
                    "read_length_range": [READ_LENGTH_MIN, READ_LENGTH_MAX],
                    "mismatch_range": [0, 4],
                    "protected_prefix_length": PROTECTED_PREFIX_LENGTH,
                },
                "checksums": {
                    "reference.fasta": _sha256(temp_paths[0]),
                    "reads.fastq": _sha256(temp_paths[1]),
                },
                "reads": [item[1] for item in generated],
            }
            write_truth(temp_paths[2], truth)
            for temporary, final in zip(temp_paths, final_paths, strict=True):
                os.replace(temporary, final)

            descriptor = DatasetDescriptor(
                source_mode="generated",
                dataset_directory=directory,
                reference_path=final_paths[0],
                reads_path=final_paths[1],
                truth_path=final_paths[2],
            )
            loaded = self.dataset_service.load(descriptor)
            index = KmerIndex.build(GenomeBuffer(reference), PROTECTED_PREFIX_LENGTH)
            matcher = TolerantMatcher(index)
            for read, truth_item in generated:
                result = matcher.search_read(read, 4, truth_start_0=truth_item["reference_start_0"])
                if not any(hit.start_0 == truth_item["reference_start_0"] for hit in result.hits):
                    raise AssertionError(f"生成数据自检失败：{read.id} 未找回真实来源位置")
            return loaded
        except Exception:
            for path in temp_paths + final_paths:
                if path.is_file():
                    path.unlink()
            try:
                directory.rmdir()
            except OSError:
                pass
            raise
