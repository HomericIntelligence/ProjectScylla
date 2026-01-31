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
