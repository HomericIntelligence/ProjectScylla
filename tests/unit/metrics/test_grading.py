"""Tests for grading calculations."""

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
        """Test Passed."""
        assert calculate_pass_rate(True) == 1.0

    def test_failed(self) -> None:
        """Test Failed."""
        assert calculate_pass_rate(False) == 0.0


class TestCalculateImplRate:
    """Tests for implementation rate calculation."""

    def test_valid_score(self) -> None:
        """Test Valid score."""
        assert calculate_impl_rate(0.85) == 0.85

    def test_clamps_above_one(self) -> None:
        """Test Clamps above one."""
        assert calculate_impl_rate(1.5) == 1.0

    def test_clamps_below_zero(self) -> None:
        """Test Clamps below zero."""
        assert calculate_impl_rate(-0.5) == 0.0

    def test_boundary_values(self) -> None:
        """Test Boundary values."""
        assert calculate_impl_rate(0.0) == 0.0
        assert calculate_impl_rate(1.0) == 1.0


class TestCalculateCostOfPass:
    """Tests for cost of pass calculation."""

    def test_normal_case(self) -> None:
        """Test Normal case."""
        # Cost $1.00, pass rate 0.5 -> $2.00 per pass
        assert calculate_cost_of_pass(1.0, 0.5) == 2.0

    def test_full_pass_rate(self) -> None:
        """Test Full pass rate."""
        # Cost $1.00, pass rate 1.0 -> $1.00 per pass
        assert calculate_cost_of_pass(1.0, 1.0) == 1.0

    def test_zero_pass_rate(self) -> None:
        """Test Zero pass rate."""
        # Zero pass rate -> infinity
        result = calculate_cost_of_pass(1.0, 0.0)
        assert math.isinf(result)

    def test_negative_pass_rate(self) -> None:
        """Test Negative pass rate."""
        # Negative pass rate -> infinity
        result = calculate_cost_of_pass(1.0, -0.1)
        assert math.isinf(result)

    def test_zero_cost(self) -> None:
        """Test Zero cost."""
        # Zero cost -> 0 per pass
        assert calculate_cost_of_pass(0.0, 0.5) == 0.0


class TestCalculateCompositeScore:
    """Tests for composite score calculation."""

    def test_default_weights(self) -> None:
        """Test Default weights."""
        # Equal weights: (0.8 + 0.6) / 2 = 0.7
        assert calculate_composite_score(0.8, 0.6) == pytest.approx(0.7)

    def test_custom_weights(self) -> None:
        """Test Custom weights."""
        # pass_rate=0.8 (weight=2), impl_rate=0.6 (weight=1)
        # (0.8*2 + 0.6*1) / 3 = 2.2/3 = 0.733...
        result = calculate_composite_score(0.8, 0.6, pass_weight=2.0, impl_weight=1.0)
        assert result == pytest.approx(2.2 / 3)

    def test_zero_weights(self) -> None:
        """Test Zero weights."""
        # Zero total weight -> 0
        assert calculate_composite_score(0.8, 0.6, pass_weight=0.0, impl_weight=0.0) == 0.0

    def test_perfect_scores(self) -> None:
        """Test Perfect scores."""
        assert calculate_composite_score(1.0, 1.0) == 1.0

    def test_zero_scores(self) -> None:
        """Test Zero scores."""
        assert calculate_composite_score(0.0, 0.0) == 0.0


class TestAssignLetterGrade:
    """Tests for letter grade assignment using industry-aligned scale."""

    def test_grade_s(self) -> None:
        """S grade requires perfect score (1.0)."""
        assert assign_letter_grade(1.0) == "S"

    def test_grade_a(self) -> None:
        """A grade: >= 0.80 (Excellent - production ready)."""
        assert assign_letter_grade(0.80) == "A"
        assert assign_letter_grade(0.99) == "A"

    def test_grade_b(self) -> None:
        """B grade: >= 0.60 (Good - minor improvements possible)."""
        assert assign_letter_grade(0.60) == "B"
        assert assign_letter_grade(0.79) == "B"

    def test_grade_c(self) -> None:
        """C grade: >= 0.40 (Acceptable - functional with issues)."""
        assert assign_letter_grade(0.40) == "C"
        assert assign_letter_grade(0.59) == "C"

    def test_grade_d(self) -> None:
        """D grade: >= 0.20 (Marginal - significant issues)."""
        assert assign_letter_grade(0.20) == "D"
        assert assign_letter_grade(0.39) == "D"

    def test_grade_f(self) -> None:
        """F grade: < 0.20 (Failing - does not meet requirements)."""
        assert assign_letter_grade(0.19) == "F"
        assert assign_letter_grade(0.0) == "F"


class TestCalculateTierUplift:
    """Tests for tier uplift calculation."""

    def test_positive_uplift(self) -> None:
        """Test Positive uplift."""
        # T1 = 0.8, T0 = 0.5 -> (0.8-0.5)/0.5 = 0.6 (60% improvement)
        assert calculate_tier_uplift(0.8, 0.5) == pytest.approx(0.6)

    def test_no_uplift(self) -> None:
        """Test No uplift."""
        # Same score -> 0% uplift
        assert calculate_tier_uplift(0.5, 0.5) == 0.0

    def test_negative_uplift(self) -> None:
        """Test Negative uplift."""
        # Regression: T1 < T0
        # T1 = 0.4, T0 = 0.5 -> (0.4-0.5)/0.5 = -0.2 (-20%)
        assert calculate_tier_uplift(0.4, 0.5) == pytest.approx(-0.2)

    def test_zero_baseline(self) -> None:
        """Test Zero baseline."""
        # Zero baseline -> 0 (avoid division by zero)
        assert calculate_tier_uplift(0.8, 0.0) == 0.0


class TestCalculateCostDelta:
    """Tests for cost delta calculation."""

    def test_multiple_costs(self) -> None:
        """Test Multiple costs."""
        costs = [0.50, 0.75, 1.25, 0.80]
        # max - min = 1.25 - 0.50 = 0.75
        assert calculate_cost_delta(costs) == pytest.approx(0.75)

    def test_identical_costs(self) -> None:
        """Test Identical costs."""
        costs = [1.0, 1.0, 1.0]
        assert calculate_cost_delta(costs) == 0.0

    def test_single_cost(self) -> None:
        """Test Single cost."""
        costs = [1.0]
        assert calculate_cost_delta(costs) == 0.0

    def test_empty_list(self) -> None:
        """Test Empty list."""
        assert calculate_cost_delta([]) == 0.0


class TestGradingResult:
    """Tests for GradingResult dataclass."""

    def test_dataclass_fields(self) -> None:
        """Test Dataclass fields."""
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
    """Tests for grade_run function using industry-aligned scale."""

    def test_passing_run(self) -> None:
        """Passing run with high weighted score -> A grade."""
        result = grade_run(passed=True, weighted_score=0.9, cost_usd=1.0)
        assert result.pass_rate == 1.0
        assert result.impl_rate == 0.9
        assert result.cost_of_pass == 1.0
        assert result.composite_score == pytest.approx(0.95)
        assert result.letter_grade == "A"  # 0.95 >= 0.80

    def test_failing_run(self) -> None:
        """Failing run with moderate weighted score -> D grade."""
        result = grade_run(passed=False, weighted_score=0.5, cost_usd=1.0)
        assert result.pass_rate == 0.0
        assert result.impl_rate == 0.5
        assert math.isinf(result.cost_of_pass)
        assert result.composite_score == pytest.approx(0.25)
        assert result.letter_grade == "D"  # 0.25 >= 0.20

    def test_mixed_run(self) -> None:
        """Passing run with moderate weighted score -> A grade."""
        result = grade_run(passed=True, weighted_score=0.7, cost_usd=2.0)
        assert result.pass_rate == 1.0
        assert result.impl_rate == 0.7
        assert result.cost_of_pass == 2.0
        assert result.composite_score == pytest.approx(0.85)
        assert result.letter_grade == "A"  # 0.85 >= 0.80
