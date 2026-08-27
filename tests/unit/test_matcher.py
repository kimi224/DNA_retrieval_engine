from dna_retrieval_engine.core.genome_buffer import GenomeBuffer
from dna_retrieval_engine.core.kmer_index import KmerIndex
from dna_retrieval_engine.core.matcher import TolerantMatcher
from dna_retrieval_engine.models import ReadRecord


def read(sequence: str, identifier: str = "READ-001") -> ReadRecord:
    return ReadRecord(identifier, sequence.encode("ascii"), "I" * len(sequence))


def test_exact_and_tolerant_hits_include_visual_trace() -> None:
    matcher = TolerantMatcher(KmerIndex.build(GenomeBuffer("ACGTACGTACGT"), 4))
    exact = matcher.search_read(read("ACGTAC"), 1)
    assert [hit.start_0 for hit in exact.hits] == [0, 4]
    assert exact.best_hit().hamming_distance == 0

    tolerant = matcher.search_read(read("ACGTTC"), 1)
    assert [hit.start_0 for hit in tolerant.hits] == [0, 4]
    mismatch = tolerant.hits[0].mismatches[0]
    assert (mismatch.read_offset_0, mismatch.reference_position_0) == (4, 4)
    assert (mismatch.reference_base, mismatch.read_base) == ("A", "T")


def test_early_pruning_records_compared_characters() -> None:
    matcher = TolerantMatcher(KmerIndex.build(GenomeBuffer("AAAACCCCAAAAGGGG"), 4))
    result = matcher.search_read(read("AAAATTTT"), 1, early_prune=True)
    assert result.hits == []
    assert result.candidate_count == 2
    assert result.pruned_candidate_count == 2
    assert result.compared_base_count < result.candidate_count * 8


def test_seed_mismatch_has_no_candidate_by_design() -> None:
    matcher = TolerantMatcher(KmerIndex.build(GenomeBuffer("ACGTACGT"), 4))
    result = matcher.search_read(read("TCGTACGT"), 4)
    assert result.candidate_count == 0
    assert result.hits == []


def test_boundary_candidates_are_counted_without_overread() -> None:
    matcher = TolerantMatcher(KmerIndex.build(GenomeBuffer("ACGTAAAAACGT"), 4))
    result = matcher.search_read(read("ACGTAAAA"), 0)
    assert result.candidate_count == 2
    assert result.out_of_bounds_count == 1
    assert [hit.start_0 for hit in result.hits] == [0]
