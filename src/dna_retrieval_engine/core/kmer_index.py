"""Build a full K-mer index with a one-base sliding window."""

from typing import Any

from .genome_buffer import GenomeBuffer
from .hash_table import ChainedHashTable


def _is_prime(value: int) -> bool:
    if value < 2:
        return False
    if value % 2 == 0:
        return value == 2
    factor = 3
    while factor * factor <= value:
        if value % factor == 0:
            return False
        factor += 2
    return True


def next_prime(value: int) -> int:
    candidate = max(2, value)
    while not _is_prime(candidate):
        candidate += 1
    return candidate


class KmerIndex:
    __slots__ = ("reference", "k", "window_count", "table")

    def __init__(self, reference: GenomeBuffer, k: int) -> None:
        if k < 1 or k > reference.length:
            raise ValueError("K-mer 长度必须在参考序列长度范围内")
        self.reference = reference
        self.k = k
        self.window_count = reference.length - k + 1
        target = max(53, min(self.window_count // 2, (4**k) // 2))
        self.table = ChainedHashTable(next_prime(target))

    @classmethod
    def build(cls, reference: GenomeBuffer, k: int, *, validate: bool = True) -> "KmerIndex":
        index = cls(reference, k)
        for start in range(index.window_count):
            index.table.insert(reference.window(start, k), start)
        if index.table.position_node_count != index.window_count:
            raise AssertionError("索引位置节点数不等于滑动窗口数")
        if validate:
            index.table.validate(index.window_count - 1)
        return index

    def to_dict(self) -> dict[str, Any]:
        data = self.table.stats()
        data.update(
            {
                "k": self.k,
                "reference_length": self.reference.length,
                "window_count": self.window_count,
                "integrity_ok": self.table.position_node_count == self.window_count,
            }
        )
        return data
