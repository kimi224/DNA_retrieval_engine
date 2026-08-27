"""A fixed, contiguous one-byte-per-base reference genome buffer."""


class GenomeBuffer:
    __slots__ = ("_data",)

    def __init__(self, sequence: str | bytes) -> None:
        raw = sequence.encode("ascii") if isinstance(sequence, str) else bytes(sequence)
        data = bytearray(len(raw))
        for index, base in enumerate(raw):
            if base not in (65, 67, 71, 84):  # A, C, G, T
                raise ValueError(f"参考序列第 {index + 1} 位含非法碱基")
            data[index] = base
        self._data = data

    def __len__(self) -> int:
        return len(self._data)

    @property
    def length(self) -> int:
        return len(self._data)

    def base_at(self, index: int) -> int:
        if index < 0 or index >= len(self._data):
            raise IndexError("参考序列下标越界")
        return self._data[index]

    def validate_range(self, start: int, length: int) -> None:
        if start < 0 or length < 0 or start + length > len(self._data):
            raise IndexError("参考序列窗口越界")

    def window(self, start: int, length: int) -> bytes:
        self.validate_range(start, length)
        return bytes(self._data[start : start + length])

    def text(self, start: int = 0, length: int | None = None) -> str:
        size = len(self._data) - start if length is None else length
        return self.window(start, size).decode("ascii")
