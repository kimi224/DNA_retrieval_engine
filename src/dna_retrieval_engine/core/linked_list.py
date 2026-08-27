"""Position linked-list node used by each K-mer entry."""

from collections.abc import Iterator


class PositionNode:
    __slots__ = ("position", "next")

    def __init__(self, position: int) -> None:
        self.position = position
        self.next: PositionNode | None = None


def iter_positions(head: PositionNode | None) -> Iterator[int]:
    current = head
    while current is not None:
        yield current.position
        current = current.next
