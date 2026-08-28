"""Seed lookup followed by Hamming comparison with optional early pruning."""

from time import perf_counter

from dna_retrieval_engine.config import MISMATCH_MAX
from dna_retrieval_engine.models import Hit, Mismatch, ReadRecord, ReadSearchResult

from .kmer_index import KmerIndex


class TolerantMatcher:
    __slots__ = ("index",)

    def __init__(self, index: KmerIndex) -> None:
        self.index = index

    def search_read(
        self,
        read: ReadRecord,
        max_mismatches: int,
        *,
        early_prune: bool = True,
        truth_start_0: int | None = None,
    ) -> ReadSearchResult:
        if len(read.sequence) < self.index.k:
            raise ValueError(f"{read.id} 长度小于 K-mer 长度")
        if not 0 <= max_mismatches <= MISMATCH_MAX:
            raise ValueError(f"最大错配数必须为 0-{MISMATCH_MAX}")
        started = perf_counter()
        seed = read.sequence[: self.index.k]
        bucket = self.index.table.bucket_index(seed)
        result = ReadSearchResult(
            id=read.id,
            sequence=read.sequence.decode("ascii"),
            seed=seed.decode("ascii"),
            bucket_index=bucket,
            truth_start_0=truth_start_0,
        )
        entry = self.index.table.find_entry(seed)
        if entry is None:
            result.elapsed_ms = (perf_counter() - started) * 1000
            return result

        candidate_node = entry.positions_head
        while candidate_node is not None:
            start = candidate_node.position
            result.candidate_count += 1
            if start + len(read.sequence) > self.index.reference.length:
                result.out_of_bounds_count += 1
                candidate_node = candidate_node.next
                continue

            mismatch_items: list[Mismatch] = []
            exceeded_threshold = False
            pruned = False
            for offset, read_base in enumerate(read.sequence):
                result.compared_base_count += 1
                reference_base = self.index.reference.base_at(start + offset)
                if reference_base != read_base:
                    mismatch_items.append(
                        Mismatch(
                            read_offset_0=offset,
                            reference_position_0=start + offset,
                            reference_base=chr(reference_base),
                            read_base=chr(read_base),
                        )
                    )
                    if early_prune and len(mismatch_items) > max_mismatches:
                        # Continue only until the supported display ceiling so
                        # a rejected 1-3 mismatch Read still has a full trace.
                        if not exceeded_threshold:
                            result.pruned_candidate_count += 1
                            exceeded_threshold = True
                        if len(mismatch_items) > MISMATCH_MAX:
                            pruned = True
                            break
            candidate_hit = Hit(
                start_0=start,
                read_length=len(read.sequence),
                hamming_distance=len(mismatch_items),
                mismatches=tuple(mismatch_items),
            )
            if not pruned and len(mismatch_items) <= max_mismatches:
                result.hits.append(
                    candidate_hit
                )
            elif len(mismatch_items) <= MISMATCH_MAX:
                nearest = result.nearest_hit
                if nearest is None or (candidate_hit.hamming_distance, candidate_hit.start_0) < (
                    nearest.hamming_distance,
                    nearest.start_0,
                ):
                    result.nearest_hit = candidate_hit
            candidate_node = candidate_node.next
        result.hits.sort(key=lambda item: (item.hamming_distance, item.start_0))
        result.elapsed_ms = (perf_counter() - started) * 1000
        return result
