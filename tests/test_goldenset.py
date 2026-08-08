import json

import pytest

from goldenset import load_answerable_entries, load_entries

ENTRIES = [
    {"id": "g001", "expected_behavior": "answer"},
    {"id": "g002", "expected_behavior": "abstain"},
    {"id": "g003", "expected_behavior": "answer"},
    {"id": "g004"},
]


@pytest.fixture
def golden_file(tmp_path):
    path = tmp_path / "golden.jsonl"
    # blank lines are how the file gets hand-edited; they are not entries
    path.write_text("\n".join([json.dumps(ENTRIES[0]), "", json.dumps(ENTRIES[1]), json.dumps(ENTRIES[2]), ""]) + "\n")
    return path


class TestLoadEntries:
    def test_reads_one_entry_per_non_blank_line(self, golden_file):
        assert [entry["id"] for entry in load_entries(golden_file)] == ["g001", "g002", "g003"]


class TestLoadAnswerableEntries:
    def test_keeps_only_entries_expected_to_be_answered(self, golden_file):
        assert [entry["id"] for entry in load_answerable_entries(golden_file)] == ["g001", "g003"]

    def test_an_entry_without_expected_behavior_is_not_answerable(self, tmp_path):
        path = tmp_path / "golden.jsonl"
        path.write_text(json.dumps(ENTRIES[3]) + "\n")

        assert load_answerable_entries(path) == []


class TestShippedDataset:
    def test_the_real_dataset_loads_and_is_a_subset_of_itself(self):
        entries = load_entries()
        answerable = load_answerable_entries()

        assert entries, "data/golden_dataset.jsonl is empty"
        assert len(answerable) <= len(entries)
        assert {e["id"] for e in answerable} <= {e["id"] for e in entries}
