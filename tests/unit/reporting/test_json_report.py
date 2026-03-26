"""Tests for JSON report generator."""

import json
import tempfile
from pathlib import Path

from scylla.reporting.json_report import JsonReportGenerator, _sanitize_for_json
from scylla.reporting.markdown import ReportData, TierMetrics


def _make_report_data(test_id: str = "test-001") -> ReportData:
    """Create minimal ReportData for testing."""
    return ReportData(
        test_id=test_id,
        test_name="Test 001",
        timestamp="2025-01-01T00:00:00Z",
        runs_per_tier=10,
        judge_model="claude-opus-4-6",
    )


class TestSanitizeForJson:
    """Tests for _sanitize_for_json helper."""

    def test_sanitize_inf(self) -> None:
        """Positive infinity is replaced with None."""
        assert _sanitize_for_json(float("inf")) is None

    def test_sanitize_negative_inf(self) -> None:
        """Negative infinity is replaced with None."""
        assert _sanitize_for_json(float("-inf")) is None

    def test_sanitize_nan(self) -> None:
        """NaN is replaced with None."""
        assert _sanitize_for_json(float("nan")) is None

    def test_sanitize_normal_float(self) -> None:
        """Normal floats are preserved."""
        assert _sanitize_for_json(1.5) == 1.5

    def test_sanitize_dict(self) -> None:
        """Dict values are recursively sanitized."""
        result = _sanitize_for_json({"a": float("inf"), "b": 1.0})
        assert result == {"a": None, "b": 1.0}

    def test_sanitize_list(self) -> None:
        """List values are recursively sanitized."""
        result = _sanitize_for_json([float("nan"), 2.0])
        assert result == [None, 2.0]

    def test_sanitize_nested(self) -> None:
        """Nested structures are recursively sanitized."""
        result = _sanitize_for_json({"items": [{"cost": float("inf")}]})
        assert result == {"items": [{"cost": None}]}

    def test_sanitize_non_float(self) -> None:
        """Non-float values are passed through."""
        assert _sanitize_for_json("hello") == "hello"
        assert _sanitize_for_json(42) == 42


class TestJsonReportGenerator:
    """Tests for JsonReportGenerator."""

    def test_get_report_dir(self) -> None:
        """Report dir is base_dir / test_id."""
        gen = JsonReportGenerator(Path("/reports"))
        assert gen.get_report_dir("test-001") == Path("/reports/test-001")

    def test_generate_report_returns_valid_json(self) -> None:
        """generate_report returns parseable JSON."""
        gen = JsonReportGenerator(Path("/tmp"))
        data = _make_report_data()
        result = gen.generate_report(data)
        parsed = json.loads(result)
        assert parsed["test_id"] == "test-001"
        assert parsed["test_name"] == "Test 001"

    def test_generate_report_sanitizes_inf(self) -> None:
        """Infinity values in tier metrics are sanitized to null."""
        gen = JsonReportGenerator(Path("/tmp"))
        data = _make_report_data()
        data.tiers = [
            TierMetrics(
                tier_id="T0",
                tier_name="Vanilla",
                pass_rate_median=0.5,
                impl_rate_median=0.5,
                composite_median=0.5,
                cost_of_pass_median=float("inf"),
                consistency_std_dev=0.1,
                uplift=0.0,
            )
        ]
        result = gen.generate_report(data)
        parsed = json.loads(result)
        assert parsed["tiers"][0]["cost_of_pass_median"] is None

    def test_write_report_creates_file(self) -> None:
        """write_report creates report.json in the correct directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = JsonReportGenerator(Path(tmpdir))
            data = _make_report_data()
            path = gen.write_report(data)

            assert path.exists()
            assert path.name == "report.json"
            assert path.parent.name == "test-001"

            content = json.loads(path.read_text())
            assert content["test_id"] == "test-001"

    def test_write_report_creates_directories(self) -> None:
        """write_report creates missing directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = JsonReportGenerator(Path(tmpdir) / "nested" / "reports")
            data = _make_report_data()
            path = gen.write_report(data)
            assert path.exists()

    def test_write_report_with_explicit_output_path(self) -> None:
        """When output_path is provided, write to that exact path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = JsonReportGenerator(Path(tmpdir))
            data = _make_report_data()
            target = Path(tmpdir) / "my-custom-report.json"

            path = gen.write_report(data, output_path=target)

            assert path == target
            assert target.exists()
            content = json.loads(target.read_text())
            assert content["test_id"] == "test-001"

    def test_write_report_with_output_path_creates_parents(self) -> None:
        """Parent directories are created when output_path has non-existent parents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = JsonReportGenerator(Path(tmpdir))
            data = _make_report_data()
            target = Path(tmpdir) / "deep" / "nested" / "report.json"

            path = gen.write_report(data, output_path=target)

            assert path == target
            assert target.exists()

    def test_write_report_without_output_path_uses_convention(self) -> None:
        """Default behavior (no output_path) writes to {base_dir}/{test_id}/report.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = JsonReportGenerator(Path(tmpdir))
            data = _make_report_data()

            path = gen.write_report(data)

            expected = Path(tmpdir) / "test-001" / "report.json"
            assert path == expected
            assert path.exists()
