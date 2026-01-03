"""Tests for statistical calculations.

Python justification: Required for pytest testing framework.
"""

import math

import pytest

from scylla.metrics.statistics import (
    Statistics,
    calculate_all,
    calculate_consistency,
    calculate_mean,
    calculate_median,
    calculate_mode,
    calculate_range,
    calculate_std_dev,
    calculate_variance,
)


class TestCalculateMedian:
    """Tests for median calculation."""

    def test_empty_list(self) -> None:
        assert calculate_median([]) == 0.0

    def test_single_value(self) -> None:
        assert calculate_median([5.0]) == 5.0

    def test_odd_count(self) -> None:
        # 9 values: median is 5th value
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
        assert calculate_median(values) == 5.0

    def test_even_count(self) -> None:
        # 4 values: median is average of 2nd and 3rd
        values = [1.0, 2.0, 3.0, 4.0]
        assert calculate_median(values) == 2.5

    def test_unsorted_input(self) -> None:
        values = [9.0, 1.0, 5.0, 3.0, 7.0]
        assert calculate_median(values) == 5.0

    def test_with_duplicates(self) -> None:
        values = [1.0, 2.0, 2.0, 3.0, 3.0]
        assert calculate_median(values) == 2.0


class TestCalculateMean:
    """Tests for mean calculation."""

    def test_empty_list(self) -> None:
        assert calculate_mean([]) == 0.0

    def test_single_value(self) -> None:
        assert calculate_mean([5.0]) == 5.0

    def test_multiple_values(self) -> None:
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert calculate_mean(values) == 3.0

    def test_with_decimals(self) -> None:
        values = [0.1, 0.2, 0.3]
        assert calculate_mean(values) == pytest.approx(0.2)


class TestCalculateMode:
    """Tests for mode calculation."""

    def test_empty_list(self) -> None:
        assert calculate_mode([]) == 0.0

    def test_single_value(self) -> None:
        assert calculate_mode([5.0]) == 5.0

    def test_clear_mode(self) -> None:
        values = [1.0, 2.0, 2.0, 3.0]
        assert calculate_mode(values) == 2.0

    def test_tie_returns_smallest(self) -> None:
        values = [1.0, 1.0, 2.0, 2.0]
        assert calculate_mode(values) == 1.0

    def test_all_unique(self) -> None:
        values = [1.0, 2.0, 3.0]
        # When all unique, returns smallest
        assert calculate_mode(values) == 1.0


class TestCalculateRange:
    """Tests for range calculation."""

    def test_empty_list(self) -> None:
        assert calculate_range([]) == (0.0, 0.0)

    def test_single_value(self) -> None:
        assert calculate_range([5.0]) == (5.0, 5.0)

    def test_multiple_values(self) -> None:
        values = [3.0, 1.0, 4.0, 1.0, 5.0]
        assert calculate_range(values) == (1.0, 5.0)


class TestCalculateVariance:
    """Tests for variance calculation."""

    def test_empty_list(self) -> None:
        assert calculate_variance([]) == 0.0

    def test_single_value(self) -> None:
        assert calculate_variance([5.0]) == 0.0

    def test_identical_values(self) -> None:
        values = [5.0, 5.0, 5.0]
        assert calculate_variance(values) == 0.0

    def test_known_variance(self) -> None:
        # Values: 2, 4, 6, mean = 4
        # Variance = ((2-4)^2 + (4-4)^2 + (6-4)^2) / 3 = (4+0+4)/3 = 8/3
        values = [2.0, 4.0, 6.0]
        assert calculate_variance(values) == pytest.approx(8.0 / 3)


class TestCalculateStdDev:
    """Tests for standard deviation calculation."""

    def test_empty_list(self) -> None:
        assert calculate_std_dev([]) == 0.0

    def test_single_value(self) -> None:
        assert calculate_std_dev([5.0]) == 0.0

    def test_identical_values(self) -> None:
        values = [5.0, 5.0, 5.0]
        assert calculate_std_dev(values) == 0.0

    def test_known_std_dev(self) -> None:
        # Variance = 8/3, std_dev = sqrt(8/3)
        values = [2.0, 4.0, 6.0]
        expected = math.sqrt(8.0 / 3)
        assert calculate_std_dev(values) == pytest.approx(expected)


class TestCalculateConsistency:
    """Tests for consistency calculation.

    Consistency = 1 - (std_dev / mean)
    - 1.0 = perfectly consistent (no variance)
    - 0.0 = highly inconsistent (std_dev >= mean)
    """

    def test_empty_list(self) -> None:
        assert calculate_consistency([]) == 0.0

    def test_single_value(self) -> None:
        assert calculate_consistency([5.0]) == 0.0

    def test_identical_values(self) -> None:
        """All identical values = perfect consistency."""
        values = [0.8, 0.8, 0.8, 0.8, 0.8]
        assert calculate_consistency(values) == 1.0

    def test_all_zeros(self) -> None:
        """All zeros = perfect consistency at zero."""
        values = [0.0, 0.0, 0.0]
        assert calculate_consistency(values) == 1.0

    def test_low_variance(self) -> None:
        """Low variance = high consistency."""
        values = [0.79, 0.80, 0.81, 0.80, 0.80]
        consistency = calculate_consistency(values)
        assert consistency > 0.95  # Should be very high

    def test_high_variance(self) -> None:
        """High variance = low consistency."""
        values = [0.1, 0.5, 0.9]  # Wide spread
        consistency = calculate_consistency(values)
        assert consistency < 0.5  # Should be lower

    def test_consistency_bounds(self) -> None:
        """Consistency should be clamped to [0.0, 1.0]."""
        # Extreme variance case
        values = [0.01, 1.0, 0.01, 1.0]
        consistency = calculate_consistency(values)
        assert 0.0 <= consistency <= 1.0

    def test_typical_evaluation_scenario(self) -> None:
        """Test with typical 10-run evaluation results."""
        # Pass rates from 10 runs with some variance
        values = [1.0, 1.0, 0.0, 1.0, 1.0, 1.0, 0.0, 1.0, 1.0, 1.0]
        consistency = calculate_consistency(values)
        # 80% pass rate with 20% variance
        assert 0.4 < consistency < 0.8


class TestStatistics:
    """Tests for Statistics dataclass."""

    def test_dataclass_fields(self) -> None:
        stats = Statistics(
            median=5.0,
            mean=4.5,
            mode=4.0,
            min=1.0,
            max=9.0,
            std_dev=2.5,
            count=9,
        )
        assert stats.median == 5.0
        assert stats.mean == 4.5
        assert stats.mode == 4.0
        assert stats.min == 1.0
        assert stats.max == 9.0
        assert stats.std_dev == 2.5
        assert stats.count == 9


class TestCalculateAll:
    """Tests for calculate_all function."""

    def test_empty_list(self) -> None:
        stats = calculate_all([])
        assert stats.median == 0.0
        assert stats.mean == 0.0
        assert stats.mode == 0.0
        assert stats.min == 0.0
        assert stats.max == 0.0
        assert stats.std_dev == 0.0
        assert stats.count == 0

    def test_single_value(self) -> None:
        stats = calculate_all([5.0])
        assert stats.median == 5.0
        assert stats.mean == 5.0
        assert stats.mode == 5.0
        assert stats.min == 5.0
        assert stats.max == 5.0
        assert stats.std_dev == 0.0
        assert stats.count == 1

    def test_nine_runs(self) -> None:
        """Test with 9 runs (typical evaluation scenario)."""
        values = [0.7, 0.8, 0.75, 0.85, 0.8, 0.9, 0.8, 0.85, 0.82]
        stats = calculate_all(values)

        assert stats.count == 9
        assert stats.median == 0.8  # 5th value when sorted
        assert stats.mean == pytest.approx(sum(values) / 9)
        assert stats.min == 0.7
        assert stats.max == 0.9
        assert stats.std_dev >= 0

    def test_ten_runs(self) -> None:
        """Test with 10 runs (updated evaluation scenario)."""
        values = [0.7, 0.8, 0.75, 0.85, 0.8, 0.9, 0.8, 0.85, 0.82, 0.88]
        stats = calculate_all(values)

        assert stats.count == 10
        assert stats.min == 0.7
        assert stats.max == 0.9

    def test_consistent_scores(self) -> None:
        """Test with identical scores (low variance)."""
        values = [0.8, 0.8, 0.8, 0.8, 0.8]
        stats = calculate_all(values)

        assert stats.median == 0.8
        assert stats.mean == 0.8
        assert stats.mode == 0.8
        assert stats.std_dev == 0.0

    def test_high_variance(self) -> None:
        """Test with high variance scores."""
        values = [0.1, 0.5, 0.9]
        stats = calculate_all(values)

        assert stats.min == 0.1
        assert stats.max == 0.9
        assert stats.std_dev > 0.3
