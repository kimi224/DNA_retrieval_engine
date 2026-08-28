"""Typed data transferred between storage, algorithms, services, and the UI."""

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True, frozen=True)
class ReadRecord:
    id: str
    sequence: bytes
    quality: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sequence": self.sequence.decode("ascii"),
            "length": len(self.sequence),
        }


@dataclass(slots=True, frozen=True)
class DatasetDescriptor:
    source_mode: str
    reference_path: Path
    reads_path: Path
    dataset_directory: Path | None = None
    truth_path: Path | None = None


@dataclass(slots=True, frozen=True)
class Mismatch:
    read_offset_0: int
    reference_position_0: int
    reference_base: str
    read_base: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["read_offset_1"] = self.read_offset_0 + 1
        value["reference_position_1"] = self.reference_position_0 + 1
        return value


@dataclass(slots=True, frozen=True)
class Hit:
    start_0: int
    read_length: int
    hamming_distance: int
    mismatches: tuple[Mismatch, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_0": self.start_0,
            "start_1": self.start_0 + 1,
            "end_1": self.start_0 + self.read_length,
            "hamming_distance": self.hamming_distance,
            "mismatches": [item.to_dict() for item in self.mismatches],
        }


@dataclass(slots=True)
class ReadSearchResult:
    id: str
    sequence: str
    seed: str
    bucket_index: int
    candidate_count: int = 0
    out_of_bounds_count: int = 0
    compared_base_count: int = 0
    pruned_candidate_count: int = 0
    elapsed_ms: float = 0.0
    hits: list[Hit] = field(default_factory=list)
    # The best candidate that exceeded the selected threshold but is still
    # within the supported 0-3 mismatch display range.  It is deliberately
    # separate from ``best_hit`` so ``matched`` remains an acceptance result.
    nearest_hit: Hit | None = None
    truth_start_0: int | None = None

    def best_hit(self) -> Hit | None:
        if not self.hits:
            return None
        return min(self.hits, key=lambda item: (item.hamming_distance, item.start_0))

    def to_dict(self) -> dict[str, Any]:
        best = self.best_hit()
        truth_recovered = None
        if self.truth_start_0 is not None:
            truth_recovered = any(hit.start_0 == self.truth_start_0 for hit in self.hits)
        return {
            "id": self.id,
            "sequence": self.sequence,
            "length": len(self.sequence),
            "seed": self.seed,
            "bucket_index": self.bucket_index,
            "candidate_count": self.candidate_count,
            "out_of_bounds_count": self.out_of_bounds_count,
            "compared_base_count": self.compared_base_count,
            "pruned_candidate_count": self.pruned_candidate_count,
            "elapsed_ms": round(self.elapsed_ms, 4),
            "matched": bool(self.hits),
            "best_hit": best.to_dict() if best else None,
            "nearest_hit": self.nearest_hit.to_dict() if self.nearest_hit else None,
            "hits": [hit.to_dict() for hit in self.hits],
            "truth_start_0": self.truth_start_0,
            "truth_recovered": truth_recovered,
        }


@dataclass(slots=True)
class BatchResult:
    run_id: str
    parameters: dict[str, Any]
    reference_id: str
    reference_length: int
    reads: list[ReadSearchResult]
    elapsed_ms: float

    def to_dict(self) -> dict[str, Any]:
        read_count = len(self.reads)
        matched = sum(1 for item in self.reads if item.hits)
        candidates = sum(item.candidate_count for item in self.reads)
        pruned = sum(item.pruned_candidate_count for item in self.reads)
        compared = sum(item.compared_base_count for item in self.reads)
        distribution = [0, 0, 0, 0]
        for item in self.reads:
            best = item.best_hit()
            if best is not None and best.hamming_distance <= 3:
                distribution[best.hamming_distance] += 1
        return {
            "run_id": self.run_id,
            "parameters": self.parameters,
            "reference_id": self.reference_id,
            "reference_length": self.reference_length,
            "summary": {
                "read_count": read_count,
                "matched_read_count": matched,
                "unmatched_read_count": read_count - matched,
                "match_rate": round(matched / read_count * 100, 2) if read_count else 0.0,
                "candidate_count": candidates,
                "pruned_candidate_count": pruned,
                "prune_rate": round(pruned / candidates * 100, 2) if candidates else 0.0,
                "compared_base_count": compared,
                "elapsed_ms": round(self.elapsed_ms, 4),
                "mismatch_distribution": distribution,
                "mismatch_distribution_rates": [
                    round(value / read_count * 100, 2) if read_count else 0.0
                    for value in distribution
                ],
            },
            "reads": [item.to_dict() for item in self.reads],
        }
