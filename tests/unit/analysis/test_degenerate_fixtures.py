"""Test degenerate input fixtures for edge case testing."""

import numpy as np


def test_degenerate_single_element(degenerate_single_element):
    """Verify single-element fixture."""
    assert len(degenerate_single_element) == 1
    assert degenerate_single_element[0] == 0.5


def test_degenerate_all_same(degenerate_all_same):
    """Verify all-same-value fixture."""
    assert len(degenerate_all_same) == 5
    assert np.all(degenerate_all_same == 0.7)
    assert np.std(degenerate_all_same) == 0.0


def test_degenerate_all_pass(degenerate_all_pass):
    """Verify all-pass fixture."""
    assert len(degenerate_all_pass) == 5
    assert np.all(degenerate_all_pass == 1)
    assert np.mean(degenerate_all_pass) == 1.0


def test_degenerate_all_fail(degenerate_all_fail):
    """Verify all-fail fixture."""
    assert len(degenerate_all_fail) == 5
    assert np.all(degenerate_all_fail == 0)
    assert np.mean(degenerate_all_fail) == 0.0


def test_degenerate_unbalanced_groups(degenerate_unbalanced_groups):
    """Verify unbalanced groups fixture."""
    assert len(degenerate_unbalanced_groups["small"]) == 2
    assert len(degenerate_unbalanced_groups["large"]) == 50
    assert len(degenerate_unbalanced_groups["small"]) * 25 == len(
        degenerate_unbalanced_groups["large"]
    )


def test_degenerate_empty_array(degenerate_empty_array):
    """Verify empty array fixture."""
    assert len(degenerate_empty_array) == 0
    assert degenerate_empty_array.size == 0


def test_degenerate_nan_values(degenerate_nan_values):
    """Verify NaN values fixture."""
    assert len(degenerate_nan_values) == 5
    assert np.sum(np.isnan(degenerate_nan_values)) == 2
    assert np.sum(~np.isnan(degenerate_nan_values)) == 3


def test_degenerate_inf_values(degenerate_inf_values):
    """Verify infinite values fixture."""
    assert len(degenerate_inf_values) == 5
    assert np.sum(np.isinf(degenerate_inf_values)) == 2
    assert np.sum(np.isposinf(degenerate_inf_values)) == 1
    assert np.sum(np.isneginf(degenerate_inf_values)) == 1


def test_degenerate_binary_data(degenerate_binary_data):
    """Verify binary data fixture."""
    assert len(degenerate_binary_data) == 8
    assert set(degenerate_binary_data) == {0, 1}
    assert np.all((degenerate_binary_data == 0) | (degenerate_binary_data == 1))


def test_degenerate_boundary_values(degenerate_boundary_values):
    """Verify boundary values fixture."""
    assert len(degenerate_boundary_values) == 5
    assert np.min(degenerate_boundary_values) == 0.0
    assert np.max(degenerate_boundary_values) == 1.0
    assert 0.5 in degenerate_boundary_values


def test_degenerate_near_zero(degenerate_near_zero):
    """Verify near-zero values fixture."""
    assert len(degenerate_near_zero) == 5
    assert np.all(degenerate_near_zero > 0)
    assert np.all(degenerate_near_zero < 1e-5)
    assert np.max(degenerate_near_zero) == 1e-6


def test_degenerate_high_variance(degenerate_high_variance):
    """Verify high-variance fixture."""
    assert len(degenerate_high_variance) == 5
    variance = np.var(degenerate_high_variance)
    assert variance > 0.1  # Very high variance
    # Range spans nearly the full [0, 1] interval
    assert np.max(degenerate_high_variance) - np.min(degenerate_high_variance) > 0.9
