"""Aggregation and output helpers for the eval reports.

`mean` skips None rather than treating an unmeasurable question as zero, and
`fmt` prints that gap as a dash — both eval scripts had their own copy, so a
change to how a missing metric reads had to be made twice.
"""

import json
import statistics
from pathlib import Path

_MISSING = "  -  "


def mean(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return statistics.mean(present) if present else None


def fmt(value: float | None) -> str:
    return f"{value:.3f}" if value is not None else _MISSING


def write_json_report(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path
