"""Command-line diagnostics for the same services used by the desktop UI."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .config import DEFAULT_K, DEFAULT_MISMATCHES
from .services.dataset_generator import DatasetGenerator
from .services.dataset_service import DatasetService
from .services.report_service import ReportService
from .services.search_service import SearchService


def _print(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _services() -> tuple[DatasetService, SearchService, ReportService]:
    datasets = DatasetService()
    search = SearchService(datasets)
    return datasets, search, ReportService(datasets, search)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DNA Retrieval Engine 命令行调试工具")
    commands = parser.add_subparsers(dest="command", required=True)

    generate = commands.add_parser("generate", help="生成并校验一个课程演示数据集")
    generate.add_argument("--output", type=Path, required=True, help="保存父目录")
    generate.add_argument("--seed", type=int)
    generate.add_argument("--reference-length", type=int)

    for name, help_text in (
        ("validate", "解析并校验现有数据集"),
        ("index", "构建索引并输出真实结构统计"),
        ("search", "构建索引并运行 50 条 Reads 检索"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--dataset", type=Path, required=True)
        if name in {"index", "search"}:
            command.add_argument("--k", type=int, default=DEFAULT_K)
        if name == "search":
            command.add_argument("--mismatches", type=int, default=DEFAULT_MISMATCHES)
            command.add_argument("--no-prune", action="store_true")
            command.add_argument("--export", type=Path)

    demo = commands.add_parser("demo", help="生成、索引、检索并导出的一键调试流程")
    demo.add_argument("--output", type=Path, required=True)
    demo.add_argument("--seed", type=int, default=104729)
    demo.add_argument("--reference-length", type=int, default=3200)
    demo.add_argument("--k", type=int, default=DEFAULT_K)
    demo.add_argument("--mismatches", type=int, default=DEFAULT_MISMATCHES)
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    datasets, search, reports = _services()
    if args.command == "generate":
        loaded = DatasetGenerator(datasets).generate(
            args.output, seed=args.seed, reference_length=args.reference_length
        )
        return {"ok": True, "dataset": loaded.to_dict()}
    if args.command in {"validate", "index", "search"}:
        datasets.load_folder(args.dataset)
        if args.command == "validate":
            return {"ok": True, "dataset": datasets.state()}
        index = search.build_index(args.k)
        if args.command == "index":
            return {"ok": True, "dataset": datasets.state(), "index": index}
        result = search.search(args.k, args.mismatches, not args.no_prune)
        exported = reports.export(args.export) if args.export else []
        return {
            "ok": True,
            "dataset": datasets.state(),
            "index": search.index_state(),
            "result": result,
            "exported": exported,
        }
    loaded = DatasetGenerator(datasets).generate(
        args.output, seed=args.seed, reference_length=args.reference_length
    )
    search.build_index(args.k)
    result = search.search(args.k, args.mismatches, True)
    exported = reports.export(loaded.descriptor.dataset_directory)
    return {
        "ok": True,
        "dataset": datasets.state(),
        "index": search.index_state(),
        "result": result,
        "exported": exported,
    }


def main(argv: list[str] | None = None) -> int:
    # Keep JSON and Chinese diagnostics stable in Windows terminals and redirected files.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = build_parser()
    try:
        _print(run(parser.parse_args(argv)))
        return 0
    except Exception as exc:
        _print({"ok": False, "error": str(exc), "error_type": type(exc).__name__})
        return 1


if __name__ == "__main__":
    sys.exit(main())
