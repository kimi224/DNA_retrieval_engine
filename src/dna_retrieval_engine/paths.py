"""Resolve package resources identically from source and a frozen executable."""

import sys
from pathlib import Path


def package_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "dna_retrieval_engine"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def resource_path(*parts: str) -> Path:
    return package_root().joinpath(*parts)
