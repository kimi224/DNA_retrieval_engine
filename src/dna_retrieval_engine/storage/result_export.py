"""Atomic JSON and CSV exports for one completed search run."""

import csv
import json
import os
from pathlib import Path
from typing import Any


def export_result_files(directory: Path, payload: dict[str, Any]) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "run_report.json"
    json_tmp = json_path.with_suffix(".json.tmp")
    json_tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(json_tmp, json_path)

    csv_path = directory / "reads_results.csv"
    csv_tmp = csv_path.with_suffix(".csv.tmp")
    with csv_tmp.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "read_id",
                "sequence",
                "seed",
                "candidate_count",
                "matched",
                "best_start_1",
                "best_end_1",
                "hamming_distance",
                "hit_count",
                "compared_bases",
                "pruned_candidates",
            ]
        )
        for read in payload["reads"]:
            # Include the closest rejected alignment when available so an
            # exported CSV remains useful for failed 1-3 mismatch Reads.
            best = read["best_hit"] or read.get("nearest_hit")
            writer.writerow(
                [
                    read["id"],
                    read["sequence"],
                    read["seed"],
                    read["candidate_count"],
                    read["matched"],
                    best["start_1"] if best else "",
                    best["end_1"] if best else "",
                    best["hamming_distance"] if best else "",
                    len(read["hits"]),
                    read["compared_base_count"],
                    read["pruned_candidate_count"],
                ]
            )
    os.replace(csv_tmp, csv_path)
    return [json_path, csv_path]
