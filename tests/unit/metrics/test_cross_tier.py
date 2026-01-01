"""Tests for cross-tier analysis.

Python justification: Required for pytest testing framework.
"""

import pytest

from scylla.metrics.aggregator import AggregatedStats, TierStatistics
from scylla.metrics.cross_tier import (
    CrossTierAnalyzer,
    PromptSensitivityAnalysis,
    TierTransitionAssessment,
    TierUplift,
    calculate_frontier_cop,
)


def make_stats(
    median: float = 0.8,
    mean: float = 0.8,
    std_dev: float = 0.05,
    count: int = 10,
) -> AggregatedStats:
    """Helper to create AggregatedStats."""
    return AggregatedStats(
        median=median,
        mean=mean,
        mode=median,
        min=median - 0.1,
        max=median + 0.1,
        std_dev=std_dev,
        count=count,
    )


def make_tier_stats(
    tier_id: str,
    pass_rate: float = 1.0,
    impl_rate: float = 0.8,
    cost_usd: float = 1.0,
    duration: float = 60.0,
) -> TierStatistics:
    """Helper to create TierStatistics."""
    composite = (pass_rate + impl_rate) / 2
    return TierStatistics(
        tier_id=tier_id,
        runs_completed=10,
        pass_rate=make_stats(pass_rate),
        impl_rate=make_stats(impl_rate),
        cost_usd=make_stats(cost_usd),
        duration_seconds=make_stats(duration),
        composite_score=make_stats(composite),
        grade="B",
    )


class TestTierUplift:
    """Tests for TierUplift dataclass."""

    def test_create_uplift(self) -> None:
        uplift = TierUplift(
            tier_id="T1",
            pass_rate_uplift=0.1,
            impl_rate_uplift=0.2,
            composite_uplift=0.15,
            cost_change=0.05,
        )
        assert uplift.tier_id == "T1"
        assert uplift.pass_rate_uplift == 0.1
        assert uplift.composite_uplift == 0.15


class TestPromptSensitivityAnalysis:
    """Tests for PromptSensitivityAnalysis dataclass."""

    def test_create_analysis(self) -> None:
        analysis = PromptSensitivityAnalysis(
            pass_rate_variance=0.05,
            impl_rate_variance=0.03,
            cost_variance=0.10,
            pass_rate_sensitivity="low",
            impl_rate_sensitivity="low",
            cost_sensitivity="medium",
            tier_uplifts={},
            cost_of_pass_delta=0.5,
            best_value_tier="T1",
        )
        assert analysis.pass_rate_variance == 0.05
        assert analysis.pass_rate_sensitivity == "low"
        assert analysis.best_value_tier == "T1"


class TestTierTransitionAssessment:
    """Tests for TierTransitionAssessment dataclass."""

    def test_create_assessment(self) -> None:
        assessment = TierTransitionAssessment(
            from_tier="T0",
            to_tier="T1",
            pass_rate_delta=0.1,
            impl_rate_delta=0.15,
            cost_delta=0.2,
            worth_it=True,
            reason="+12.5% quality for +20.0% cost",
        )
        assert assessment.from_tier == "T0"
        assert assessment.to_tier == "T1"
        assert assessment.worth_it is True


class TestCrossTierAnalyzerCalculateVariance:
    """Tests for calculate_variance method."""

    def test_single_tier(self) -> None:
        tier_stats = {"T0": make_tier_stats("T0")}
        analyzer = CrossTierAnalyzer(tier_stats)
        variance = analyzer.calculate_variance("pass_rate")
        assert variance == 0.0

    def test_multiple_tiers_same_values(self) -> None:
        tier_stats = {
            "T0": make_tier_stats("T0", pass_rate=1.0),
            "T1": make_tier_stats("T1", pass_rate=1.0),
        }
        analyzer = CrossTierAnalyzer(tier_stats)
        variance = analyzer.calculate_variance("pass_rate")
        assert variance == 0.0

    def test_multiple_tiers_different_values(self) -> None:
        tier_stats = {
            "T0": make_tier_stats("T0", impl_rate=0.6),
            "T1": make_tier_stats("T1", impl_rate=0.8),
        }
        analyzer = CrossTierAnalyzer(tier_stats)
        variance = analyzer.calculate_variance("impl_rate")
        assert variance > 0


class TestCrossTierAnalyzerInterpretSensitivity:
    """Tests for interpret_sensitivity method."""

    def test_low_sensitivity(self) -> None:
        analyzer = CrossTierAnalyzer({})
        assert analyzer.interpret_sensitivity(0.01) == "low"
        assert analyzer.interpret_sensitivity(0.04) == "low"

    def test_medium_sensitivity(self) -> None:
        analyzer = CrossTierAnalyzer({})
        assert analyzer.interpret_sensitivity(0.06) == "medium"
        assert analyzer.interpret_sensitivity(0.14) == "medium"

    def test_high_sensitivity(self) -> None:
        analyzer = CrossTierAnalyzer({})
        assert analyzer.interpret_sensitivity(0.16) == "high"
        assert analyzer.interpret_sensitivity(0.5) == "high"


class TestCrossTierAnalyzerCalculateUplift:
    """Tests for calculate_uplift method."""

    def test_uplift_vs_t0(self) -> None:
        tier_stats = {
            "T0": make_tier_stats("T0", pass_rate=1.0, impl_rate=0.6),
            "T1": make_tier_stats("T1", pass_rate=1.0, impl_rate=0.8),
        }
        analyzer = CrossTierAnalyzer(tier_stats)
        uplift = analyzer.calculate_uplift("T1")

        assert uplift.tier_id == "T1"
        assert uplift.impl_rate_uplift == pytest.approx(0.333, rel=0.01)

    def test_no_t0_baseline(self) -> None:
        tier_stats = {
            "T1": make_tier_stats("T1", pass_rate=1.0, impl_rate=0.8),
        }
        analyzer = CrossTierAnalyzer(tier_stats)
        uplift = analyzer.calculate_uplift("T1")

        assert uplift.pass_rate_uplift == 0.0
        assert uplift.impl_rate_uplift == 0.0

    def test_cost_change(self) -> None:
        tier_stats = {
            "T0": make_tier_stats("T0", cost_usd=1.0),
            "T1": make_tier_stats("T1", cost_usd=1.5),
        }
        analyzer = CrossTierAnalyzer(tier_stats)
        uplift = analyzer.calculate_uplift("T1")

        assert uplift.cost_change == pytest.approx(0.5)


class TestCrossTierAnalyzerAssessTransition:
    """Tests for assess_transition method."""

    def test_worth_it_transition(self) -> None:
        """Quality improvement outweighs cost increase."""
        tier_stats = {
            "T0": make_tier_stats("T0", pass_rate=0.6, impl_rate=0.5, cost_usd=1.0),
            "T1": make_tier_stats("T1", pass_rate=0.9, impl_rate=0.8, cost_usd=1.2),
        }
        analyzer = CrossTierAnalyzer(tier_stats)
        assessment = analyzer.assess_transition("T0", "T1")

        assert assessment.from_tier == "T0"
        assert assessment.to_tier == "T1"
        assert assessment.pass_rate_delta == pytest.approx(0.3)
        assert assessment.impl_rate_delta == pytest.approx(0.3)
        assert assessment.worth_it is True

    def test_not_worth_it_transition(self) -> None:
        """Cost increase outweighs quality improvement."""
        tier_stats = {
            "T0": make_tier_stats("T0", pass_rate=0.9, impl_rate=0.8, cost_usd=1.0),
            "T1": make_tier_stats("T1", pass_rate=0.91, impl_rate=0.81, cost_usd=2.0),
        }
        analyzer = CrossTierAnalyzer(tier_stats)
        assessment = analyzer.assess_transition("T0", "T1")

        assert assessment.worth_it is False
        assert "Only" in assessment.reason


class TestCrossTierAnalyzerAnalyze:
    """Tests for analyze method."""

    def test_empty_tiers(self) -> None:
        analyzer = CrossTierAnalyzer({})
        analysis = analyzer.analyze()

        assert analysis.pass_rate_variance == 0.0
        assert analysis.pass_rate_sensitivity == "low"
        assert analysis.tier_uplifts == {}
        assert analysis.best_value_tier == "T0"

    def test_single_tier(self) -> None:
        tier_stats = {"T0": make_tier_stats("T0")}
        analyzer = CrossTierAnalyzer(tier_stats)
        analysis = analyzer.analyze()

        assert analysis.pass_rate_variance == 0.0
        assert analysis.tier_uplifts == {}
        assert analysis.best_value_tier == "T0"

    def test_multiple_tiers(self) -> None:
        tier_stats = {
            "T0": make_tier_stats("T0", pass_rate=1.0, impl_rate=0.6, cost_usd=1.0),
            "T1": make_tier_stats("T1", pass_rate=1.0, impl_rate=0.8, cost_usd=1.2),
            "T2": make_tier_stats("T2", pass_rate=1.0, impl_rate=0.9, cost_usd=2.0),
        }
        analyzer = CrossTierAnalyzer(tier_stats)
        analysis = analyzer.analyze()

        assert analysis.impl_rate_variance > 0
        assert "T1" in analysis.tier_uplifts
        assert "T2" in analysis.tier_uplifts
        assert analysis.best_value_tier in ["T0", "T1", "T2"]

    def test_best_value_tier_selection(self) -> None:
        """Best value tier should be the one with highest quality/cost ratio."""
        tier_stats = {
            "T0": make_tier_stats("T0", pass_rate=1.0, impl_rate=0.6, cost_usd=1.0),
            "T1": make_tier_stats("T1", pass_rate=1.0, impl_rate=0.8, cost_usd=1.0),
            "T2": make_tier_stats("T2", pass_rate=1.0, impl_rate=0.9, cost_usd=5.0),
        }
        analyzer = CrossTierAnalyzer(tier_stats)
        analysis = analyzer.analyze()

        # T1 has best quality/cost ratio (0.9 composite / 1.0 cost = 0.9)
        assert analysis.best_value_tier == "T1"

    def test_cost_of_pass_delta(self) -> None:
        tier_stats = {
            "T0": make_tier_stats("T0", pass_rate=1.0, cost_usd=1.0),
            "T1": make_tier_stats("T1", pass_rate=1.0, cost_usd=2.0),
        }
        analyzer = CrossTierAnalyzer(tier_stats)
        analysis = analyzer.analyze()

        # CoP for T0 = 1.0/1.0 = 1.0, CoP for T1 = 2.0/1.0 = 2.0
        # Delta = 2.0 - 1.0 = 1.0
        assert analysis.cost_of_pass_delta == pytest.approx(1.0)


class TestCrossTierAnalyzerAssessAllTransitions:
    """Tests for assess_all_transitions method."""

    def test_assess_all(self) -> None:
        tier_stats = {
            "T0": make_tier_stats("T0", pass_rate=0.7, impl_rate=0.6),
            "T1": make_tier_stats("T1", pass_rate=0.8, impl_rate=0.7),
            "T2": make_tier_stats("T2", pass_rate=0.9, impl_rate=0.8),
        }
        analyzer = CrossTierAnalyzer(tier_stats)
        transitions = analyzer.assess_all_transitions()

        assert len(transitions) == 2
        assert transitions[0].from_tier == "T0"
        assert transitions[0].to_tier == "T1"
        assert transitions[1].from_tier == "T1"
        assert transitions[1].to_tier == "T2"

    def test_single_tier(self) -> None:
        tier_stats = {"T0": make_tier_stats("T0")}
        analyzer = CrossTierAnalyzer(tier_stats)
        transitions = analyzer.assess_all_transitions()

        assert transitions == []


class TestCalculateFrontierCop:
    """Tests for calculate_frontier_cop function."""

    def test_empty_tiers(self) -> None:
        """Empty tiers returns infinity and T0."""
        frontier, tier = calculate_frontier_cop({})
        assert frontier == float("inf")
        assert tier == "T0"

    def test_single_tier(self) -> None:
        """Single tier returns that tier's CoP."""
        tier_stats = {"T0": make_tier_stats("T0", pass_rate=1.0, cost_usd=2.0)}
        frontier, tier = calculate_frontier_cop(tier_stats)
        assert frontier == 2.0  # 2.0 / 1.0
        assert tier == "T0"

    def test_multiple_tiers_find_minimum(self) -> None:
        """Finds tier with minimum CoP."""
        tier_stats = {
            "T0": make_tier_stats("T0", pass_rate=0.5, cost_usd=1.0),  # CoP = 2.0
            "T1": make_tier_stats("T1", pass_rate=1.0, cost_usd=1.0),  # CoP = 1.0 (best)
            "T2": make_tier_stats("T2", pass_rate=0.8, cost_usd=2.0),  # CoP = 2.5
        }
        frontier, tier = calculate_frontier_cop(tier_stats)
        assert frontier == 1.0
        assert tier == "T1"

    def test_zero_pass_rate_excluded(self) -> None:
        """Tiers with 0 pass rate are excluded from calculation."""
        tier_stats = {
            "T0": make_tier_stats("T0", pass_rate=0.0, cost_usd=0.5),  # Excluded
            "T1": make_tier_stats("T1", pass_rate=1.0, cost_usd=2.0),  # CoP = 2.0
        }
        frontier, tier = calculate_frontier_cop(tier_stats)
        assert frontier == 2.0
        assert tier == "T1"

    def test_all_zero_pass_rate(self) -> None:
        """All tiers with 0 pass rate returns infinity."""
        tier_stats = {
            "T0": make_tier_stats("T0", pass_rate=0.0, cost_usd=1.0),
            "T1": make_tier_stats("T1", pass_rate=0.0, cost_usd=2.0),
        }
        frontier, tier = calculate_frontier_cop(tier_stats)
        assert frontier == float("inf")
        assert tier == "T0"


class TestAnalyzeFrontierCop:
    """Tests for frontier_cop in analyze() method."""

    def test_frontier_cop_in_analysis(self) -> None:
        """Analyze includes frontier_cop calculation."""
        tier_stats = {
            "T0": make_tier_stats("T0", pass_rate=0.5, cost_usd=1.0),  # CoP = 2.0
            "T1": make_tier_stats("T1", pass_rate=1.0, cost_usd=1.5),  # CoP = 1.5 (best)
        }
        analyzer = CrossTierAnalyzer(tier_stats)
        analysis = analyzer.analyze()

        assert analysis.frontier_cop == 1.5
        assert analysis.frontier_cop_tier == "T1"

    def test_empty_returns_infinity(self) -> None:
        """Empty tiers returns infinity for frontier_cop."""
        analyzer = CrossTierAnalyzer({})
        analysis = analyzer.analyze()

        assert analysis.frontier_cop == float("inf")
        assert analysis.frontier_cop_tier == "T0"


class TestPromptSensitivityAnalysisFrontierCop:
    """Tests for PromptSensitivityAnalysis dataclass with frontier_cop."""

    def test_has_frontier_cop_fields(self) -> None:
        """PromptSensitivityAnalysis includes frontier_cop fields."""
        analysis = PromptSensitivityAnalysis(
            pass_rate_variance=0.05,
            impl_rate_variance=0.03,
            cost_variance=0.10,
            pass_rate_sensitivity="low",
            impl_rate_sensitivity="low",
            cost_sensitivity="medium",
            tier_uplifts={},
            cost_of_pass_delta=0.5,
            best_value_tier="T1",
            frontier_cop=1.5,
            frontier_cop_tier="T1",
        )
        assert analysis.frontier_cop == 1.5
        assert analysis.frontier_cop_tier == "T1"
