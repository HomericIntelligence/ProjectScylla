"""Tests for ablation score metrics."""

import pytest

from scylla.metrics.ablation import (
    AblationResult,
    AblationStudy,
    ComponentRole,
    analyze_component,
    calculate_ablation_score,
    calculate_relative_impact,
    compare_tier_ablations,
    run_ablation_study,
)


class TestCalculateAblationScore:
    """Tests for ablation score calculation."""

    def test_positive_contribution(self) -> None:
        """Component improves performance (positive score)."""
        score = calculate_ablation_score(baseline_score=0.8, ablated_score=0.6)
        assert score == pytest.approx(0.2)

    def test_negative_contribution(self) -> None:
        """Component hurts performance (negative score)."""
        score = calculate_ablation_score(baseline_score=0.6, ablated_score=0.8)
        assert score == pytest.approx(-0.2)

    def test_no_contribution(self) -> None:
        """Component has no effect."""
        score = calculate_ablation_score(baseline_score=0.8, ablated_score=0.8)
        assert score == 0.0

    def test_critical_component(self) -> None:
        """Removing critical component causes major degradation."""
        score = calculate_ablation_score(baseline_score=0.9, ablated_score=0.2)
        assert score == 0.7


class TestCalculateRelativeImpact:
    """Tests for relative impact calculation."""

    def test_ten_percent_impact(self) -> None:
        """10% of baseline performance."""
        impact = calculate_relative_impact(baseline_score=1.0, ablation_score=0.1)
        assert impact == 0.1

    def test_zero_baseline(self) -> None:
        """Zero baseline returns 0 impact."""
        impact = calculate_relative_impact(baseline_score=0.0, ablation_score=0.1)
        assert impact == 0.0

    def test_negative_impact(self) -> None:
        """Negative ablation score = negative impact."""
        impact = calculate_relative_impact(baseline_score=1.0, ablation_score=-0.2)
        assert impact == -0.2


class TestAnalyzeComponent:
    """Tests for component analysis."""

    def test_basic_analysis(self) -> None:
        """Analyze a component contribution."""
        result = analyze_component(
            component=ComponentRole.EVALUATOR,
            baseline_score=0.8,
            ablated_score=0.6,
            baseline_cost=1.0,
            ablated_cost=0.7,
        )

        assert result.component == ComponentRole.EVALUATOR
        assert result.ablation_score == pytest.approx(0.2)
        assert result.relative_impact == pytest.approx(0.25)  # 0.2 / 0.8
        assert result.cost_savings == pytest.approx(0.3)

    def test_redundant_component(self) -> None:
        """Analyze a component with negligible impact."""
        result = analyze_component(
            component=ComponentRole.MONITOR,
            baseline_score=0.8,
            ablated_score=0.79,
        )

        assert result.ablation_score == pytest.approx(0.01)
        assert result.relative_impact == pytest.approx(0.0125)


class TestRunAblationStudy:
    """Tests for complete ablation study."""

    def test_empty_study(self) -> None:
        """Study with no components."""
        study = run_ablation_study(
            tier_id="T5",
            baseline_score=0.8,
            baseline_cost=1.0,
            component_results={},
        )

        assert study.tier_id == "T5"
        assert study.baseline_score == 0.8
        assert len(study.results) == 0
        assert len(study.critical_components) == 0

    def test_classify_critical_component(self) -> None:
        """Critical components have high relative impact."""
        study = run_ablation_study(
            tier_id="T5",
            baseline_score=0.8,
            baseline_cost=1.0,
            component_results={
                ComponentRole.EVALUATOR: (0.5, 0.7),  # Big impact
                ComponentRole.MONITOR: (0.78, 0.95),  # Small impact
            },
            critical_threshold=0.1,
        )

        assert ComponentRole.EVALUATOR in study.critical_components
        assert ComponentRole.MONITOR not in study.critical_components

    def test_classify_redundant_component(self) -> None:
        """Redundant components have negligible impact."""
        study = run_ablation_study(
            tier_id="T5",
            baseline_score=0.8,
            baseline_cost=1.0,
            component_results={
                ComponentRole.MONITOR: (0.798, 0.99),  # Negligible
            },
            redundant_threshold=0.01,
        )

        assert ComponentRole.MONITOR in study.redundant_components

    def test_results_sorted_by_impact(self) -> None:
        """Results should be sorted by ablation score magnitude."""
        study = run_ablation_study(
            tier_id="T5",
            baseline_score=1.0,
            baseline_cost=1.0,
            component_results={
                ComponentRole.MONITOR: (0.95, 0.9),  # Small impact
                ComponentRole.EVALUATOR: (0.5, 0.7),  # Large impact
                ComponentRole.ORCHESTRATOR: (0.8, 0.85),  # Medium impact
            },
        )

        assert len(study.results) == 3
        # First should have highest impact
        assert study.results[0].component == ComponentRole.EVALUATOR
        # Last should have lowest impact
        assert study.results[2].component == ComponentRole.MONITOR


class TestCompareTierAblations:
    """Tests for cross-tier ablation comparison."""

    def test_compare_single_tier(self) -> None:
        """Compare with single tier."""
        study = AblationStudy(
            tier_id="T5",
            baseline_score=0.8,
            baseline_cost=1.0,
            results=[
                AblationResult(
                    component=ComponentRole.EVALUATOR,
                    baseline_score=0.8,
                    ablated_score=0.6,
                    ablation_score=0.2,
                    relative_impact=0.25,
                )
            ],
        )

        comparison = compare_tier_ablations([study])
        assert ComponentRole.EVALUATOR in comparison
        assert comparison[ComponentRole.EVALUATOR] == [0.2]

    def test_compare_multiple_tiers(self) -> None:
        """Compare same component across tiers."""
        study_t4 = AblationStudy(
            tier_id="T4",
            baseline_score=0.7,
            baseline_cost=0.8,
            results=[
                AblationResult(
                    component=ComponentRole.DELEGATION,
                    baseline_score=0.7,
                    ablated_score=0.5,
                    ablation_score=0.2,
                    relative_impact=0.286,
                )
            ],
        )
        study_t5 = AblationStudy(
            tier_id="T5",
            baseline_score=0.85,
            baseline_cost=1.2,
            results=[
                AblationResult(
                    component=ComponentRole.DELEGATION,
                    baseline_score=0.85,
                    ablated_score=0.6,
                    ablation_score=0.25,
                    relative_impact=0.294,
                )
            ],
        )

        comparison = compare_tier_ablations([study_t4, study_t5])
        assert ComponentRole.DELEGATION in comparison
        assert comparison[ComponentRole.DELEGATION] == [0.2, 0.25]


class TestComponentRole:
    """Tests for ComponentRole enum."""

    def test_core_components(self) -> None:
        """Core components are defined."""
        assert ComponentRole.TASK_DECOMPOSER.value == "task_decomposer"
        assert ComponentRole.ACTOR.value == "actor"
        assert ComponentRole.MONITOR.value == "monitor"
        assert ComponentRole.EVALUATOR.value == "evaluator"

    def test_tier_specific_components(self) -> None:
        """Tier-specific components are defined."""
        assert ComponentRole.SKILLS.value == "skills"
        assert ComponentRole.TOOLS.value == "tools"
        assert ComponentRole.DELEGATION.value == "delegation"
        assert ComponentRole.HIERARCHY.value == "hierarchy"
        assert ComponentRole.AGENTIC_RAG.value == "agentic_rag"
