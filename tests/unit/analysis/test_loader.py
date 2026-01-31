"""Unit tests for data loader.

Note: These tests use the public API of the loader module.
Internal/private helper functions are not tested directly.
"""

import pytest


def test_loader_imports():
    """Test that loader module can be imported."""
    # Basic smoke test - can import the module
    import scylla.analysis.loader

    assert scylla.analysis.loader is not None


def test_load_run_signature():
    """Test load_run function has expected signature."""
    import inspect

    from scylla.analysis.loader import load_run

    # Verify function exists and has expected parameters
    sig = inspect.signature(load_run)
    params = list(sig.parameters.keys())

    # Should have parameters for experiment, tier, subtest, run_dir
    assert "run_dir" in params
    assert "experiment" in params
    assert "tier" in params
    assert "subtest" in params


def test_load_all_experiments_signature():
    """Test load_all_experiments function has expected signature."""
    import inspect

    from scylla.analysis.loader import load_all_experiments

    # Verify function exists
    sig = inspect.signature(load_all_experiments)
    assert sig is not None


@pytest.mark.skipif(True, reason="Requires actual filesystem data")
def test_load_experiment_integration():
    """Integration test for loading experiment data.

    This test is skipped by default as it requires actual filesystem data.
    To run this test, ensure you have experiment data in ~/fullruns/ and remove skip.
    """
    from pathlib import Path

    from scylla.analysis.loader import load_all_experiments

    # This would require actual data
    experiments = load_all_experiments(base_dir=Path("~/fullruns").expanduser())
    assert isinstance(experiments, dict)
