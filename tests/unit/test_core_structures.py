import pytest

from dna_retrieval_engine.core.genome_buffer import GenomeBuffer
from dna_retrieval_engine.core.hash_table import ChainedHashTable
from dna_retrieval_engine.core.kmer_index import KmerIndex, next_prime


def test_genome_buffer_is_contiguous_and_checked() -> None:
    genome = GenomeBuffer("ACGTAC")
    assert genome.length == 6
    assert genome.base_at(2) == ord("G")
    assert genome.window(1, 4) == b"CGTA"
    assert genome.text() == "ACGTAC"
    with pytest.raises(ValueError, match="非法碱基"):
        GenomeBuffer("ACNT")
    with pytest.raises(IndexError, match="越界"):
        genome.window(4, 3)


def test_hash_table_uses_two_independent_chains() -> None:
    table = ChainedHashTable(1)
    table.insert(b"AAAA", 0)
    table.insert(b"AAAA", 4)
    table.insert(b"CCCC", 1)
    table.insert(b"GGGG", 2)

    assert table.unique_key_count == 3
    assert table.position_node_count == 4
    assert table.used_bucket_count == 1
    assert table.collision_count == 2
    assert table.max_bucket_chain_length == 3
    assert list(table.find_entry(b"AAAA").positions()) == [0, 4]
    assert table.find_entry(b"TTTT") is None
    table.validate(max_position=4)


def test_hash_table_rejects_out_of_order_positions() -> None:
    table = ChainedHashTable(3)
    table.insert(b"AAAA", 5)
    with pytest.raises(ValueError, match="严格升序"):
        table.insert(b"AAAA", 4)


def test_kmer_index_covers_every_one_base_window() -> None:
    genome = GenomeBuffer("AAAAAAC")
    index = KmerIndex.build(genome, 3)
    assert index.window_count == 5
    assert index.table.position_node_count == 5
    assert list(index.table.find_entry(b"AAA").positions()) == [0, 1, 2, 3]
    assert list(index.table.find_entry(b"AAC").positions()) == [4]
    assert index.to_dict()["integrity_ok"] is True


def test_next_prime_is_deterministic() -> None:
    assert next_prime(53) == 53
    assert next_prime(54) == 59
