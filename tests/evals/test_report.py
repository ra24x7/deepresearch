import json

from evals.report import fmt, mean, write_json_report


class TestMean:
    def test_averages_the_present_values(self):
        assert mean([1.0, 2.0, 3.0]) == 2.0

    def test_unmeasurable_questions_are_skipped_not_counted_as_zero(self):
        assert mean([1.0, None, 1.0]) == 1.0

    def test_all_missing_is_missing_rather_than_zero(self):
        assert mean([None, None]) is None

    def test_empty_is_missing(self):
        assert mean([]) is None


class TestFmt:
    def test_metrics_print_to_three_decimals(self):
        assert fmt(0.9663) == "0.966"

    def test_a_missing_metric_prints_as_a_dash(self):
        assert fmt(None).strip() == "-"

    def test_missing_and_present_render_to_the_same_width(self):
        assert len(fmt(None)) == len(fmt(0.966))


class TestWriteJsonReport:
    def test_creates_missing_parent_directories(self, tmp_path):
        path = write_json_report(tmp_path / "notebooks" / "phaseN" / "report.json", {"k": 10})

        assert path.exists()
        assert json.loads(path.read_text()) == {"k": 10}

    def test_ends_with_a_newline(self, tmp_path):
        path = write_json_report(tmp_path / "report.json", {"k": 10})

        assert path.read_text().endswith("}\n")
