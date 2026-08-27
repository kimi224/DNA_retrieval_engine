from pathlib import Path

from dna_retrieval_engine.services.dataset_generator import DatasetGenerator
from dna_retrieval_engine.services.dataset_service import DatasetService
from dna_retrieval_engine.services.report_service import ReportService
from dna_retrieval_engine.services.search_service import SearchService


def test_generated_dataset_full_flow_and_threshold_monotonicity(tmp_path: Path) -> None:
    datasets = DatasetService()
    loaded = DatasetGenerator(datasets).generate(tmp_path, seed=104729, reference_length=2000)
    search = SearchService(datasets)

    counts = []
    for threshold in range(5):
        result = search.search(12, threshold, True)
        counts.append(result["summary"]["matched_read_count"])
    assert counts == [10, 20, 30, 40, 50]
    assert all(read["truth_recovered"] for read in result["reads"])
    assert search.index_state()["position_node_count"] == 2000 - 12 + 1

    exported = ReportService(datasets, search).export(loaded.descriptor.dataset_directory)
    assert {Path(path).name for path in exported} == {"run_report.json", "reads_results.csv"}
    assert all(Path(path).is_file() for path in exported)


def test_generated_truth_is_reproducible(tmp_path: Path) -> None:
    first_service = DatasetService()
    second_service = DatasetService()
    first = DatasetGenerator(first_service).generate(tmp_path, seed=7, reference_length=2000)
    second = DatasetGenerator(second_service).generate(tmp_path, seed=7, reference_length=2000)
    assert (
        first.descriptor.reference_path.read_bytes()
        == second.descriptor.reference_path.read_bytes()
    )
    assert first.descriptor.reads_path.read_bytes() == second.descriptor.reads_path.read_bytes()
    mismatch_counts = [len(item["mismatch_offsets_0"]) for item in first.truth["reads"]]
    assert sorted(mismatch_counts) == [value for value in range(5) for _ in range(10)]
    deciles = {min(9, item["reference_start_0"] * 10 // 2000) for item in first.truth["reads"]}
    assert deciles == set(range(10))
