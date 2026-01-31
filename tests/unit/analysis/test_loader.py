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


def test_model_id_to_display_removes_date_suffix():
    """Test that model_id_to_display removes date suffix from model IDs.

    Regression test for P0 bug where re.sub replaced pattern within full string,
    causing date suffix to leak through (e.g., "Sonnet 4.5-20250929").
    """
    from scylla.analysis.loader import model_id_to_display

    # Test date-suffixed models
    assert model_id_to_display("claude-sonnet-4-5-20250929") == "Sonnet 4.5"
    assert model_id_to_display("claude-opus-4-5-20251101") == "Opus 4.5"
    assert model_id_to_display("claude-haiku-3-5-20241022") == "Haiku 3.5"

    # Test without date suffix (should still work)
    assert model_id_to_display("claude-sonnet-3-5") == "Sonnet 3.5"
    assert model_id_to_display("claude-opus-4-0") == "Opus 4.0"

    # Test unknown model (should return as-is)
    assert model_id_to_display("gpt-4") == "gpt-4"
    assert model_id_to_display("unknown-model") == "unknown-model"
