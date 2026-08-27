"""Deterministic, non-recursive discovery of a dataset directory."""

from pathlib import Path

from dna_retrieval_engine.models import DatasetDescriptor

REFERENCE_SUFFIXES = {".fa", ".fasta"}
READS_SUFFIXES = {".fq", ".fastq"}


def _discover_one(directory: Path, canonical: str, suffixes: set[str], label: str) -> Path:
    canonical_path = directory / canonical
    if canonical_path.is_file():
        return canonical_path
    candidates = sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in suffixes
        ),
        key=lambda path: path.name.lower(),
    )
    if not candidates:
        raise ValueError(f"数据集文件夹缺少{label}文件（{', '.join(sorted(suffixes))}）")
    if len(candidates) > 1:
        names = "、".join(path.name for path in candidates)
        raise ValueError(f"发现多个{label}候选：{names}。请改用“分别选择文件”")
    return candidates[0]


def discover_dataset(directory: str | Path) -> DatasetDescriptor:
    folder = Path(directory).expanduser().resolve()
    if not folder.is_dir():
        raise ValueError("所选数据集文件夹不存在或不是文件夹")
    reference = _discover_one(folder, "reference.fasta", REFERENCE_SUFFIXES, "参考序列")
    reads = _discover_one(folder, "reads.fastq", READS_SUFFIXES, "Reads")
    truth = folder / "ground_truth.json"
    return DatasetDescriptor(
        source_mode="folder",
        dataset_directory=folder,
        reference_path=reference,
        reads_path=reads,
        truth_path=truth if truth.is_file() else None,
    )


def descriptor_from_files(
    reference_path: str | Path,
    reads_path: str | Path,
    truth_path: str | Path | None = None,
) -> DatasetDescriptor:
    reference = Path(reference_path).expanduser().resolve()
    reads = Path(reads_path).expanduser().resolve()
    truth = Path(truth_path).expanduser().resolve() if truth_path else None
    if not reference.is_file() or reference.suffix.lower() not in REFERENCE_SUFFIXES:
        raise ValueError("请选择存在的 .fa/.fasta 参考序列文件")
    if not reads.is_file() or reads.suffix.lower() not in READS_SUFFIXES:
        raise ValueError("请选择存在的 .fq/.fastq Reads 文件")
    if truth is not None and (not truth.is_file() or truth.suffix.lower() != ".json"):
        raise ValueError("可选真值文件必须是存在的 JSON 文件")
    return DatasetDescriptor(
        source_mode="separate_files",
        dataset_directory=None,
        reference_path=reference,
        reads_path=reads,
        truth_path=truth,
    )
