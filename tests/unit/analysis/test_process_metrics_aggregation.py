"""Tests for process metric aggregations in build_subtests_df() and tier_summary().

Verifies that mean/median/std of r_prog, cfp, pr_revert_rate, and strategic_drift
are correctly aggregated at both the subtest and tier levels.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PROCESS_METRIC_COLS = [
    "mean_r_prog",
    "median_r_prog",
    "std_r_prog",
    "mean_cfp",
    "median_cfp",
    "std_cfp",
    "mean_pr_revert_rate",
    "median_pr_revert_rate",
    "std_pr_revert_rate",
    "mean_strategic_drift",
    "median_strategic_drift",
    "std_strategic_drift",
]


def _make_runs_df(
    r_prog: Sequence[float | None],
    cfp: Sequence[float | None] | None = None,
    pr_revert_rate: Sequence[float | None] | None = None,
    strategic_drift: Sequence[float | None] | None = None,
    *,
    n: int | None = None,
) -> pd.DataFrame:
    """Build a minimal runs_df with process metrics for a single subtest group.

    Args:
        r_prog: Values for the r_prog column (None → NaN).
        cfp: Values for cfp column; defaults to same length as r_prog, all NaN.
        pr_revert_rate: Values for pr_revert_rate; defaults to all NaN.
        strategic_drift: Values for strategic_drift; defaults to all NaN.
        n: Ignored — inferred from len(r_prog).

    Returns:
        DataFrame with one subtest group suitable for build_subtests_df().

    """
    size = len(r_prog)
    if cfp is None:
        cfp = [np.nan] * size
    if pr_revert_rate is None:
        pr_revert_rate = [np.nan] * size
    if strategic_drift is None:
        strategic_drift = [np.nan] * size

    rows = []
    for i in range(size):
        rows.append(
            {
                "experiment": "test-exp",
                "agent_model": "Sonnet 4.5",
                "tier": "T0",
                "subtest": "00",
                "run_number": i + 1,
                "passed": 1,
                "score": 0.8,
                "impl_rate": 0.8,
                "grade": "A",
                "cost_usd": 0.05,
                "duration_seconds": 10.0,
                "r_prog": r_prog[i],
                "cfp": cfp[i],
                "pr_revert_rate": pr_revert_rate[i],
                "strategic_drift": strategic_drift[i],
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# build_subtests_df — column presence
# ---------------------------------------------------------------------------


def test_build_subtests_df_has_all_process_metric_columns() -> None:
    """build_subtests_df() output contains all 12 process metric aggregation columns."""
    from scylla.analysis.dataframes import build_subtests_df

    runs_df = _make_runs_df([0.5, 0.6, 0.7], cfp=[0.1, 0.2, 0.15])
    result = build_subtests_df(runs_df)

    for col in _PROCESS_METRIC_COLS:
        assert col in result.columns, f"Missing column: {col}"


# ---------------------------------------------------------------------------
# build_subtests_df — correct values when data is present
# ---------------------------------------------------------------------------


def test_build_subtests_df_mean_r_prog_correct() -> None:
    """build_subtests_df() computes correct mean_r_prog."""
    from scylla.analysis.dataframes import build_subtests_df

    values = [0.4, 0.6, 0.8]
    runs_df = _make_runs_df(values)
    result = build_subtests_df(runs_df)

    assert result["mean_r_prog"].iloc[0] == pytest.approx(np.mean(values), abs=1e-9)


def test_build_subtests_df_median_r_prog_correct() -> None:
    """build_subtests_df() computes correct median_r_prog."""
    from scylla.analysis.dataframes import build_subtests_df

    values = [0.4, 0.6, 0.8]
    runs_df = _make_runs_df(values)
    result = build_subtests_df(runs_df)

    assert result["median_r_prog"].iloc[0] == pytest.approx(np.median(values), abs=1e-9)


def test_build_subtests_df_std_r_prog_correct() -> None:
    """build_subtests_df() computes correct std_r_prog."""
    from scylla.analysis.dataframes import build_subtests_df

    values = [0.4, 0.6, 0.8]
    runs_df = _make_runs_df(values)
    result = build_subtests_df(runs_df)

    # pandas std uses ddof=1 by default
    expected_std = pd.Series(values).std()
    assert result["std_r_prog"].iloc[0] == pytest.approx(expected_std, abs=1e-9)


def test_build_subtests_df_cfp_aggregations_correct() -> None:
    """build_subtests_df() computes correct mean/median/std for cfp."""
    from scylla.analysis.dataframes import build_subtests_df

    cfp_values = [0.1, 0.2, 0.3]
    runs_df = _make_runs_df([np.nan] * 3, cfp=cfp_values)
    result = build_subtests_df(runs_df)

    assert result["mean_cfp"].iloc[0] == pytest.approx(np.mean(cfp_values), abs=1e-9)
    assert result["median_cfp"].iloc[0] == pytest.approx(np.median(cfp_values), abs=1e-9)
    assert result["std_cfp"].iloc[0] == pytest.approx(pd.Series(cfp_values).std(), abs=1e-9)


def test_build_subtests_df_pr_revert_rate_aggregations_correct() -> None:
    """build_subtests_df() computes correct mean/median/std for pr_revert_rate."""
    from scylla.analysis.dataframes import build_subtests_df

    pr_values = [0.05, 0.10, 0.15]
    runs_df = _make_runs_df([np.nan] * 3, pr_revert_rate=pr_values)
    result = build_subtests_df(runs_df)

    assert result["mean_pr_revert_rate"].iloc[0] == pytest.approx(np.mean(pr_values), abs=1e-9)
    assert result["median_pr_revert_rate"].iloc[0] == pytest.approx(np.median(pr_values), abs=1e-9)
    assert result["std_pr_revert_rate"].iloc[0] == pytest.approx(
        pd.Series(pr_values).std(), abs=1e-9
    )


def test_build_subtests_df_strategic_drift_aggregations_correct() -> None:
    """build_subtests_df() computes correct mean/median/std for strategic_drift."""
    from scylla.analysis.dataframes import build_subtests_df

    drift_values = [0.1, 0.3, 0.5]
    runs_df = _make_runs_df([np.nan] * 3, strategic_drift=drift_values)
    result = build_subtests_df(runs_df)

    assert result["mean_strategic_drift"].iloc[0] == pytest.approx(np.mean(drift_values), abs=1e-9)
    assert result["median_strategic_drift"].iloc[0] == pytest.approx(
        np.median(drift_values), abs=1e-9
    )
    assert result["std_strategic_drift"].iloc[0] == pytest.approx(
        pd.Series(drift_values).std(), abs=1e-9
    )


# ---------------------------------------------------------------------------
# build_subtests_df — all-NaN group → NaN aggregation
# ---------------------------------------------------------------------------


def test_build_subtests_df_all_nan_r_prog_yields_nan() -> None:
    """build_subtests_df() produces NaN aggregations when all r_prog are NaN."""
    from scylla.analysis.dataframes import build_subtests_df

    runs_df = _make_runs_df([np.nan, np.nan, np.nan])
    result = build_subtests_df(runs_df)

    assert pd.isna(result["mean_r_prog"].iloc[0])
    assert pd.isna(result["median_r_prog"].iloc[0])
    assert pd.isna(result["std_r_prog"].iloc[0])


def test_build_subtests_df_all_nan_cfp_yields_nan() -> None:
    """build_subtests_df() produces NaN aggregations when all cfp are NaN."""
    from scylla.analysis.dataframes import build_subtests_df

    runs_df = _make_runs_df([0.5, 0.6], cfp=[np.nan, np.nan])
    result = build_subtests_df(runs_df)

    assert pd.isna(result["mean_cfp"].iloc[0])
    assert pd.isna(result["median_cfp"].iloc[0])
    assert pd.isna(result["std_cfp"].iloc[0])


# ---------------------------------------------------------------------------
# build_subtests_df — mixed (some NaN) group → skips NaN
# ---------------------------------------------------------------------------


def test_build_subtests_df_mixed_nan_r_prog_skips_nan() -> None:
    """build_subtests_df() skips NaN values in r_prog aggregation (skipna=True)."""
    from scylla.analysis.dataframes import build_subtests_df

    values_with_nan = [0.4, np.nan, 0.8]
    runs_df = _make_runs_df(values_with_nan)
    result = build_subtests_df(runs_df)

    # mean/median/std should use only the non-NaN values [0.4, 0.8]
    non_nan = [0.4, 0.8]
    assert result["mean_r_prog"].iloc[0] == pytest.approx(np.mean(non_nan), abs=1e-9)
    assert result["median_r_prog"].iloc[0] == pytest.approx(np.median(non_nan), abs=1e-9)
    assert np.isfinite(result["mean_r_prog"].iloc[0])


# ---------------------------------------------------------------------------
# tier_summary — column presence
# ---------------------------------------------------------------------------


def test_tier_summary_has_all_process_metric_columns() -> None:
    """tier_summary() output contains all 12 process metric aggregation columns."""
    from scylla.analysis.dataframes import tier_summary

    runs_df = _make_runs_df([0.5, 0.6, 0.7], cfp=[0.1, 0.2, 0.15])
    result = tier_summary(runs_df)

    for col in _PROCESS_METRIC_COLS:
        assert col in result.columns, f"Missing column: {col}"


# ---------------------------------------------------------------------------
# tier_summary — correct values when data is present
# ---------------------------------------------------------------------------


def test_tier_summary_mean_r_prog_correct() -> None:
    """tier_summary() computes correct mean_r_prog."""
    from scylla.analysis.dataframes import tier_summary

    values = [0.3, 0.5, 0.7, 0.9]
    runs_df = _make_runs_df(values)
    result = tier_summary(runs_df)

    assert result["mean_r_prog"].iloc[0] == pytest.approx(np.mean(values), abs=1e-9)


def test_tier_summary_all_nan_yields_nan() -> None:
    """tier_summary() produces NaN aggregations when all process metrics are NaN."""
    from scylla.analysis.dataframes import tier_summary

    runs_df = _make_runs_df([np.nan, np.nan])
    result = tier_summary(runs_df)

    assert pd.isna(result["mean_r_prog"].iloc[0])
    assert pd.isna(result["mean_cfp"].iloc[0])
    assert pd.isna(result["mean_pr_revert_rate"].iloc[0])
    assert pd.isna(result["mean_strategic_drift"].iloc[0])


# ---------------------------------------------------------------------------
# Fixture symmetry: sample_subtests_df columns match build_subtests_df output
# ---------------------------------------------------------------------------


def test_fixture_symmetry_subtests_df(sample_runs_df, sample_subtests_df) -> None:
    """sample_subtests_df fixture columns match production build_subtests_df output."""
    from scylla.analysis.dataframes import build_subtests_df

    production_df = build_subtests_df(sample_runs_df)

    assert set(sample_subtests_df.columns) == set(production_df.columns), (
        f"Fixture columns differ from production.\n"
        f"  In fixture only: {set(sample_subtests_df.columns) - set(production_df.columns)}\n"
        f"  In production only: {set(production_df.columns) - set(sample_subtests_df.columns)}"
    )
