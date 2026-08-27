"""Ground-truth JSON validation and serialization."""

import json
from pathlib import Path
from typing import Any


def read_truth(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取真值 JSON：{exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("ground_truth.json 的 schema_version 必须为 1")
    if not isinstance(data.get("reads"), list):
        raise ValueError("ground_truth.json 缺少 reads 数组")
    return data


def write_truth(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
