"""Tests for rubric conflict handling in load_rubric_weights().

Covers the rubric_conflict parameter: 'error', 'warn', 'first', 'last',
float tolerance, and error message contents.
"""

import warnings

import pytest
import yaml


def _write_rubric(path, categories: dict[str, object]) -> None:
    """Write a rubric.yaml file at path/rubric.yaml."""
    path.mkdir(parents=True, exist_ok=True)
    with (path / "rubric.yaml").open("w") as f:
        yaml.dump({"categories": categories}, f)


def _make_two_experiment_dir(tmp_path, cats1: dict[str, object], cats2: dict[str, object]):
    """Create data_dir with two experiments having different rubric weights."""
    data_dir = tmp_path / "fullruns"
    exp1_dir = data_dir / "experiment1" / "2026-01-31T10-00-00-run"
    exp2_dir = data_dir / "experiment2" / "2026-01-31T11-00-00-run"
    _write_rubric(exp1_dir, cats1)
    _write_rubric(exp2_dir, cats2)
    return data_dir


# ---------------------------------------------------------------------------
# Error (default) behaviour
# ---------------------------------------------------------------------------


def test_rubric_conflict_raises_by_default(tmp_path):
    """Two experiments with same category, different weights → RubricConflictError."""
    from scylla.analysis.loader import RubricConflictError, load_rubric_weights

    data_dir = _make_two_experiment_dir(
        tmp_path,
        cats1={"functional": {"weight": 10.0}},
        cats2={"functional": {"weight": 5.0}},
    )

    with pytest.raises(RubricConflictError):
        load_rubric_weights(data_dir)


def test_rubric_conflict_raises_explicitly(tmp_path):
    """Passing rubric_conflict='error' raises RubricConflictError."""
    from scylla.analysis.loader import RubricConflictError, load_rubric_weights

    data_dir = _make_two_experiment_dir(
        tmp_path,
        cats1={"functional": {"weight": 10.0}},
        cats2={"functional": {"weight": 5.0}},
    )

    with pytest.raises(RubricConflictError):
        load_rubric_weights(data_dir, rubric_conflict="error")


def test_rubric_conflict_error_message_contains_details(tmp_path):
    """Error message includes category name, both experiment names, both weights."""
    from scylla.analysis.loader import RubricConflictError, load_rubric_weights

    data_dir = _make_two_experiment_dir(
        tmp_path,
        cats1={"functional": {"weight": 10.0}},
        cats2={"functional": {"weight": 5.0}},
    )

    with pytest.raises(RubricConflictError) as exc_info:
        load_rubric_weights(data_dir)

    msg = str(exc_info.value)
    assert "functional" in msg
    assert "experiment1" in msg
    assert "experiment2" in msg
    assert "10.0" in msg or "10" in msg
    assert "5.0" in msg or "5" in msg


# ---------------------------------------------------------------------------
# Warn behaviour
# ---------------------------------------------------------------------------


def test_rubric_conflict_warn(tmp_path):
    """rubric_conflict='warn' emits UserWarning and returns weights."""
    from scylla.analysis.loader import load_rubric_weights

    data_dir = _make_two_experiment_dir(
        tmp_path,
        cats1={"functional": {"weight": 10.0}},
        cats2={"functional": {"weight": 5.0}},
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        weights = load_rubric_weights(data_dir, rubric_conflict="warn")

    assert weights is not None
    assert any(issubclass(w.category, UserWarning) for w in caught)


def test_rubric_conflict_warn_message_contains_details(tmp_path):
    """Warning message includes category name and conflicting weights."""
    from scylla.analysis.loader import load_rubric_weights

    data_dir = _make_two_experiment_dir(
        tmp_path,
        cats1={"functional": {"weight": 10.0}},
        cats2={"functional": {"weight": 5.0}},
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        load_rubric_weights(data_dir, rubric_conflict="warn")

    warning_msgs = " ".join(str(w.message) for w in caught)
    assert "functional" in warning_msgs


# ---------------------------------------------------------------------------
# First / Last policies
# ---------------------------------------------------------------------------


def test_rubric_conflict_first(tmp_path):
    """rubric_conflict='first' keeps the first experiment's weights."""
    from scylla.analysis.loader import load_rubric_weights

    data_dir = _make_two_experiment_dir(
        tmp_path,
        cats1={"functional": {"weight": 10.0}},
        cats2={"functional": {"weight": 5.0}},
    )

    weights = load_rubric_weights(data_dir, rubric_conflict="first")

    assert weights is not None
    assert weights["functional"] == pytest.approx(10.0)


def test_rubric_conflict_last(tmp_path):
    """rubric_conflict='last' keeps the last experiment's weights."""
    from scylla.analysis.loader import load_rubric_weights

    data_dir = _make_two_experiment_dir(
        tmp_path,
        cats1={"functional": {"weight": 10.0}},
        cats2={"functional": {"weight": 5.0}},
    )

    weights = load_rubric_weights(data_dir, rubric_conflict="last")

    assert weights is not None
    assert weights["functional"] == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# No-conflict cases
# ---------------------------------------------------------------------------


def test_rubric_no_conflict_identical_weights(tmp_path):
    """Same weights across experiments → no error or warning raised."""
    from scylla.analysis.loader import load_rubric_weights

    data_dir = _make_two_experiment_dir(
        tmp_path,
        cats1={"functional": {"weight": 10.0}},
        cats2={"functional": {"weight": 10.0}},
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        weights = load_rubric_weights(data_dir)

    assert weights is not None
    assert weights["functional"] == pytest.approx(10.0)
    # No rubric-conflict warnings
    rubric_warnings = [w for w in caught if "rubric" in str(w.message).lower()]
    assert len(rubric_warnings) == 0


def test_rubric_conflict_float_tolerance(tmp_path):
    """Weights differing by ≤ 1e-6 are not treated as a conflict."""
    from scylla.analysis.loader import load_rubric_weights

    data_dir = _make_two_experiment_dir(
        tmp_path,
        cats1={"functional": {"weight": 10.0}},
        cats2={"functional": {"weight": 10.0 + 1e-10}},
    )

    # Should not raise
    weights = load_rubric_weights(data_dir)
    assert weights is not None
    assert weights["functional"] == pytest.approx(10.0)


def test_rubric_new_category_in_second_experiment(tmp_path):
    """Second experiment adds a new category → no conflict, weights merged."""
    from scylla.analysis.loader import load_rubric_weights

    data_dir = _make_two_experiment_dir(
        tmp_path,
        cats1={"functional": {"weight": 10.0}},
        cats2={"code_quality": {"weight": 5.0}},
    )

    weights = load_rubric_weights(data_dir)
    assert weights is not None
    assert weights["functional"] == pytest.approx(10.0)
    assert weights["code_quality"] == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# load_all_experiments integration
# ---------------------------------------------------------------------------


def test_load_all_experiments_passes_rubric_conflict(tmp_path):
    """load_all_experiments() accepts rubric_conflict parameter."""
    import inspect

    from scylla.analysis.loader import load_all_experiments

    sig = inspect.signature(load_all_experiments)
    assert "rubric_conflict" in sig.parameters
    default = sig.parameters["rubric_conflict"].default
    assert default == "error"
