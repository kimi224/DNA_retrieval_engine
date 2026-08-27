"""Minimal strict single-record FASTA reader/writer."""

from pathlib import Path


def read_fasta(path: Path) -> tuple[str, str]:
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise ValueError(f"无法读取 FASTA 文件：{exc}") from exc
    records: list[tuple[str, list[str]]] = []
    current_id = ""
    sequence_lines: list[str] = []
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if current_id:
                records.append((current_id, sequence_lines))
            header = line[1:].strip()
            if not header:
                raise ValueError(f"FASTA 第 {line_number} 行缺少序列名称")
            current_id = header.split()[0]
            sequence_lines = []
        elif not current_id:
            raise ValueError("FASTA 序列内容必须位于 > 标题行之后")
        else:
            sequence_lines.append(line.upper())
    if current_id:
        records.append((current_id, sequence_lines))
    if len(records) != 1:
        raise ValueError(f"本项目要求 FASTA 恰好包含 1 条参考序列，实际为 {len(records)} 条")
    identifier, parts = records[0]
    sequence = "".join(parts)
    if not sequence:
        raise ValueError("FASTA 参考序列为空")
    for index, base in enumerate(sequence):
        if base not in "ACGT":
            raise ValueError(f"FASTA 第 {index + 1} 个碱基 {base!r} 非法，只允许 A/C/G/T")
    return identifier, sequence


def write_fasta(path: Path, identifier: str, sequence: str, *, width: int = 80) -> None:
    if not identifier or any(base not in "ACGT" for base in sequence):
        raise ValueError("FASTA 标识或序列无效")
    lines = [f">{identifier}"]
    lines.extend(sequence[index : index + width] for index in range(0, len(sequence), width))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
