"""Tests for grading calculations.

Python justification: Required for pytest testing framework.
"""

import math

import pytest

from scylla.metrics.grading import (
    GradingResult,
    assign_letter_grade,
    calculate_composite_score,
    calculate_cost_delta,
    calculate_cost_of_pass,
    calculate_impl_rate,
    calculate_pass_rate,
    calculate_tier_uplift,
    grade_run,
)


class TestCalculatePassRate:
    """Tests for pass rate calculation."""

    def test_passed(self) -> None:
        assert calculate_pass_rate(True) == 1.0

    def test_failed(self) -> None:
        assert calculate_pass_rate(False) == 0.0


class TestCalculateImplRate:
    """Tests for implementation rate calculation."""

    def test_valid_score(self) -> None:
        assert calculate_impl_rate(0.85) == 0.85

    def test_clamps_above_one(self) -> None:
        assert calculate_impl_rate(1.5) == 1.0

    def test_clamps_below_zero(self) -> None:
        assert calculate_impl_rate(-0.5) == 0.0

    def test_boundary_values(self) -> None:
        assert calculate_impl_rate(0.0) == 0.0
        assert calculate_impl_rate(1.0) == 1.0


class TestCalculateCostOfPass:
    """Tests for cost of pass calculation."""

    def test_normal_case(self) -> None:
        # Cost $1.00, pass rate 0.5 -> $2.00 per pass
        assert calculate_cost_of_pass(1.0, 0.5) == 2.0

    def test_full_pass_rate(self) -> None:
        # Cost $1.00, pass rate 1.0 -> $1.00 per pass
        assert calculate_cost_of_pass(1.0, 1.0) == 1.0

    def test_zero_pass_rate(self) -> None:
        # Zero pass rate -> infinity
        result = calculate_cost_of_pass(1.0, 0.0)
        assert math.isinf(result)

    def test_negative_pass_rate(self) -> None:
        # Negative pass rate -> infinity
        result = calculate_cost_of_pass(1.0, -0.1)
        assert math.isinf(result)

    def test_zero_cost(self) -> None:
        # Zero cost -> 0 per pass
        assert calculate_cost_of_pass(0.0, 0.5) == 0.0


class TestCalculateCompositeScore:
    """Tests for composite score calculation."""

    def test_default_weights(self) -> None:
        # Equal weights: (0.8 + 0.6) / 2 = 0.7
        assert calculate_composite_score(0.8, 0.6) == pytest.approx(0.7)

    def test_custom_weights(self) -> None:
        # pass_rate=0.8 (weight=2), impl_rate=0.6 (weight=1)
        # (0.8*2 + 0.6*1) / 3 = 2.2/3 = 0.733...
        result = calculate_composite_score(0.8, 0.6, pass_weight=2.0, impl_weight=1.0)
        assert result == pytest.approx(2.2 / 3)

    def test_zero_weights(self) -> None:
        # Zero total weight -> 0
        assert calculate_composite_score(0.8, 0.6, pass_weight=0.0, impl_weight=0.0) == 0.0

    def test_perfect_scores(self) -> None:
        assert calculate_composite_score(1.0, 1.0) == 1.0

    def test_zero_scores(self) -> None:
        assert calculate_composite_score(0.0, 0.0) == 0.0


class TestAssignLetterGrade:
    """Tests for letter grade assignment."""

    def test_grade_a(self) -> None:
        assert assign_letter_grade(0.95) == "A"
        assert assign_letter_grade(1.0) == "A"

    def test_grade_b(self) -> None:
        assert assign_letter_grade(0.85) == "B"
        assert assign_letter_grade(0.94) == "B"

    def test_grade_c(self) -> None:
        assert assign_letter_grade(0.75) == "C"
        assert assign_letter_grade(0.84) == "C"

    def test_grade_d(self) -> None:
        assert assign_letter_grade(0.65) == "D"
        assert assign_letter_grade(0.74) == "D"

    def test_grade_f(self) -> None:
        assert assign_letter_grade(0.64) == "F"
        assert assign_letter_grade(0.0) == "F"


class TestCalculateTierUplift:
    """Tests for tier uplift calculation."""

    def test_positive_uplift(self) -> None:
        # T1 = 0.8, T0 = 0.5 -> (0.8-0.5)/0.5 = 0.6 (60% improvement)
        assert calculate_tier_uplift(0.8, 0.5) == pytest.approx(0.6)

    def test_no_uplift(self) -> None:
        # Same score -> 0% uplift
        assert calculate_tier_uplift(0.5, 0.5) == 0.0

    def test_negative_uplift(self) -> None:
        # Regression: T1 < T0
        # T1 = 0.4, T0 = 0.5 -> (0.4-0.5)/0.5 = -0.2 (-20%)
        assert calculate_tier_uplift(0.4, 0.5) == pytest.approx(-0.2)

    def test_zero_baseline(self) -> None:
        # Zero baseline -> 0 (avoid division by zero)
        assert calculate_tier_uplift(0.8, 0.0) == 0.0


class TestCalculateCostDelta:
    """Tests for cost delta calculation."""

    def test_multiple_costs(self) -> None:
        costs = [0.50, 0.75, 1.25, 0.80]
        # max - min = 1.25 - 0.50 = 0.75
        assert calculate_cost_delta(costs) == pytest.approx(0.75)

    def test_identical_costs(self) -> None:
        costs = [1.0, 1.0, 1.0]
        assert calculate_cost_delta(costs) == 0.0

    def test_single_cost(self) -> None:
        costs = [1.0]
        assert calculate_cost_delta(costs) == 0.0

    def test_empty_list(self) -> None:
        assert calculate_cost_delta([]) == 0.0


class TestGradingResult:
    """Tests for GradingResult dataclass."""

    def test_dataclass_fields(self) -> None:
        result = GradingResult(
            pass_rate=1.0,
            impl_rate=0.85,
            cost_of_pass=1.50,
            composite_score=0.925,
            letter_grade="A",
        )
        assert result.pass_rate == 1.0
        assert result.impl_rate == 0.85
        assert result.cost_of_pass == 1.50
        assert result.composite_score == 0.925
        assert result.letter_grade == "A"


class TestGradeRun:
    """Tests for grade_run function."""

    def test_passing_run(self) -> None:
        result = grade_run(passed=True, weighted_score=0.9, cost_usd=1.0)
        assert result.pass_rate == 1.0
        assert result.impl_rate == 0.9
        assert result.cost_of_pass == 1.0
        assert result.composite_score == pytest.approx(0.95)
        assert result.letter_grade == "A"

    def test_failing_run(self) -> None:
        result = grade_run(passed=False, weighted_score=0.5, cost_usd=1.0)
        assert result.pass_rate == 0.0
        assert result.impl_rate == 0.5
        assert math.isinf(result.cost_of_pass)
        assert result.composite_score == pytest.approx(0.25)
        assert result.letter_grade == "F"

    def test_mixed_run(self) -> None:
        result = grade_run(passed=True, weighted_score=0.7, cost_usd=2.0)
        assert result.pass_rate == 1.0
        assert result.impl_rate == 0.7
        assert result.cost_of_pass == 2.0
        assert result.composite_score == pytest.approx(0.85)
        assert result.letter_grade == "B"
