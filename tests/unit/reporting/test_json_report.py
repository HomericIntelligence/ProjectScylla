"""Tests for JSON report generator."""

import json
import tempfile
from pathlib import Path

import pytest

from scylla.reporting.json_report import JsonReportGenerator, _sanitize_for_json
from scylla.reporting.markdown import (
    SensitivityAnalysis,
    TierMetrics,
    TransitionAssessment,
    create_report_data,
)


def _make_tier_metrics(
    tier_id: str = "T0",
    tier_name: str = "T0 (Vanilla)",
    pass_rate_median: float = 0.8,
    impl_rate_median: float = 0.75,
    composite_median: float = 0.775,
    cost_of_pass_median: float = 1.0,
    consistency_std_dev: float = 0.1,
    uplift: float = 0.0,
) -> TierMetrics:
    """Create test TierMetrics."""
    return TierMetrics(
        tier_id=tier_id,
        tier_name=tier_name,
        pass_rate_median=pass_rate_median,
        impl_rate_median=impl_rate_median,
        composite_median=composite_median,
        cost_of_pass_median=cost_of_pass_median,
        consistency_std_dev=consistency_std_dev,
        uplift=uplift,
    )


class TestSanitizeForJson:
    """Tests for _sanitize_for_json helper."""

    def test_nan_replaced_with_none(self) -> None:
        """Test NaN replaced with none."""
        result = _sanitize_for_json(float("nan"))
        assert result is None

    def test_inf_replaced_with_none(self) -> None:
        """Test Inf replaced with none."""
        result = _sanitize_for_json(float("inf"))
        assert result is None

    def test_negative_inf_replaced_with_none(self) -> None:
        """Test negative Inf replaced with none."""
        result = _sanitize_for_json(float("-inf"))
        assert result is None

    def test_normal_float_preserved(self) -> None:
        """Test normal float preserved."""
        result = _sanitize_for_json(1.5)
        assert result == 1.5

    def test_zero_float_preserved(self) -> None:
        """Test zero float preserved."""
        result = _sanitize_for_json(0.0)
        assert result == 0.0

    def test_dict_recursion(self) -> None:
        """Test dict recursion."""
        data: dict[str, object] = {"a": 1.0, "b": float("nan"), "c": "text"}
        result = _sanitize_for_json(data)
        assert result == {"a": 1.0, "b": None, "c": "text"}

    def test_list_recursion(self) -> None:
        """Test list recursion."""
        data: list[object] = [1.0, float("inf"), "text"]
        result = _sanitize_for_json(data)
        assert result == [1.0, None, "text"]

    def test_nested_dict_and_list(self) -> None:
        """Test nested dict and list."""
        data: dict[str, object] = {
            "tiers": [{"cost": float("inf")}, {"cost": 1.5}],
        }
        result = _sanitize_for_json(data)
        assert result == {"tiers": [{"cost": None}, {"cost": 1.5}]}

    def test_non_float_passthrough(self) -> None:
        """Test non-float passthrough."""
        assert _sanitize_for_json(42) == 42
        assert _sanitize_for_json("hello") == "hello"
        assert _sanitize_for_json(None) is None
        assert _sanitize_for_json(True) is True


class TestJsonReportGenerator:
    """Tests for JsonReportGenerator class."""

    def test_generate_report_valid_json(self) -> None:
        """Test generate_report returns valid JSON."""
        generator = JsonReportGenerator(Path("/tmp"))
        data = create_report_data(
            test_id="001-test",
            test_name="Test Name",
            timestamp="2024-01-15T14:30:00Z",
        )
        result = generator.generate_report(data)

        parsed = json.loads(result)
        assert parsed["test_id"] == "001-test"
        assert parsed["test_name"] == "Test Name"
        assert parsed["timestamp"] == "2024-01-15T14:30:00Z"
        assert parsed["tiers"] == []

    def test_generate_report_with_tiers(self) -> None:
        """Test generate_report includes tier data."""
        generator = JsonReportGenerator(Path("/tmp"))
        data = create_report_data(
            test_id="001-test",
            test_name="Test Name",
            timestamp="2024-01-15T14:30:00Z",
        )
        data.tiers = [
            _make_tier_metrics(tier_id="T0"),
            _make_tier_metrics(tier_id="T1", pass_rate_median=0.9, uplift=0.12),
        ]

        result = generator.generate_report(data)
        parsed = json.loads(result)

        assert len(parsed["tiers"]) == 2
        assert parsed["tiers"][0]["tier_id"] == "T0"
        assert parsed["tiers"][1]["tier_id"] == "T1"
        assert parsed["tiers"][1]["pass_rate_median"] == pytest.approx(0.9)

    def test_generate_report_sanitizes_infinity(self) -> None:
        """Test generate_report replaces Inf with null in JSON."""
        generator = JsonReportGenerator(Path("/tmp"))
        data = create_report_data(test_id="001-test", test_name="Test")
        data.tiers = [_make_tier_metrics(cost_of_pass_median=float("inf"))]

        result = generator.generate_report(data)
        parsed = json.loads(result)

        assert parsed["tiers"][0]["cost_of_pass_median"] is None

    def test_generate_report_with_sensitivity(self) -> None:
        """Test generate_report includes sensitivity analysis."""
        generator = JsonReportGenerator(Path("/tmp"))
        data = create_report_data(test_id="001-test", test_name="Test")
        data.sensitivity = SensitivityAnalysis(0.05, 0.03, 0.10)

        result = generator.generate_report(data)
        parsed = json.loads(result)

        assert parsed["sensitivity"]["pass_rate_variance"] == pytest.approx(0.05)

    def test_generate_report_with_transitions(self) -> None:
        """Test generate_report includes transition assessments."""
        generator = JsonReportGenerator(Path("/tmp"))
        data = create_report_data(test_id="001-test", test_name="Test")
        data.transitions = [
            TransitionAssessment("T0", "T1", 0.1, 0.15, 0.5, True),
        ]

        result = generator.generate_report(data)
        parsed = json.loads(result)

        assert len(parsed["transitions"]) == 1
        assert parsed["transitions"][0]["from_tier"] == "T0"
        assert parsed["transitions"][0]["worth_it"] is True

    def test_write_report_creates_file(self) -> None:
        """Test write_report creates the JSON file on disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = JsonReportGenerator(Path(tmpdir))
            data = create_report_data(test_id="001-test", test_name="Test")
            data.tiers = [_make_tier_metrics()]

            output_path = generator.write_report(data)

            assert output_path.exists()
            assert output_path.name == "report.json"
            expected_path = Path(tmpdir) / "001-test" / "report.json"
            assert output_path == expected_path

            # Verify content is valid JSON
            content = json.loads(output_path.read_text())
            assert content["test_id"] == "001-test"

    def test_get_report_dir(self) -> None:
        """Test get_report_dir returns correct path."""
        generator = JsonReportGenerator(Path("/reports"))
        assert generator.get_report_dir("001-test") == Path("/reports/001-test")

    def test_write_report_creates_directories(self) -> None:
        """write_report creates missing directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = JsonReportGenerator(Path(tmpdir) / "nested" / "reports")
            data = create_report_data(test_id="test-001", test_name="Test 001")
            path = generator.write_report(data)
            assert path.exists()
