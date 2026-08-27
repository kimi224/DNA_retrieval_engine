"""Handwritten separate-chaining hash table for fixed-length DNA K-mers."""

from collections.abc import Iterator
from typing import Any

from .linked_list import PositionNode, iter_positions


def _base_code(base: int) -> int:
    if base == 65:  # A
        return 0
    if base == 67:  # C
        return 1
    if base == 71:  # G
        return 2
    if base == 84:  # T
        return 3
    raise ValueError("K-mer 含非法碱基")


class KmerEntry:
    __slots__ = (
        "key",
        "positions_head",
        "positions_tail",
        "position_count",
        "next",
    )

    def __init__(self, key: bytes, position: int) -> None:
        node = PositionNode(position)
        self.key = key
        self.positions_head = node
        self.positions_tail = node
        self.position_count = 1
        self.next: KmerEntry | None = None

    def append_position(self, position: int) -> None:
        if position <= self.positions_tail.position:
            raise ValueError("K-mer 位置必须按严格升序插入")
        node = PositionNode(position)
        self.positions_tail.next = node
        self.positions_tail = node
        self.position_count += 1

    def positions(self) -> Iterator[int]:
        return iter_positions(self.positions_head)


class ChainedHashTable:
    """Array of collision chains; no dict/set backs the K-mer index."""

    __slots__ = (
        "_buckets",
        "bucket_count",
        "unique_key_count",
        "position_node_count",
        "used_bucket_count",
        "collision_count",
        "max_bucket_chain_length",
    )

    def __init__(self, bucket_count: int) -> None:
        if bucket_count < 1:
            raise ValueError("哈希桶数量必须为正整数")
        self._buckets: list[KmerEntry | None] = [None] * bucket_count
        self.bucket_count = bucket_count
        self.unique_key_count = 0
        self.position_node_count = 0
        self.used_bucket_count = 0
        self.collision_count = 0
        self.max_bucket_chain_length = 0

    def bucket_index(self, key: bytes) -> int:
        code = 0
        for base in key:
            code = code * 4 + _base_code(base)
        return code % self.bucket_count

    def insert(self, key: bytes, position: int) -> None:
        index = self.bucket_index(key)
        current = self._buckets[index]
        if current is None:
            self._buckets[index] = KmerEntry(key, position)
            self.used_bucket_count += 1
            self.unique_key_count += 1
            self.position_node_count += 1
            self.max_bucket_chain_length = max(self.max_bucket_chain_length, 1)
            return

        chain_length = 0
        previous: KmerEntry | None = None
        while current is not None:
            chain_length += 1
            if current.key == key:
                current.append_position(position)
                self.position_node_count += 1
                return
            previous = current
            current = current.next

        assert previous is not None
        previous.next = KmerEntry(key, position)
        self.unique_key_count += 1
        self.position_node_count += 1
        self.collision_count += 1
        self.max_bucket_chain_length = max(self.max_bucket_chain_length, chain_length + 1)

    def find_entry(self, key: bytes) -> KmerEntry | None:
        current = self._buckets[self.bucket_index(key)]
        while current is not None:
            if current.key == key:
                return current
            current = current.next
        return None

    def iter_bucket(self, index: int) -> Iterator[KmerEntry]:
        current = self._buckets[index]
        while current is not None:
            yield current
            current = current.next

    def longest_buckets(self, limit: int = 6) -> list[dict[str, Any]]:
        rows: list[tuple[int, int, int, str, list[int]]] = []
        for index in range(self.bucket_count):
            chain_length = 0
            positions = 0
            first_key = ""
            first_positions: list[int] = []
            current = self._buckets[index]
            while current is not None:
                chain_length += 1
                positions += current.position_count
                if not first_key:
                    first_key = current.key.decode("ascii")
                    for position in current.positions():
                        if len(first_positions) >= 8:
                            break
                        first_positions.append(position)
                current = current.next
            if chain_length:
                rows.append((chain_length, positions, index, first_key, first_positions))
        rows.sort(reverse=True)
        return [
            {
                "bucket_index": row[2],
                "chain_length": row[0],
                "position_count": row[1],
                "sample_key": row[3],
                "sample_positions_0": row[4],
            }
            for row in rows[:limit]
        ]

    def stats(self) -> dict[str, Any]:
        return {
            "bucket_count": self.bucket_count,
            "used_bucket_count": self.used_bucket_count,
            "unique_key_count": self.unique_key_count,
            "position_node_count": self.position_node_count,
            "collision_count": self.collision_count,
            "max_bucket_chain_length": self.max_bucket_chain_length,
            "load_factor": round(self.unique_key_count / self.bucket_count, 4),
            "longest_buckets": self.longest_buckets(),
        }

    def validate(self, max_position: int) -> None:
        entries = positions = used = collisions = 0
        longest = 0
        for bucket_index in range(self.bucket_count):
            current = self._buckets[bucket_index]
            if current is not None:
                used += 1
            chain_length = 0
            while current is not None:
                chain_length += 1
                entries += 1
                if self.bucket_index(current.key) != bucket_index:
                    raise AssertionError("K-mer 位于错误的哈希桶")
                other = current.next
                while other is not None:
                    if other.key == current.key:
                        raise AssertionError("同一桶链中存在重复 K-mer 条目")
                    other = other.next
                count = 0
                previous_position = -1
                tail: PositionNode | None = None
                node = current.positions_head
                while node is not None:
                    if node.position <= previous_position or node.position > max_position:
                        raise AssertionError("位置链下标无效或未保持升序")
                    previous_position = node.position
                    tail = node
                    count += 1
                    node = node.next
                if count != current.position_count or tail is not current.positions_tail:
                    raise AssertionError("位置链统计或尾指针不一致")
                if current.positions_tail.next is not None:
                    raise AssertionError("位置链尾节点必须指向 None")
                positions += count
                current = current.next
            if chain_length > 1:
                collisions += chain_length - 1
            longest = max(longest, chain_length)
        expected = (
            self.unique_key_count,
            self.position_node_count,
            self.used_bucket_count,
            self.collision_count,
            self.max_bucket_chain_length,
        )
        actual = (entries, positions, used, collisions, longest)
        if actual != expected:
            raise AssertionError(f"哈希表统计不一致: expected={expected}, actual={actual}")
