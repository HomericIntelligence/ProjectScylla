"""Tests for _load_report_data() loading logic."""

import pytest

from scylla.cli.main import _load_report_data
from scylla.reporting import ReportData, SensitivityAnalysis, TierMetrics, TransitionAssessment


def _make_result(
    tier_id: str = "T0",
    pass_rate: float = 0.8,
    impl_rate: float = 0.7,
    composite_score: float = 0.75,
    cost_of_pass: float = 1.50,
) -> dict[str, object]:
    """Create a minimal result dict matching the on-disk result.json schema."""
    return {
        "tier_id": tier_id,
        "grading": {
            "pass_rate": pass_rate,
            "composite_score": composite_score,
            "cost_of_pass": cost_of_pass,
        },
        "judgment": {
            "impl_rate": impl_rate,
            "passed": pass_rate > 0,
            "letter_grade": "B",
        },
        "metrics": {
            "cost_usd": 0.05,
        },
    }


class TestLoadReportDataBasic:
    """Basic behaviour of _load_report_data."""

    def test_returns_report_data(self) -> None:
        """Returns a ReportData instance."""
        result = _load_report_data("test-001", [_make_result()])
        assert isinstance(result, ReportData)

    def test_test_id_propagated(self) -> None:
        """test_id is set on the returned ReportData."""
        result = _load_report_data("test-001", [_make_result()])
        assert result.test_id == "test-001"

    def test_test_name_derived(self) -> None:
        """test_name is derived from test_id."""
        result = _load_report_data("my-cool-test", [_make_result()])
        assert result.test_name == "My Cool Test"

    def test_raises_on_empty_results(self) -> None:
        """Raises ValueError when results list is empty."""
        with pytest.raises(ValueError, match="No results provided"):
            _load_report_data("test-001", [])


class TestLoadReportDataSingleTier:
    """Single-tier scenarios."""

    def test_single_tier_populates_tiers(self) -> None:
        """A single tier produces exactly one TierMetrics entry."""
        results = [_make_result("T0")]
        data = _load_report_data("test-001", results)
        assert len(data.tiers) == 1
        assert isinstance(data.tiers[0], TierMetrics)
        assert data.tiers[0].tier_id == "T0"

    def test_single_tier_pass_rate(self) -> None:
        """Pass rate median is correctly calculated for a single result."""
        results = [_make_result("T0", pass_rate=0.6)]
        data = _load_report_data("test-001", results)
        assert data.tiers[0].pass_rate_median == pytest.approx(0.6)

    def test_single_tier_impl_rate(self) -> None:
        """Implementation rate median is correctly calculated."""
        results = [_make_result("T0", impl_rate=0.9)]
        data = _load_report_data("test-001", results)
        assert data.tiers[0].impl_rate_median == pytest.approx(0.9)

    def test_single_tier_cost_of_pass(self) -> None:
        """Cost-of-pass median is correctly calculated."""
        results = [_make_result("T0", cost_of_pass=2.50)]
        data = _load_report_data("test-001", results)
        assert data.tiers[0].cost_of_pass_median == pytest.approx(2.50)

    def test_single_tier_no_sensitivity(self) -> None:
        """Sensitivity analysis is None with a single tier."""
        data = _load_report_data("test-001", [_make_result("T0")])
        assert data.sensitivity is None

    def test_single_tier_no_transitions(self) -> None:
        """No transitions with a single tier."""
        data = _load_report_data("test-001", [_make_result("T0")])
        assert data.transitions == []

    def test_runs_per_tier_count(self) -> None:
        """runs_per_tier reflects the number of results for the first tier."""
        results = [_make_result("T0"), _make_result("T0")]
        data = _load_report_data("test-001", results)
        assert data.runs_per_tier == 2


class TestLoadReportDataMultipleTiers:
    """Multi-tier scenarios."""

    def test_two_tiers_sorted(self) -> None:
        """Tiers are sorted by tier_id."""
        results = [_make_result("T1"), _make_result("T0")]
        data = _load_report_data("test-001", results)
        assert [t.tier_id for t in data.tiers] == ["T0", "T1"]

    def test_sensitivity_populated(self) -> None:
        """Sensitivity analysis is populated with multiple tiers."""
        results = [
            _make_result("T0", pass_rate=0.4, impl_rate=0.3),
            _make_result("T1", pass_rate=0.8, impl_rate=0.7),
        ]
        data = _load_report_data("test-001", results)
        assert data.sensitivity is not None
        assert isinstance(data.sensitivity, SensitivityAnalysis)
        assert data.sensitivity.pass_rate_variance > 0

    def test_transitions_populated(self) -> None:
        """Transitions are populated with multiple tiers."""
        results = [
            _make_result("T0", pass_rate=0.4),
            _make_result("T1", pass_rate=0.8),
        ]
        data = _load_report_data("test-001", results)
        assert len(data.transitions) == 1
        assert isinstance(data.transitions[0], TransitionAssessment)
        assert data.transitions[0].from_tier == "T0"
        assert data.transitions[0].to_tier == "T1"

    def test_transition_pass_rate_delta(self) -> None:
        """Transition pass_rate_delta is computed correctly."""
        results = [
            _make_result("T0", pass_rate=0.3),
            _make_result("T1", pass_rate=0.7),
        ]
        data = _load_report_data("test-001", results)
        assert data.transitions[0].pass_rate_delta == pytest.approx(0.4)

    def test_three_tiers_two_transitions(self) -> None:
        """Three tiers produce two transition assessments."""
        results = [
            _make_result("T0"),
            _make_result("T1"),
            _make_result("T2"),
        ]
        data = _load_report_data("test-001", results)
        assert len(data.transitions) == 2
        assert data.transitions[0].from_tier == "T0"
        assert data.transitions[0].to_tier == "T1"
        assert data.transitions[1].from_tier == "T1"
        assert data.transitions[1].to_tier == "T2"

    def test_uplift_vs_t0(self) -> None:
        """Tiers other than T0 have uplift calculated relative to T0."""
        results = [
            _make_result("T0", pass_rate=0.5),
            _make_result("T1", pass_rate=0.75),
        ]
        data = _load_report_data("test-001", results)
        t0_tier = data.tiers[0]
        t1_tier = data.tiers[1]
        assert t0_tier.uplift == 0.0
        # uplift = ((0.75 - 0.5) / 0.5) * 100 = 50.0
        assert t1_tier.uplift == pytest.approx(50.0)


class TestLoadReportDataEdgeCases:
    """Edge-case scenarios."""

    def test_inf_cost_of_pass(self) -> None:
        """Infinity cost_of_pass is handled gracefully."""
        results = [_make_result("T0", cost_of_pass=float("inf"))]
        data = _load_report_data("test-001", results)
        assert data.tiers[0].cost_of_pass_median == float("inf")

    def test_multiple_results_per_tier_median(self) -> None:
        """Median is computed when multiple results exist for one tier."""
        results = [
            _make_result("T0", pass_rate=0.2),
            _make_result("T0", pass_rate=0.6),
            _make_result("T0", pass_rate=1.0),
        ]
        data = _load_report_data("test-001", results)
        assert data.tiers[0].pass_rate_median == pytest.approx(0.6)

    def test_key_finding_populated(self) -> None:
        """key_finding contains run and tier counts."""
        results = [_make_result("T0"), _make_result("T1")]
        data = _load_report_data("test-001", results)
        assert "2 runs" in data.key_finding
        assert "2 tier" in data.key_finding

    def test_recommendations_populated(self) -> None:
        """Recommendations list is non-empty."""
        data = _load_report_data("test-001", [_make_result()])
        assert len(data.recommendations) >= 1

    def test_timestamp_is_set(self) -> None:
        """Timestamp is a non-empty string."""
        data = _load_report_data("test-001", [_make_result()])
        assert isinstance(data.timestamp, str)
        assert len(data.timestamp) > 0

    def test_judge_model_is_set(self) -> None:
        """judge_model is set."""
        data = _load_report_data("test-001", [_make_result()])
        assert data.judge_model != ""
