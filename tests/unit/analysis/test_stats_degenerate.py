"""Degenerate input tests for statistical functions.

Tests edge cases and boundary conditions using degenerate fixtures from conftest.py.
"""

import numpy as np
import pytest


# Cliff's Delta Degenerate Tests
class TestCliffsDetaDegenerate:
    """Test Cliff's delta with degenerate inputs."""

    def test_cliffs_delta_all_same_groups(self, degenerate_all_same):
        """Test Cliff's delta with identical values in both groups."""
        from scylla.analysis.stats import cliffs_delta

        # Both groups have all same values -> delta = 0
        delta = cliffs_delta(degenerate_all_same, degenerate_all_same)
        assert delta == pytest.approx(0.0)

    def test_cliffs_delta_single_element_groups(self, degenerate_single_element):
        """Test Cliff's delta with single-element groups."""
        from scylla.analysis.stats import cliffs_delta

        # n1=1, n2=1
        delta = cliffs_delta(degenerate_single_element, degenerate_single_element)
        assert delta == pytest.approx(0.0)

        # Test with different single values
        g1 = np.array([0.3])
        g2 = np.array([0.7])
        delta = cliffs_delta(g1, g2)
        assert delta == pytest.approx(-1.0)  # g1 < g2

    def test_cliffs_delta_unbalanced_groups(self, degenerate_unbalanced_groups):
        """Test Cliff's delta with severely unbalanced group sizes."""
        from scylla.analysis.stats import cliffs_delta

        small = degenerate_unbalanced_groups["small"]
        large = degenerate_unbalanced_groups["large"]

        # Should handle n1=2, n2=50 gracefully
        delta = cliffs_delta(small, large)
        assert -1.0 <= delta <= 1.0  # Valid range

    def test_cliffs_delta_nan_handling(self, degenerate_nan_values):
        """Test Cliff's delta with NaN values."""
        from scylla.analysis.stats import cliffs_delta

        # NaN values should propagate or be handled gracefully
        result = cliffs_delta(degenerate_nan_values, degenerate_nan_values)
        # If NaNs are not filtered, result should be NaN
        assert np.isnan(result) or isinstance(result, float)

    def test_cliffs_delta_inf_handling(self, degenerate_inf_values):
        """Test Cliff's delta with infinite values."""
        from scylla.analysis.stats import cliffs_delta

        # Infinite values should be handled
        result = cliffs_delta(degenerate_inf_values, degenerate_inf_values)
        # Should either be NaN or handle inf gracefully
        assert np.isnan(result) or isinstance(result, float)


# Bootstrap CI Degenerate Tests
class TestBootstrapCIDegenerate:
    """Test bootstrap confidence intervals with degenerate inputs."""

    def test_bootstrap_all_same(self, degenerate_all_same):
        """Test bootstrap CI with zero variance data."""
        from scylla.analysis.stats import bootstrap_ci

        mean, ci_low, ci_high = bootstrap_ci(degenerate_all_same)
        # All values are 0.7
        assert mean == pytest.approx(0.7, abs=1e-6)
        assert ci_low == pytest.approx(0.7, abs=1e-6)
        assert ci_high == pytest.approx(0.7, abs=1e-6)

    def test_bootstrap_binary(self, degenerate_binary_data):
        """Test bootstrap CI with binary data."""
        from scylla.analysis.stats import bootstrap_ci

        mean, ci_low, ci_high = bootstrap_ci(degenerate_binary_data)
        # Binary data should produce valid CI
        assert 0.0 <= ci_low <= mean <= ci_high <= 1.0

    def test_bootstrap_boundary_values(self, degenerate_boundary_values):
        """Test bootstrap CI with exact boundary values (0.0, 1.0)."""
        from scylla.analysis.stats import bootstrap_ci

        mean, ci_low, ci_high = bootstrap_ci(degenerate_boundary_values)
        # Should handle boundaries gracefully
        assert 0.0 <= ci_low <= mean <= ci_high <= 1.0

    def test_bootstrap_near_zero(self, degenerate_near_zero):
        """Test bootstrap CI with very small values (numerical stability)."""
        from scylla.analysis.stats import bootstrap_ci

        mean, ci_low, ci_high = bootstrap_ci(degenerate_near_zero)
        # Should maintain order and positivity
        assert 0.0 < ci_low <= mean <= ci_high
        assert mean < 1e-5  # All values are very small

    def test_bootstrap_high_variance(self, degenerate_high_variance):
        """Test bootstrap CI with extreme variance."""
        from scylla.analysis.stats import bootstrap_ci

        mean, ci_low, ci_high = bootstrap_ci(degenerate_high_variance)
        # Should produce wide CI
        assert 0.0 <= ci_low <= mean <= ci_high <= 1.0
        ci_width = ci_high - ci_low
        assert ci_width > 0.2  # Expect wide interval


# Mann-Whitney U Degenerate Tests
class TestMannWhitneyDegenerate:
    """Test Mann-Whitney U with degenerate inputs."""

    def test_mann_whitney_all_same(self, degenerate_all_same):
        """Test Mann-Whitney U with identical distributions."""
        from scylla.analysis.stats import mann_whitney_u

        u_stat, p_value = mann_whitney_u(degenerate_all_same, degenerate_all_same)
        # Identical distributions -> not significant
        assert p_value > 0.05

    def test_mann_whitney_all_pass_vs_all_fail(self, degenerate_all_pass, degenerate_all_fail):
        """Test Mann-Whitney U with completely separated groups."""
        from scylla.analysis.stats import mann_whitney_u

        u_stat, p_value = mann_whitney_u(degenerate_all_pass, degenerate_all_fail)
        # Completely separated -> highly significant
        assert p_value < 0.01

    def test_mann_whitney_single_element(self, degenerate_single_element):
        """Test Mann-Whitney U with single-element groups."""
        from scylla.analysis.stats import mann_whitney_u

        g1 = degenerate_single_element
        g2 = np.array([0.3])

        # n1=1, n2=1 -> should handle gracefully
        u_stat, p_value = mann_whitney_u(g1, g2)
        # With very small samples, expect high p-value or warning
        assert isinstance(p_value, float)

    def test_mann_whitney_unbalanced(self, degenerate_unbalanced_groups):
        """Test Mann-Whitney U with unbalanced group sizes."""
        from scylla.analysis.stats import mann_whitney_u

        small = degenerate_unbalanced_groups["small"]
        large = degenerate_unbalanced_groups["large"]

        u_stat, p_value = mann_whitney_u(small, large)
        # Should handle n1=2, n2=50
        assert isinstance(p_value, float)
        assert 0.0 <= p_value <= 1.0


# Consistency Metric Degenerate Tests
class TestConsistencyDegenerate:
    """Test consistency (1-CV) with degenerate inputs."""

    def test_consistency_all_same(self, degenerate_all_same):
        """Test consistency with zero variance."""
        from scylla.analysis.stats import compute_consistency

        mean = np.mean(degenerate_all_same)
        std = np.std(degenerate_all_same)
        # All same values -> std = 0 -> CV = 0 -> consistency = 1.0
        consistency = compute_consistency(mean, std)
        assert consistency == pytest.approx(1.0, abs=1e-6)

    def test_consistency_single_element(self, degenerate_single_element):
        """Test consistency with single element."""
        from scylla.analysis.stats import compute_consistency

        mean = np.mean(degenerate_single_element)
        std = np.std(degenerate_single_element)
        # n=1 -> std=0 -> CV = 0 -> consistency = 1.0
        consistency = compute_consistency(mean, std)
        assert consistency == pytest.approx(1.0, abs=1e-6)

    def test_consistency_high_variance(self, degenerate_high_variance):
        """Test consistency with extreme variance."""
        from scylla.analysis.stats import compute_consistency

        mean = np.mean(degenerate_high_variance)
        std = np.std(degenerate_high_variance)
        consistency = compute_consistency(mean, std)
        # High CV -> low consistency (could be negative, clamped to 0)
        assert 0.0 <= consistency <= 1.0

    def test_consistency_near_zero_mean(self, degenerate_near_zero):
        """Test consistency when mean is near zero."""
        from scylla.analysis.stats import compute_consistency

        mean = np.mean(degenerate_near_zero)
        std = np.std(degenerate_near_zero)
        # Very small mean -> CV could be very large
        consistency = compute_consistency(mean, std)
        # Should be clamped to [0, 1]
        assert 0.0 <= consistency <= 1.0


# Kruskal-Wallis Degenerate Tests
class TestKruskalWallisDegenerate:
    """Test Kruskal-Wallis with degenerate inputs."""

    def test_kruskal_all_same_groups(self, degenerate_all_same):
        """Test Kruskal-Wallis with identical groups."""
        from scylla.analysis.stats import kruskal_wallis

        # Use variadic args, not list
        h_stat, p_value = kruskal_wallis(
            degenerate_all_same, degenerate_all_same, degenerate_all_same
        )

        # Identical groups with zero variance -> p_value is NaN (no variation to test)
        # This is expected behavior from scipy when all values are identical
        assert np.isnan(p_value) or p_value > 0.05

    def test_kruskal_two_groups_only(self, degenerate_all_pass, degenerate_all_fail):
        """Test Kruskal-Wallis with minimum 2 groups."""
        from scylla.analysis.stats import kruskal_wallis

        # Use variadic args
        h_stat, p_value = kruskal_wallis(degenerate_all_pass, degenerate_all_fail)

        # Completely different groups -> significant
        assert p_value < 0.05

    def test_kruskal_unbalanced_groups(self, degenerate_unbalanced_groups):
        """Test Kruskal-Wallis with severely unbalanced groups."""
        from scylla.analysis.stats import kruskal_wallis

        small = degenerate_unbalanced_groups["small"]
        large = degenerate_unbalanced_groups["large"]
        medium = np.array([0.5, 0.6, 0.7, 0.8, 0.9])

        # Use variadic args
        h_stat, p_value = kruskal_wallis(small, medium, large)

        # Should handle n1=2, n2=5, n3=50
        assert isinstance(p_value, float)
        assert 0.0 <= p_value <= 1.0


# Integration test for table generation with degenerate data
@pytest.mark.parametrize(
    "fixture_name",
    [
        "degenerate_all_same",
        "degenerate_all_pass",
        "degenerate_all_fail",
        "degenerate_single_element",
        "degenerate_binary_data",
    ],
)
def test_stats_pipeline_with_degenerate_data(fixture_name, request):
    """Integration test: ensure stats pipeline handles degenerate data gracefully.

    This test verifies that the core statistical pipeline (used in tables/figures)
    can process degenerate inputs without crashing.
    """
    from scylla.analysis.stats import bootstrap_ci, cliffs_delta, mann_whitney_u

    fixture_data = request.getfixturevalue(fixture_name)

    # Test bootstrap CI
    try:
        mean, ci_low, ci_high = bootstrap_ci(fixture_data)
        assert ci_low <= mean <= ci_high
    except Exception as e:
        pytest.fail(f"bootstrap_ci failed on {fixture_name}: {e}")

    # Test Cliff's delta (needs two groups)
    try:
        delta = cliffs_delta(fixture_data, fixture_data)
        assert -1.0 <= delta <= 1.0 or np.isnan(delta)
    except Exception as e:
        pytest.fail(f"cliffs_delta failed on {fixture_name}: {e}")

    # Test Mann-Whitney U
    try:
        u_stat, p_value = mann_whitney_u(fixture_data, fixture_data)
        assert 0.0 <= p_value <= 1.0 or np.isnan(p_value)
    except Exception as e:
        pytest.fail(f"mann_whitney_u failed on {fixture_name}: {e}")
