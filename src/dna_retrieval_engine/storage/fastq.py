"""Strict four-line FASTQ reader/writer for the teaching dataset."""

from pathlib import Path

from dna_retrieval_engine.models import ReadRecord


def read_fastq(path: Path) -> list[ReadRecord]:
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise ValueError(f"无法读取 FASTQ 文件：{exc}") from exc
    if not lines or len(lines) % 4:
        raise ValueError("FASTQ 必须由完整的四行记录组成")
    reads: list[ReadRecord] = []
    ids: set[str] = set()
    for offset in range(0, len(lines), 4):
        header, sequence, plus, quality = lines[offset : offset + 4]
        record_number = offset // 4 + 1
        if not header.startswith("@") or not header[1:].strip():
            raise ValueError(f"FASTQ 第 {record_number} 条记录的 @ 标题无效")
        if not plus.startswith("+"):
            raise ValueError(f"FASTQ 第 {record_number} 条记录缺少 + 分隔行")
        identifier = header[1:].strip().split()[0]
        if identifier in ids:
            raise ValueError(f"FASTQ Read 编号重复：{identifier}")
        ids.add(identifier)
        sequence = sequence.strip().upper()
        for index, base in enumerate(sequence):
            if base not in "ACGT":
                raise ValueError(f"{identifier} 第 {index + 1} 个碱基 {base!r} 非法")
        if len(sequence) != len(quality):
            raise ValueError(f"{identifier} 的质量字符串长度与序列长度不一致")
        reads.append(ReadRecord(identifier, sequence.encode("ascii"), quality))
    return reads


def write_fastq(path: Path, reads: list[ReadRecord]) -> None:
    lines: list[str] = []
    for read in reads:
        sequence = read.sequence.decode("ascii")
        if any(base not in "ACGT" for base in sequence) or len(sequence) != len(read.quality):
            raise ValueError(f"{read.id} 不能写入 FASTQ")
        lines.extend((f"@{read.id}", sequence, "+", read.quality))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
