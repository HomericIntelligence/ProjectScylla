"""Parametrized tests for statistical functions.

Tests statistical functions systematically across multiple input combinations.
Complements test_stats.py with broader coverage using pytest.mark.parametrize.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


class TestCliffsDeltaParametrized:
    """Parametrized tests for Cliff's delta effect size."""

    @pytest.mark.parametrize(
        "g1,g2,expected_delta",
        [
            # Complete separation (positive)
            ([7, 8, 9], [1, 2, 3], 1.0),
            ([10, 11, 12], [1, 2, 3], 1.0),
            # Complete separation (negative)
            ([1, 2, 3], [7, 8, 9], -1.0),
            ([1, 2, 3], [10, 11, 12], -1.0),
            # Identical groups
            ([1, 2, 3, 4, 5], [1, 2, 3, 4, 5], 0.0),
            ([10.0, 20.0, 30.0], [10.0, 20.0, 30.0], 0.0),
            # Partial overlap: g1=[5,6,7], g2=[3,4,5]
            # 5 > [3,4] = 2; 6 > [3,4,5] = 3; 7 > [3,4,5] = 3
            # Total greater = 8, delta = 8/9
            ([5, 6, 7], [3, 4, 5], 8 / 9),
            # Single element groups
            ([10], [5], 1.0),
            ([5], [10], -1.0),
            ([5], [5], 0.0),
        ],
        ids=[
            "complete_sep_pos_1",
            "complete_sep_pos_2",
            "complete_sep_neg_1",
            "complete_sep_neg_2",
            "identical_1",
            "identical_2",
            "partial_overlap",
            "single_gt",
            "single_lt",
            "single_eq",
        ],
    )
    def test_cliffs_delta_values(self, g1, g2, expected_delta):
        """Test Cliff's delta with various input combinations."""
        from scylla.analysis.stats import cliffs_delta

        delta = cliffs_delta(g1, g2)
        assert delta == pytest.approx(expected_delta, abs=1e-6)

    @pytest.mark.parametrize(
        "g1,g2",
        [
            ([], [1, 2, 3]),
            ([1, 2, 3], []),
            ([], []),
            (pd.Series([]), pd.Series([1, 2, 3])),
        ],
        ids=["empty_g1", "empty_g2", "both_empty", "pandas_empty"],
    )
    def test_cliffs_delta_empty_groups(self, g1, g2):
        """Test Cliff's delta returns NaN for empty groups."""
        from scylla.analysis.stats import cliffs_delta

        delta = cliffs_delta(g1, g2)
        assert np.isnan(delta)

    @pytest.mark.parametrize(
        "g1,g2",
        [
            (pd.Series([5, 6, 7]), pd.Series([1, 2, 3])),
            (pd.Series([1, 2, 3]), pd.Series([5, 6, 7])),
            (np.array([5, 6, 7]), np.array([1, 2, 3])),
        ],
        ids=["pandas_pos", "pandas_neg", "numpy"],
    )
    def test_cliffs_delta_input_types(self, g1, g2):
        """Test Cliff's delta works with different input types."""
        from scylla.analysis.stats import cliffs_delta

        delta = cliffs_delta(g1, g2)
        assert not np.isnan(delta)
        assert -1.0 <= delta <= 1.0


class TestBootstrapCIParametrized:
    """Parametrized tests for bootstrap confidence intervals."""

    @pytest.mark.parametrize(
        "data,expected_mean",
        [
            ([1, 2, 3, 4, 5], 3.0),
            ([10, 20, 30, 40, 50], 30.0),
            ([0.1, 0.2, 0.3, 0.4, 0.5], 0.3),
            (np.array([1.0, 2.0, 3.0]), 2.0),
            (pd.Series([5.0, 10.0, 15.0]), 10.0),
        ],
        ids=["int_1-5", "int_10-50", "float_decimals", "numpy", "pandas"],
    )
    def test_bootstrap_ci_mean(self, data, expected_mean):
        """Test bootstrap CI computes correct mean."""
        from scylla.analysis.stats import bootstrap_ci

        mean, ci_low, ci_high = bootstrap_ci(data)
        assert mean == pytest.approx(expected_mean, abs=1e-6)

    @pytest.mark.parametrize(
        "data",
        [
            [1, 2, 3, 4, 5],
            [10, 20, 30],
            [0.1, 0.2, 0.3, 0.4],
        ],
        ids=["5_elements", "3_elements", "4_elements"],
    )
    def test_bootstrap_ci_bounds(self, data):
        """Test bootstrap CI bounds satisfy ci_low <= mean <= ci_high."""
        from scylla.analysis.stats import bootstrap_ci

        mean, ci_low, ci_high = bootstrap_ci(data)
        assert ci_low <= mean <= ci_high

    @pytest.mark.parametrize(
        "data,expected",
        [
            ([5.0], (5.0, 5.0, 5.0)),
            ([0.0], (0.0, 0.0, 0.0)),
            ([7.0, 7.0, 7.0], (7.0, 7.0, 7.0)),  # Zero variance
        ],
        ids=["single_element", "single_zero", "zero_variance"],
    )
    def test_bootstrap_ci_degenerate(self, data, expected):
        """Test bootstrap CI with degenerate inputs (zero variance)."""
        from scylla.analysis.stats import bootstrap_ci

        mean, ci_low, ci_high = bootstrap_ci(data)
        exp_mean, exp_low, exp_high = expected
        assert mean == pytest.approx(exp_mean, abs=1e-6)
        assert ci_low == pytest.approx(exp_low, abs=1e-6)
        assert ci_high == pytest.approx(exp_high, abs=1e-6)


class TestMannWhitneyUParametrized:
    """Parametrized tests for Mann-Whitney U test."""

    @pytest.mark.parametrize(
        "g1,g2,expect_significant",
        [
            # Use larger samples for more reliable p-values
            ([1, 2, 3, 4, 5], [10, 11, 12, 13, 14], True),  # Clearly different
            ([1, 2, 3, 4, 5], [1, 2, 3, 4, 5], False),  # Identical
            ([1, 2, 3, 4, 5], [2, 3, 4, 5, 6], False),  # Overlap
        ],
        ids=["clearly_different", "identical", "overlap"],
    )
    def test_mann_whitney_significance(self, g1, g2, expect_significant):
        """Test Mann-Whitney U significance detection."""
        from scylla.analysis.stats import mann_whitney_u

        u_stat, p_value = mann_whitney_u(g1, g2)
        if expect_significant:
            assert p_value < 0.05
        else:
            assert p_value >= 0.05

    @pytest.mark.parametrize(
        "g1,g2",
        [
            ([1], [2, 3, 4]),
            ([1, 2], [3]),
            ([], [1, 2, 3]),
            ([1, 2, 3], []),
        ],
        ids=["single_g1", "single_g2", "empty_g1", "empty_g2"],
    )
    def test_mann_whitney_degenerate_safe_defaults(self, g1, g2):
        """Test Mann-Whitney U returns safe defaults for degenerate input."""
        from scylla.analysis.stats import mann_whitney_u

        u_stat, p_value = mann_whitney_u(g1, g2)
        # Should return (0.0, 1.0) for insufficient data
        assert u_stat == pytest.approx(0.0)
        assert p_value == pytest.approx(1.0)


class TestConsistencyParametrized:
    """Parametrized tests for consistency metric (1 - CV)."""

    @pytest.mark.parametrize(
        "mean_score,std_score,expected_consistency",
        [
            (10.0, 0.0, 1.0),  # Zero variance = perfect consistency
            (10.0, 1.0, 0.9),  # CV = 0.1, consistency = 0.9
            (10.0, 2.0, 0.8),  # CV = 0.2, consistency = 0.8
            (10.0, 5.0, 0.5),  # CV = 0.5, consistency = 0.5
            (10.0, 10.0, 0.0),  # CV = 1.0, consistency = 0.0
        ],
        ids=["zero_variance", "cv_0.1", "cv_0.2", "cv_0.5", "cv_1.0"],
    )
    def test_consistency_values(self, mean_score, std_score, expected_consistency):
        """Test consistency calculation with known values."""
        from scylla.analysis.stats import compute_consistency

        consistency = compute_consistency(mean_score, std_score)
        assert consistency == pytest.approx(expected_consistency, abs=1e-6)

    @pytest.mark.parametrize(
        "mean_score,std_score,expected",
        [
            (0.0, 0.0, 0.0),  # Division by zero -> 0.0
            (0.0, 1.0, 0.0),  # Zero mean -> 0.0
        ],
        ids=["zero_mean_zero_std", "zero_mean_nonzero_std"],
    )
    def test_consistency_edge_cases(self, mean_score, std_score, expected):
        """Test consistency with edge cases."""
        from scylla.analysis.stats import compute_consistency

        consistency = compute_consistency(mean_score, std_score)
        assert consistency == pytest.approx(expected, abs=1e-6)


class TestCostOfPassParametrized:
    """Parametrized tests for Cost-of-Pass metric."""

    @pytest.mark.parametrize(
        "mean_cost,pass_rate,expected_cop",
        [
            (1.0, 1.0, 1.0),  # Perfect pass rate
            (2.0, 0.5, 4.0),  # 50% pass rate
            (10.0, 0.25, 40.0),  # 25% pass rate
            (5.0, 0.1, 50.0),  # 10% pass rate
        ],
        ids=["perfect_pass", "half_pass", "quarter_pass", "tenth_pass"],
    )
    def test_cop_values(self, mean_cost, pass_rate, expected_cop):
        """Test CoP calculation with known values."""
        from scylla.analysis.stats import compute_cop

        cop = compute_cop(mean_cost, pass_rate)
        assert cop == pytest.approx(expected_cop, abs=1e-6)

    @pytest.mark.parametrize(
        "mean_cost,pass_rate",
        [
            (1.0, 0.0),
            (10.0, 0.0),
            (0.0, 0.0),
        ],
        ids=["zero_pass_nonzero_cost", "zero_pass_high_cost", "zero_both"],
    )
    def test_cop_zero_pass_rate(self, mean_cost, pass_rate):
        """Test CoP returns infinity for zero pass rate."""
        from scylla.analysis.stats import compute_cop

        cop = compute_cop(mean_cost, pass_rate)
        assert np.isinf(cop)


class TestHolmBonferroniParametrized:
    """Parametrized tests for Holm-Bonferroni correction."""

    @pytest.mark.parametrize(
        "p_values,expected_rejections",
        [
            # Holm-Bonferroni is step-down: stops at first non-rejection
            # [0.001, 0.01, 0.03, 0.04] -> corrected [0.004, 0.03, 0.06, 0.06]
            ([0.001, 0.01, 0.03, 0.04], [True, True, False, False]),
            # [0.001, 0.02, 0.03, 0.04] -> corrected [0.004, 0.06, 0.06, 0.06]
            ([0.001, 0.02, 0.03, 0.04], [True, False, False, False]),
            ([0.06, 0.07, 0.08], [False, False, False]),
            ([0.001], [True]),
            ([0.1], [False]),
        ],
        ids=[
            "step_down_stops_at_third",
            "step_down_stops_at_second",
            "none_significant",
            "single_significant",
            "single_not_significant",
        ],
    )
    def test_holm_bonferroni_rejections(self, p_values, expected_rejections):
        """Test Holm-Bonferroni correction rejection pattern (alpha=0.05)."""
        from scylla.analysis.stats import holm_bonferroni_correction

        alpha = 0.05
        corrected = holm_bonferroni_correction(p_values)

        # Check which hypotheses are rejected (p_corrected < alpha)
        rejections = [p < alpha for p in corrected]
        assert rejections == expected_rejections

    @pytest.mark.parametrize(
        "p_values",
        [
            [0.01, 0.02, 0.03],
            [0.05, 0.04, 0.03, 0.02, 0.01],
        ],
        ids=["ascending", "descending"],
    )
    def test_holm_bonferroni_monotonicity(self, p_values):
        """Test corrected p-values are monotonically increasing."""
        from scylla.analysis.stats import holm_bonferroni_correction

        corrected = holm_bonferroni_correction(p_values)

        # Corrected p-values should be monotonically increasing (after sorting)
        sorted_corrected = sorted(corrected)
        for i in range(len(sorted_corrected) - 1):
            assert sorted_corrected[i] <= sorted_corrected[i + 1]


class TestImplRateParametrized:
    """Parametrized tests for implementation rate calculation."""

    @pytest.mark.parametrize(
        "achieved,max_points,expected_rate",
        [
            (10.0, 10.0, 1.0),  # Perfect
            (5.0, 10.0, 0.5),  # Half
            (7.5, 10.0, 0.75),  # Three quarters
            (0.0, 10.0, 0.0),  # Zero
            (10.0, 20.0, 0.5),  # Different scale
        ],
        ids=["perfect", "half", "three_quarters", "zero", "different_scale"],
    )
    def test_impl_rate_values(self, achieved, max_points, expected_rate):
        """Test implementation rate calculation."""
        from scylla.analysis.stats import compute_impl_rate

        rate = compute_impl_rate(achieved, max_points)
        assert rate == pytest.approx(expected_rate, abs=1e-6)

    @pytest.mark.parametrize(
        "achieved,max_points",
        [
            (0.0, 0.0),  # Division by zero -> NaN
            (5.0, 0.0),  # Division by zero -> NaN
        ],
        ids=["zero_both", "zero_max"],
    )
    def test_impl_rate_edge_cases(self, achieved, max_points):
        """Test implementation rate edge cases (division by zero)."""
        from scylla.analysis.stats import compute_impl_rate

        rate = compute_impl_rate(achieved, max_points)
        # Should return NaN for division by zero
        assert np.isnan(rate)
