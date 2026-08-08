"""Reading the golden dataset.

Three call sites each re-implemented "one JSON object per non-blank line, keep
the ones whose expected_behavior is answer" — the audit and the two eval
scripts, which must agree on the answerable set or their numbers are not
comparable.
"""

import json
from pathlib import Path

GOLDEN_PATH = Path("data/golden_dataset.jsonl")
_ANSWERABLE = "answer"


def load_entries(path: Path = GOLDEN_PATH) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_answerable_entries(path: Path = GOLDEN_PATH) -> list[dict]:
    return [entry for entry in load_entries(path) if entry.get("expected_behavior") == _ANSWERABLE]
