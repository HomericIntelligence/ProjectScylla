"""Unit tests for DataFrame builders."""

import numpy as np
import pandas as pd
import pytest


def test_build_runs_df_structure(sample_runs_df):
    """Test runs DataFrame has expected structure."""
    # Verify required columns exist
    required_cols = [
        "experiment",
        "agent_model",
        "tier",
        "subtest",
        "run_number",
        "passed",
        "score",
        "grade",
        "cost_usd",
        "input_tokens",
        "output_tokens",
        "cache_creation_tokens",
        "cache_read_tokens",
        "total_tokens",
        "duration_seconds",
        "agent_duration_seconds",
        "judge_duration_seconds",
        "exit_code",
    ]

    for col in required_cols:
        assert col in sample_runs_df.columns

    # Verify data types
    assert sample_runs_df["passed"].dtype == np.int64
    assert sample_runs_df["score"].dtype == np.float64
    assert sample_runs_df["cost_usd"].dtype == np.float64
    assert sample_runs_df["run_number"].dtype == np.int64


def test_build_runs_df_values(sample_runs_df):
    """Test runs DataFrame has valid values."""
    # Score should be in [0, 1]
    assert sample_runs_df["score"].min() >= 0.0
    assert sample_runs_df["score"].max() <= 1.0

    # Passed should be 0 or 1
    assert sample_runs_df["passed"].isin([0, 1]).all()

    # Cost should be positive
    assert (sample_runs_df["cost_usd"] > 0).all()

    # Tokens should be positive integers (or zero for cache tokens)
    assert (sample_runs_df["input_tokens"] > 0).all()
    assert (sample_runs_df["output_tokens"] > 0).all()
    assert (sample_runs_df["cache_creation_tokens"] >= 0).all()
    assert (sample_runs_df["cache_read_tokens"] >= 0).all()


def test_build_judges_df_structure(sample_judges_df):
    """Test judges DataFrame has expected structure."""
    required_cols = [
        "experiment",
        "agent_model",
        "tier",
        "subtest",
        "run_number",
        "judge_number",
        "judge_model",
        "judge_score",
        "judge_passed",
        "judge_grade",
        "judge_is_valid",
    ]

    for col in required_cols:
        assert col in sample_judges_df.columns

    # Verify 3 judges per run
    judges_per_run = sample_judges_df.groupby(
        ["experiment", "tier", "subtest", "run_number"]
    ).size()
    assert (judges_per_run == 3).all()


def test_build_criteria_df_structure(sample_criteria_df):
    """Test criteria DataFrame has expected structure."""
    required_cols = [
        "experiment",
        "agent_model",
        "tier",
        "subtest",
        "run_number",
        "judge_number",
        "judge_model",
        "criterion",
        "criterion_score",
        "criterion_achieved",
        "criterion_max",
    ]

    for col in required_cols:
        assert col in sample_criteria_df.columns

    # Verify 5 criteria per judge
    criteria_per_judge = sample_criteria_df.groupby(
        ["experiment", "tier", "subtest", "run_number", "judge_number"]
    ).size()
    assert (criteria_per_judge == 5).all()


def test_build_subtests_df_structure(sample_subtests_df):
    """Test subtests DataFrame has expected structure matching production.

    Must match columns produced by dataframes.build_subtests_df().
    """
    required_cols = [
        # Grouping keys
        "experiment",
        "agent_model",
        "tier",
        "subtest",
        # Score metrics
        "pass_rate",
        "mean_score",
        "median_score",
        "std_score",
        # Impl-rate metrics
        "mean_impl_rate",
        "median_impl_rate",
        "std_impl_rate",
        # Other metrics
        "consistency",
        "mean_cost",
        "total_cost",
        "mean_duration",
        "cop",
        # Grade distribution
        "grade_S",
        "grade_A",
        "grade_B",
        "grade_C",
        "grade_D",
        "grade_F",
        "modal_grade",
    ]

    for col in required_cols:
        assert col in sample_subtests_df.columns, f"Missing column: {col}"

    # Verify data types and ranges
    assert sample_subtests_df["pass_rate"].min() >= 0.0
    assert sample_subtests_df["pass_rate"].max() <= 1.0
    assert sample_subtests_df["mean_score"].min() >= 0.0
    assert sample_subtests_df["mean_score"].max() <= 1.0
    assert sample_subtests_df["consistency"].min() >= 0.0
    assert sample_subtests_df["consistency"].max() <= 1.0


def test_tier_summary_aggregation(sample_runs_df):
    """Test tier_summary() aggregation function."""
    from scylla.analysis.dataframes import tier_summary

    summary = tier_summary(sample_runs_df)

    # Verify structure
    assert "tier" in summary.columns
    assert "agent_model" in summary.columns
    assert "pass_rate" in summary.columns
    assert "mean_score" in summary.columns
    assert "mean_cost" in summary.columns

    # Verify one row per (model, tier) combination
    expected_rows = sample_runs_df.groupby(["agent_model", "tier"]).ngroups
    assert len(summary) == expected_rows

    # Verify aggregation is correct for one tier/model combo
    first_row = summary.iloc[0]
    model = first_row["agent_model"]
    tier = first_row["tier"]

    tier_data = sample_runs_df[
        (sample_runs_df["agent_model"] == model) & (sample_runs_df["tier"] == tier)
    ]

    expected_pass_rate = tier_data["passed"].mean()
    assert first_row["pass_rate"] == pytest.approx(expected_pass_rate, abs=1e-6)


def test_model_comparison_aggregation(sample_runs_df):
    """Test model_comparison() aggregation function."""
    from scylla.analysis.dataframes import model_comparison

    comparison = model_comparison(sample_runs_df)

    # Verify structure - model_comparison returns MultiIndex columns
    # from the aggregation: ('passed', 'mean'), ('score', 'mean'), etc.
    assert "agent_model" in comparison.columns or ("agent_model", "") in comparison.columns
    assert "tier" in comparison.columns or ("tier", "") in comparison.columns

    # Check that aggregated columns exist (as tuples in MultiIndex)
    column_list = list(comparison.columns)
    has_passed_mean = ("passed", "mean") in column_list or "passed" in column_list
    assert has_passed_mean, f"Expected ('passed', 'mean') in columns, got: {column_list}"

    # Verify one row per (model, tier) combination
    expected_rows = sample_runs_df.groupby(["agent_model", "tier"]).ngroups
    assert len(comparison) == expected_rows


def test_consistency_calculation():
    """Test consistency metric calculation (1 - CV)."""
    from scylla.analysis.stats import compute_consistency

    # Test with known values
    assert compute_consistency(10.0, 2.0) == pytest.approx(0.8)
    assert compute_consistency(10.0, 0.0) == pytest.approx(1.0)
    assert compute_consistency(10.0, 10.0) == pytest.approx(0.0)
    assert compute_consistency(0.0, 5.0) == pytest.approx(0.0)

    # Negative consistency should be clamped
    assert compute_consistency(5.0, 10.0) == pytest.approx(0.0)


def test_cop_calculation():
    """Test Cost-of-Pass calculation."""
    from scylla.analysis.stats import compute_cop

    assert compute_cop(1.0, 0.5) == pytest.approx(2.0, abs=1e-6)
    assert compute_cop(2.0, 0.8) == pytest.approx(2.5, abs=1e-6)
    assert compute_cop(1.0, 0.0) == float("inf")


def test_empty_dataframe_handling():
    """Test functions handle empty DataFrames gracefully."""
    from scylla.analysis.dataframes import tier_summary

    empty_df = pd.DataFrame(
        columns=[
            "experiment",
            "agent_model",
            "tier",
            "subtest",
            "run_number",
            "passed",
            "score",
            "grade",
            "cost_usd",
        ]
    )

    # Should return empty result, not crash
    summary = tier_summary(empty_df)
    assert len(summary) == 0


def test_dataframe_filtering(sample_runs_df):
    """Test filtering DataFrames by tier/model."""
    # Filter by single tier
    t0_only = sample_runs_df[sample_runs_df["tier"] == "T0"]
    assert (t0_only["tier"] == "T0").all()
    assert len(t0_only) > 0

    # Filter by single model
    sonnet_only = sample_runs_df[sample_runs_df["agent_model"] == "Sonnet 4.5"]
    assert (sonnet_only["agent_model"] == "Sonnet 4.5").all()
    assert len(sonnet_only) > 0

    # Filter by both
    t0_sonnet = sample_runs_df[
        (sample_runs_df["tier"] == "T0") & (sample_runs_df["agent_model"] == "Sonnet 4.5")
    ]
    assert len(t0_sonnet) > 0
    assert (t0_sonnet["tier"] == "T0").all()
    assert (t0_sonnet["agent_model"] == "Sonnet 4.5").all()


def test_judge_summary_aggregation(sample_judges_df):
    """Test judge_summary() aggregates judge scores correctly."""
    from scylla.analysis.dataframes import judge_summary

    summary = judge_summary(sample_judges_df)

    # Verify structure - should have one row per judge_model
    assert "judge_model" in summary.columns
    expected_judges = sample_judges_df["judge_model"].nunique()
    assert len(summary) == expected_judges

    # Verify aggregated columns exist (MultiIndex from agg)
    # Format: ('judge_score', 'mean'), ('judge_score', 'median'), etc.
    column_tuples = list(summary.columns)
    assert ("judge_score", "mean") in column_tuples
    assert ("judge_score", "median") in column_tuples
    assert ("judge_score", "std") in column_tuples
    assert ("judge_score", "min") in column_tuples
    assert ("judge_score", "max") in column_tuples
    assert ("judge_passed", "mean") in column_tuples

    # Verify aggregation correctness for one judge
    # Get the judge_model value as a scalar, not a Series
    first_judge_model = summary["judge_model"].iloc[0]
    judge_data = sample_judges_df[sample_judges_df["judge_model"] == first_judge_model]

    expected_mean = judge_data["judge_score"].mean()
    actual_mean = summary[summary["judge_model"] == first_judge_model][
        ("judge_score", "mean")
    ].iloc[0]
    assert actual_mean == pytest.approx(expected_mean, abs=1e-6)


def test_judge_summary_empty_dataframe():
    """Test judge_summary() handles empty DataFrames gracefully."""
    from scylla.analysis.dataframes import judge_summary

    empty_df = pd.DataFrame(
        columns=[
            "experiment",
            "agent_model",
            "tier",
            "subtest",
            "run_number",
            "judge_number",
            "judge_model",
            "judge_score",
            "judge_passed",
        ]
    )

    # Should return empty result, not crash
    summary = judge_summary(empty_df)
    assert len(summary) == 0


def test_criteria_summary_aggregation(sample_criteria_df):
    """Test criteria_summary() aggregates by criterion correctly."""
    from scylla.analysis.dataframes import criteria_summary

    summary = criteria_summary(sample_criteria_df)

    # Verify structure - should have one row per (agent_model, tier, criterion)
    assert "agent_model" in summary.columns
    assert "tier" in summary.columns
    assert "criterion" in summary.columns

    expected_rows = sample_criteria_df.groupby(["agent_model", "tier", "criterion"]).ngroups
    assert len(summary) == expected_rows

    # Verify aggregated columns exist (MultiIndex from agg)
    column_tuples = list(summary.columns)
    assert ("criterion_score", "mean") in column_tuples
    assert ("criterion_score", "std") in column_tuples
    assert ("criterion_score", "median") in column_tuples
    assert ("criterion_achieved", "sum") in column_tuples
    assert ("criterion_max", "sum") in column_tuples

    # Verify aggregation correctness for one criterion
    # Get scalar values, not Series
    model = summary["agent_model"].iloc[0]
    tier = summary["tier"].iloc[0]
    criterion = summary["criterion"].iloc[0]

    criterion_data = sample_criteria_df[
        (sample_criteria_df["agent_model"] == model)
        & (sample_criteria_df["tier"] == tier)
        & (sample_criteria_df["criterion"] == criterion)
    ]

    expected_mean = criterion_data["criterion_score"].mean()
    actual_mean = summary[
        (summary["agent_model"] == model)
        & (summary["tier"] == tier)
        & (summary["criterion"] == criterion)
    ][("criterion_score", "mean")].iloc[0]
    assert actual_mean == pytest.approx(expected_mean, abs=1e-6)


def test_criteria_summary_empty_dataframe():
    """Test criteria_summary() handles empty DataFrames gracefully."""
    from scylla.analysis.dataframes import criteria_summary

    empty_df = pd.DataFrame(
        columns=[
            "experiment",
            "agent_model",
            "tier",
            "subtest",
            "run_number",
            "judge_number",
            "judge_model",
            "criterion",
            "criterion_score",
            "criterion_achieved",
            "criterion_max",
        ]
    )

    # Should return empty result, not crash
    summary = criteria_summary(empty_df)
    assert len(summary) == 0
