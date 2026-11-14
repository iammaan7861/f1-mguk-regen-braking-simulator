"""Shared paths and helpers for the report / presentation builders."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "outputs" / "figures"
OUT = ROOT / "outputs"
RESULTS = OUT / "results.json"
TESTS = OUT / "test_results.json"
GROUP = ROOT / "group_details.json"
EQ = OUT / "equations"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def f(path_name: str) -> Path:
    p = FIG / path_name
    if not p.is_file():
        raise FileNotFoundError(p)
    return p


def fmt(x, digits=2):
    if isinstance(x, (int, float)):
        return f"{x:.{digits}f}"
    return str(x)


def pct(x, digits=1):
    return f"{x:.{digits}f} %"
