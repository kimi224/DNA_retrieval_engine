import json
from pathlib import Path

import pytest

from dna_retrieval_engine.models import ReadRecord
from dna_retrieval_engine.storage.dataset_discovery import (
    descriptor_from_files,
    discover_dataset,
)
from dna_retrieval_engine.storage.fasta import read_fasta, write_fasta
from dna_retrieval_engine.storage.fastq import read_fastq, write_fastq
from dna_retrieval_engine.storage.truth import read_truth, write_truth


def test_fasta_round_trip_and_validation(tmp_path: Path) -> None:
    path = tmp_path / "reference.fasta"
    write_fasta(path, "chr-demo", "ACGT" * 30, width=17)
    assert read_fasta(path) == ("chr-demo", "ACGT" * 30)
    path.write_text(">a\nACGT\n>b\nACGT\n", encoding="utf-8")
    with pytest.raises(ValueError, match="恰好包含 1 条"):
        read_fasta(path)


def test_fastq_round_trip_and_quality_validation(tmp_path: Path) -> None:
    path = tmp_path / "reads.fastq"
    reads = [ReadRecord("READ-001", b"ACGT", "IIII"), ReadRecord("READ-002", b"TGCA", "JJJJ")]
    write_fastq(path, reads)
    assert read_fastq(path) == reads
    path.write_text("@READ-001\nACGT\n+\nIII\n", encoding="utf-8")
    with pytest.raises(ValueError, match="质量字符串长度"):
        read_fastq(path)


def test_truth_round_trip_requires_schema(tmp_path: Path) -> None:
    path = tmp_path / "ground_truth.json"
    payload = {"schema_version": 1, "reads": []}
    write_truth(path, payload)
    assert read_truth(path) == payload
    path.write_text(json.dumps({"schema_version": 2, "reads": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="schema_version"):
        read_truth(path)


def test_dataset_discovery_prefers_canonical_names(tmp_path: Path) -> None:
    canonical_reference = tmp_path / "reference.fasta"
    canonical_reads = tmp_path / "reads.fastq"
    canonical_reference.write_text("x", encoding="utf-8")
    canonical_reads.write_text("x", encoding="utf-8")
    (tmp_path / "another.fa").write_text("x", encoding="utf-8")
    descriptor = discover_dataset(tmp_path)
    assert descriptor.reference_path == canonical_reference
    assert descriptor.reads_path == canonical_reads


def test_dataset_discovery_reports_ambiguity(tmp_path: Path) -> None:
    (tmp_path / "a.fa").write_text("x", encoding="utf-8")
    (tmp_path / "b.fasta").write_text("x", encoding="utf-8")
    (tmp_path / "reads.fq").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="多个参考序列候选"):
        discover_dataset(tmp_path)


def test_separate_files_validate_extensions(tmp_path: Path) -> None:
    reference = tmp_path / "reference.fa"
    reads = tmp_path / "reads.fq"
    reference.touch()
    reads.touch()
    descriptor = descriptor_from_files(reference, reads)
    assert descriptor.source_mode == "separate_files"
    with pytest.raises(ValueError, match="参考序列"):
        descriptor_from_files(tmp_path / "missing.fa", reads)
