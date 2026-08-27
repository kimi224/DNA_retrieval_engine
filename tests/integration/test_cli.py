from pathlib import Path

from dna_retrieval_engine.cli import build_parser, main, run


def test_cli_commands_share_the_production_services(tmp_path: Path) -> None:
    parser = build_parser()
    generated = run(
        parser.parse_args(
            [
                "generate",
                "--output",
                str(tmp_path),
                "--seed",
                "19",
                "--reference-length",
                "2000",
            ]
        )
    )
    dataset = Path(generated["dataset"]["dataset_directory"])
    assert generated["ok"] and dataset.is_dir()

    validated = run(parser.parse_args(["validate", "--dataset", str(dataset)]))
    assert validated["dataset"]["read_count"] == 50

    indexed = run(parser.parse_args(["index", "--dataset", str(dataset), "--k", "8"]))
    assert indexed["index"]["position_node_count"] == 2000 - 8 + 1

    searched = run(
        parser.parse_args(
            [
                "search",
                "--dataset",
                str(dataset),
                "--k",
                "8",
                "--mismatches",
                "4",
                "--export",
                str(dataset),
            ]
        )
    )
    assert searched["result"]["summary"]["matched_read_count"] == 50
    assert len(searched["exported"]) == 2


def test_cli_main_returns_json_error_for_bad_input(tmp_path: Path, capsys) -> None:
    exit_code = main(["validate", "--dataset", str(tmp_path / "missing")])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert '"ok": false' in captured.out
    assert "数据集文件夹" in captured.out
