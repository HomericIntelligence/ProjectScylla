"""Tests for JSON report generator."""

import json
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
    """Tests for the _sanitize_for_json helper."""

    def test_normal_values_unchanged(self) -> None:
        """Normal float, int, str, bool, None pass through unchanged."""
        obj = {"a": 1.5, "b": 42, "c": "hello", "d": True, "e": None}
        assert _sanitize_for_json(obj) == obj

    def test_inf_replaced_with_none(self) -> None:
        """float('inf') becomes None."""
        assert _sanitize_for_json(float("inf")) is None

    def test_negative_inf_replaced_with_none(self) -> None:
        """float('-inf') becomes None."""
        assert _sanitize_for_json(float("-inf")) is None

    def test_nan_replaced_with_none(self) -> None:
        """float('nan') becomes None."""
        assert _sanitize_for_json(float("nan")) is None

    def test_nested_dict(self) -> None:
        """Sanitizes values inside nested dicts."""
        obj = {"outer": {"inner": float("inf")}}
        result = _sanitize_for_json(obj)
        assert result == {"outer": {"inner": None}}

    def test_list_of_floats(self) -> None:
        """Sanitizes special floats inside lists."""
        obj = [1.0, float("nan"), float("-inf"), 3.5]
        result = _sanitize_for_json(obj)
        assert result == [1.0, None, None, 3.5]

    def test_mixed_nested_structure(self) -> None:
        """Sanitizes deeply nested mixed structures."""
        obj = {"tiers": [{"cost": float("inf")}, {"cost": 2.5}]}
        result = _sanitize_for_json(obj)
        assert result == {"tiers": [{"cost": None}, {"cost": 2.5}]}


class TestJsonReportGenerator:
    """Tests for JsonReportGenerator."""

    def test_generate_report_basic(self) -> None:
        """Basic ReportData serializes to valid JSON."""
        generator = JsonReportGenerator(Path("/tmp"))
        data = create_report_data(
            test_id="001-test",
            test_name="Test Name",
            timestamp="2024-01-15T14:30:00Z",
        )

        output = generator.generate_report(data)
        parsed = json.loads(output)

        assert parsed["test_id"] == "001-test"
        assert parsed["test_name"] == "Test Name"
        assert parsed["timestamp"] == "2024-01-15T14:30:00Z"
        assert parsed["tiers"] == []
        assert parsed["recommendations"] == []

    def test_generate_report_with_tiers(self) -> None:
        """ReportData with tiers serializes correctly."""
        generator = JsonReportGenerator(Path("/tmp"))
        data = create_report_data(
            test_id="001-test",
            test_name="Test Name",
            timestamp="2024-01-15T14:30:00Z",
        )
        data.tiers = [
            _make_tier_metrics(tier_id="T0"),
            _make_tier_metrics(tier_id="T1", tier_name="T1 (Prompted)", uplift=0.15),
        ]

        output = generator.generate_report(data)
        parsed = json.loads(output)

        assert len(parsed["tiers"]) == 2
        assert parsed["tiers"][0]["tier_id"] == "T0"
        assert parsed["tiers"][1]["tier_id"] == "T1"
        assert parsed["tiers"][1]["uplift"] == pytest.approx(0.15)

    def test_generate_report_sanitizes_inf(self) -> None:
        """Infinity cost values are serialized as null."""
        generator = JsonReportGenerator(Path("/tmp"))
        data = create_report_data(
            test_id="001-test",
            test_name="Test Name",
            timestamp="2024-01-15T14:30:00Z",
        )
        data.tiers = [_make_tier_metrics(cost_of_pass_median=float("inf"))]

        output = generator.generate_report(data)
        parsed = json.loads(output)

        assert parsed["tiers"][0]["cost_of_pass_median"] is None

    def test_generate_report_with_sensitivity(self) -> None:
        """SensitivityAnalysis is serialized correctly."""
        generator = JsonReportGenerator(Path("/tmp"))
        data = create_report_data(
            test_id="001-test",
            test_name="Test Name",
            timestamp="2024-01-15T14:30:00Z",
        )
        data.sensitivity = SensitivityAnalysis(0.05, 0.03, 0.10)

        output = generator.generate_report(data)
        parsed = json.loads(output)

        assert parsed["sensitivity"]["pass_rate_variance"] == pytest.approx(0.05)
        assert parsed["sensitivity"]["impl_rate_variance"] == pytest.approx(0.03)
        assert parsed["sensitivity"]["cost_variance"] == pytest.approx(0.10)

    def test_generate_report_with_transitions(self) -> None:
        """TransitionAssessments are serialized correctly."""
        generator = JsonReportGenerator(Path("/tmp"))
        data = create_report_data(
            test_id="001-test",
            test_name="Test Name",
            timestamp="2024-01-15T14:30:00Z",
        )
        data.transitions = [
            TransitionAssessment("T0", "T1", 0.1, 0.15, 0.5, True),
        ]

        output = generator.generate_report(data)
        parsed = json.loads(output)

        assert len(parsed["transitions"]) == 1
        assert parsed["transitions"][0]["from_tier"] == "T0"
        assert parsed["transitions"][0]["worth_it"] is True

    def test_write_report(self, tmp_path: Path) -> None:
        """write_report creates report.json at expected path."""
        generator = JsonReportGenerator(tmp_path)
        data = create_report_data(
            test_id="001-test",
            test_name="Test Name",
            timestamp="2024-01-15T14:30:00Z",
        )
        data.tiers = [_make_tier_metrics()]

        output_path = generator.write_report(data)

        assert output_path.exists()
        assert output_path.name == "report.json"
        assert output_path == tmp_path / "001-test" / "report.json"

        # Verify content is valid JSON
        content = output_path.read_text()
        parsed = json.loads(content)
        assert parsed["test_id"] == "001-test"

    def test_write_report_creates_directories(self, tmp_path: Path) -> None:
        """write_report creates intermediate directories."""
        generator = JsonReportGenerator(tmp_path / "nested" / "reports")
        data = create_report_data(
            test_id="deep-test",
            test_name="Deep Test",
            timestamp="2024-01-15T14:30:00Z",
        )

        output_path = generator.write_report(data)

        assert output_path.exists()
        assert output_path.parent.name == "deep-test"

    def test_get_report_dir(self) -> None:
        """get_report_dir returns base_dir / test_id."""
        generator = JsonReportGenerator(Path("/reports"))
        assert generator.get_report_dir("001-test") == Path("/reports/001-test")

    @pytest.mark.parametrize(
        "special_value",
        [float("inf"), float("-inf"), float("nan")],
        ids=["inf", "neg_inf", "nan"],
    )
    def test_special_float_values_produce_valid_json(self, special_value: float) -> None:
        """Special float values don't break JSON serialization."""
        generator = JsonReportGenerator(Path("/tmp"))
        data = create_report_data(
            test_id="001-test",
            test_name="Test Name",
            timestamp="2024-01-15T14:30:00Z",
        )
        data.tiers = [_make_tier_metrics(cost_of_pass_median=special_value)]

        output = generator.generate_report(data)
        # Must be valid JSON (json.loads would raise on bare Infinity/NaN)
        parsed = json.loads(output)
        assert parsed["tiers"][0]["cost_of_pass_median"] is None
