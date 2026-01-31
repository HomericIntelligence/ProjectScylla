"""Unit tests for statistical functions."""

import numpy as np
import pandas as pd


def test_cliffs_delta_basic():
    """Test Cliff's delta with known values."""
    # Group 1 has higher values than Group 2
    g1 = [5, 6, 7, 8, 9]
    g2 = [1, 2, 3, 4, 5]

    from scylla.analysis.stats import cliffs_delta

    delta = cliffs_delta(g1, g2)

    # All 5 values in g1 are >= all 5 values in g2
    # Only ties: g1[0]=5 == g2[4]=5 (count=0)
    # Greater: 5 pairs where g1[i] > g2[j] for each g1[i] except g1[0]=5 vs g2[4]=5
    # Actually: g1=[5,6,7,8,9], g2=[1,2,3,4,5]
    # 5 > [1,2,3,4] = 4, 6 > [1,2,3,4,5] = 5, 7 > all = 5, 8 > all = 5, 9 > all = 5
    # Total greater = 4 + 5 + 5 + 5 + 5 = 24
    # Less = 0, Equal = 1 (5 vs 5)
    # delta = (24 - 0) / 25 = 0.96
    expected = 24 / 25
    assert abs(delta - expected) < 1e-6


def test_cliffs_delta_identical():
    """Test Cliff's delta with identical groups (delta should be 0)."""
    from scylla.analysis.stats import cliffs_delta

    g1 = [1, 2, 3, 4, 5]
    g2 = [1, 2, 3, 4, 5]

    delta = cliffs_delta(g1, g2)
    assert abs(delta) < 1e-6


def test_cliffs_delta_negative():
    """Test Cliff's delta when group2 dominates group1."""
    from scylla.analysis.stats import cliffs_delta

    g1 = [1, 2, 3]
    g2 = [7, 8, 9]

    delta = cliffs_delta(g1, g2)

    # All g1 values < all g2 values: -1.0
    assert abs(delta - (-1.0)) < 1e-6


def test_cliffs_delta_empty():
    """Test Cliff's delta with empty groups."""
    from scylla.analysis.stats import cliffs_delta

    assert cliffs_delta([], [1, 2, 3]) == 0.0
    assert cliffs_delta([1, 2, 3], []) == 0.0
    assert cliffs_delta([], []) == 0.0


def test_cliffs_delta_pandas_series():
    """Test Cliff's delta with pandas Series input."""
    from scylla.analysis.stats import cliffs_delta

    g1 = pd.Series([5, 6, 7])
    g2 = pd.Series([1, 2, 3])

    delta = cliffs_delta(g1, g2)

    # All g1 > all g2: delta = 1.0
    assert abs(delta - 1.0) < 1e-6


def test_cliffs_delta_reference():
    """Test Cliff's delta against hand-calculated reference.

    Reference implementation (O(n²) loops):
    dominance = 0
    for x in g1:
        for y in g2:
            if x > y: dominance += 1
            elif x < y: dominance -= 1
    delta = dominance / (n1 * n2)
    """
    from scylla.analysis.stats import cliffs_delta

    g1 = np.array([3.2, 4.1, 5.5, 2.9])
    g2 = np.array([2.1, 3.8, 4.9])

    # Hand calculation:
    # 3.2 > [2.1] = +1, 3.2 < [3.8, 4.9] = -2 → sum = -1
    # 4.1 > [2.1, 3.8] = +2, 4.1 < [4.9] = -1 → sum = +1
    # 5.5 > [2.1, 3.8, 4.9] = +3 → sum = +3
    # 2.9 > [2.1] = +1, 2.9 < [3.8, 4.9] = -2 → sum = -1
    # Total = -1 + 1 + 3 - 1 = 2
    # delta = 2 / (4 * 3) = 2/12 = 0.1667
    expected = 2 / 12

    delta = cliffs_delta(g1, g2)
    assert abs(delta - expected) < 1e-6


def test_bootstrap_ci_deterministic():
    """Test bootstrap CI is deterministic with fixed random state."""
    from scylla.analysis.stats import bootstrap_ci

    data = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])

    mean1, lower1, upper1 = bootstrap_ci(data, n_resamples=1000)
    mean2, lower2, upper2 = bootstrap_ci(data, n_resamples=1000)

    # Should be identical due to random_state=42 in implementation
    assert mean1 == mean2
    assert lower1 == lower2
    assert upper1 == upper2


def test_mann_whitney_u_basic():
    """Test Mann-Whitney U returns reasonable values."""
    from scylla.analysis.stats import mann_whitney_u

    # Clearly different groups
    g1 = [1, 2, 3, 4, 5]
    g2 = [6, 7, 8, 9, 10]

    u_stat, p_value = mann_whitney_u(g1, g2)

    # Groups are completely separated, expect very small p-value
    assert p_value < 0.01
    assert u_stat >= 0


def test_mann_whitney_u_identical():
    """Test Mann-Whitney U with identical groups."""
    from scylla.analysis.stats import mann_whitney_u

    g1 = [1, 2, 3, 4, 5]
    g2 = [1, 2, 3, 4, 5]

    u_stat, p_value = mann_whitney_u(g1, g2)

    # Identical groups should have high p-value (no significant difference)
    assert p_value > 0.9


def test_krippendorff_alpha_perfect_agreement():
    """Test Krippendorff's alpha with perfect inter-rater agreement."""
    from scylla.analysis.stats import krippendorff_alpha

    # 3 judges, 5 items, all agree on varied scores
    ratings = np.array(
        [
            [0.2, 0.4, 0.6, 0.8, 1.0],  # Judge 1
            [0.2, 0.4, 0.6, 0.8, 1.0],  # Judge 2
            [0.2, 0.4, 0.6, 0.8, 1.0],  # Judge 3
        ]
    )

    alpha = krippendorff_alpha(ratings, level="interval")

    # Perfect agreement should give alpha = 1.0
    assert abs(alpha - 1.0) < 1e-6


def test_krippendorff_alpha_ordinal():
    """Test Krippendorff's alpha with ordinal data."""
    from scylla.analysis.stats import krippendorff_alpha

    # 2 judges, 4 items
    ratings = np.array(
        [
            [1, 2, 3, 4],  # Judge 1
            [1, 2, 3, 3],  # Judge 2 (slight disagreement on last item)
        ]
    )

    alpha = krippendorff_alpha(ratings, level="ordinal")

    # Should have high but not perfect agreement
    assert 0.7 < alpha < 1.0


def test_krippendorff_alpha_nominal():
    """Test Krippendorff's alpha with nominal data."""
    from scylla.analysis.stats import krippendorff_alpha

    # 3 judges, 6 items, categorical ratings
    ratings = np.array(
        [
            [1, 2, 1, 2, 1, 2],  # Judge 1
            [1, 2, 1, 2, 1, 2],  # Judge 2
            [1, 2, 1, 2, 1, 1],  # Judge 3 (disagrees on last item)
        ]
    )

    alpha = krippendorff_alpha(ratings, level="nominal")

    # Should have high agreement
    assert 0.6 < alpha < 1.0


def test_bonferroni_correction():
    """Test Bonferroni correction for multiple comparisons."""
    from scylla.analysis.stats import bonferroni_correction

    # Test basic correction
    assert bonferroni_correction(0.01, 5) == 0.05
    assert bonferroni_correction(0.02, 10) == 0.20

    # Test clamping to 1.0
    assert bonferroni_correction(0.5, 3) == 1.0
    assert bonferroni_correction(1.0, 2) == 1.0


def test_compute_consistency():
    """Test consistency metric (1 - CV)."""
    from scylla.analysis.stats import compute_consistency

    # Perfect consistency (no variation)
    assert compute_consistency(10.0, 0.0) == 1.0

    # High variation
    assert compute_consistency(10.0, 10.0) == 0.0

    # Moderate variation
    consistency = compute_consistency(10.0, 2.0)
    assert 0.7 < consistency < 0.9

    # Zero mean (edge case)
    assert compute_consistency(0.0, 5.0) == 0.0

    # Negative consistency should be clamped to 0
    consistency = compute_consistency(5.0, 10.0)  # std > mean
    assert consistency == 0.0


def test_compute_cop():
    """Test Cost-of-Pass metric."""
    from scylla.analysis.stats import compute_cop

    # Basic calculation
    cop = compute_cop(1.0, 0.5)
    assert abs(cop - 2.0) < 1e-6

    # High pass rate
    cop = compute_cop(1.0, 0.9)
    assert abs(cop - (1.0 / 0.9)) < 1e-6

    # Zero pass rate (edge case)
    cop = compute_cop(1.0, 0.0)
    assert cop == float("inf")


def test_spearman_correlation():
    """Test Spearman rank correlation."""
    from scylla.analysis.stats import spearman_correlation

    # Perfect positive correlation
    x = [1, 2, 3, 4, 5]
    y = [2, 4, 6, 8, 10]
    corr, p_value = spearman_correlation(x, y)
    assert abs(corr - 1.0) < 1e-6
    assert p_value < 0.01

    # Perfect negative correlation
    x = [1, 2, 3, 4, 5]
    y = [10, 8, 6, 4, 2]
    corr, p_value = spearman_correlation(x, y)
    assert abs(corr - (-1.0)) < 1e-6


def test_pearson_correlation():
    """Test Pearson correlation."""
    from scylla.analysis.stats import pearson_correlation

    # Perfect positive correlation
    x = [1, 2, 3, 4, 5]
    y = [2, 4, 6, 8, 10]
    corr, p_value = pearson_correlation(x, y)
    assert abs(corr - 1.0) < 1e-6
    assert p_value < 0.01

    # No correlation
    x = [1, 2, 3, 4, 5]
    y = [3, 3, 3, 3, 3]  # Constant
    corr, p_value = pearson_correlation(x, y)
    assert np.isnan(corr)  # Pearson undefined for constant series
