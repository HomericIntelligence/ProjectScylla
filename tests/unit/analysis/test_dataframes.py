"""Unit tests for DataFrame builders."""

import numpy as np
import pandas as pd


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
        "tokens_in",
        "tokens_out",
        "latency_seconds",
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

    # Tokens should be positive integers
    assert (sample_runs_df["tokens_in"] > 0).all()
    assert (sample_runs_df["tokens_out"] > 0).all()


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
    """Test subtests DataFrame has expected structure."""
    required_cols = [
        "experiment",
        "agent_model",
        "tier",
        "subtest",
        "pass_rate",
        "mean_score",
        "std_score",
        "mean_cost",
        "std_cost",
    ]

    for col in required_cols:
        assert col in sample_subtests_df.columns

    # Pass rate should be in [0, 1]
    assert sample_subtests_df["pass_rate"].min() >= 0.0
    assert sample_subtests_df["pass_rate"].max() <= 1.0

    # Mean score should be in [0, 1]
    assert sample_subtests_df["mean_score"].min() >= 0.0
    assert sample_subtests_df["mean_score"].max() <= 1.0


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
    assert abs(first_row["pass_rate"] - expected_pass_rate) < 1e-6


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
    assert compute_consistency(10.0, 2.0) == 0.8
    assert compute_consistency(10.0, 0.0) == 1.0
    assert compute_consistency(10.0, 10.0) == 0.0
    assert compute_consistency(0.0, 5.0) == 0.0

    # Negative consistency should be clamped
    assert compute_consistency(5.0, 10.0) == 0.0


def test_cop_calculation():
    """Test Cost-of-Pass calculation."""
    from scylla.analysis.stats import compute_cop

    assert abs(compute_cop(1.0, 0.5) - 2.0) < 1e-6
    assert abs(compute_cop(2.0, 0.8) - 2.5) < 1e-6
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
