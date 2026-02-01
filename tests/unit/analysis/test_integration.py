"""End-to-end integration tests for analysis pipeline.

Tests the full pipeline flow: load -> build DataFrames -> generate outputs.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
import pytest


def test_e2e_pipeline_with_sample_data(sample_runs_df):
    """End-to-end test: complete analysis pipeline with sample data.

    Verifies that the full pipeline can execute without crashes:
    1. DataFrames are properly structured
    2. Tables can be generated
    3. Figures can be generated
    4. No exceptions raised during processing
    """
    from scylla.analysis.figures.tier_performance import fig04_pass_rate_by_tier
    from scylla.analysis.tables.summary import table01_tier_summary

    # Verify DataFrame structure
    assert isinstance(sample_runs_df, pd.DataFrame)
    assert "tier" in sample_runs_df.columns
    assert "agent_model" in sample_runs_df.columns
    assert "passed" in sample_runs_df.columns
    assert len(sample_runs_df) > 0

    # Test table generation (no exceptions)
    with TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        # Generate summary table (tables don't take output_dir)
        table_md, table_tex = table01_tier_summary(sample_runs_df)
        assert isinstance(table_md, str)
        assert isinstance(table_tex, str)
        assert len(table_md) > 0
        assert len(table_tex) > 0
        assert "Tier" in table_md
        assert r"\begin{table}" in table_tex or r"\begin{longtable}" in table_tex

        # Generate figure (smoke test)
        fig04_pass_rate_by_tier(sample_runs_df, output_dir, render=False)

        # Verify outputs exist
        vl_files = list(output_dir.glob("*.vl.json"))
        csv_files = list(output_dir.glob("*.csv"))
        assert len(vl_files) > 0, "Expected Vega-Lite spec files"
        assert len(csv_files) > 0, "Expected CSV data files"


def test_e2e_empty_dataframe_handling():
    """Test pipeline gracefully handles empty DataFrames."""
    from scylla.analysis.tables.summary import table01_tier_summary

    # Create minimal empty DataFrame with required columns
    empty_df = pd.DataFrame(
        columns=["tier", "agent_model", "passed", "score", "cost_usd", "total_tokens"]
    )

    # Should not crash, even with empty data (tables don't need output_dir)
    table_md, table_tex = table01_tier_summary(empty_df)
    assert isinstance(table_md, str)
    assert isinstance(table_tex, str)


def test_e2e_dataframe_types_validation(sample_runs_df):
    """Verify DataFrame has correct column types for analysis."""
    # Critical columns must exist
    required_cols = ["tier", "agent_model", "passed", "score"]
    for col in required_cols:
        assert col in sample_runs_df.columns, f"Missing required column: {col}"

    # passed should be boolean or 0/1
    assert sample_runs_df["passed"].dtype in [
        bool,
        "int64",
        "int32",
    ], "passed column should be boolean or integer"

    # score should be numeric
    assert pd.api.types.is_numeric_dtype(sample_runs_df["score"]), "score column should be numeric"

    # tier should be categorical or string-like
    tier_dtype_str = str(sample_runs_df["tier"].dtype)
    assert any(
        x in tier_dtype_str for x in ["object", "category", "string", "str"]
    ), f"tier column should be string or categorical, got {tier_dtype_str}"


@pytest.mark.parametrize(
    "function_name,module_path",
    [
        ("fig04_pass_rate_by_tier", "scylla.analysis.figures.tier_performance"),
        ("fig01_score_variance_by_tier", "scylla.analysis.figures.variance"),
        ("table01_tier_summary", "scylla.analysis.tables.summary"),
    ],
)
def test_e2e_smoke_test_outputs(function_name, module_path, sample_runs_df):
    """Smoke test: verify key outputs can be generated without crashes."""
    import importlib

    module = importlib.import_module(module_path)
    func = getattr(module, function_name)

    with TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        # Call function - should not raise
        if "table" in function_name:
            # Tables don't take output_dir
            result = func(sample_runs_df)
            assert result is not None
            assert len(result) == 2  # (markdown, latex)
        else:
            # Figure function
            func(sample_runs_df, output_dir, render=False)
            # Verify at least one output file created
            assert len(list(output_dir.iterdir())) > 0


def test_e2e_statistical_pipeline_integration(sample_runs_df):
    """Test that statistical functions integrate properly with DataFrames."""
    from scylla.analysis.stats import bootstrap_ci, cliffs_delta, mann_whitney_u

    # Test bootstrap CI on real data
    tier_data = sample_runs_df[sample_runs_df["tier"] == "T0"]
    if len(tier_data) >= 2:
        passed_values = tier_data["passed"].astype(int)
        mean, ci_low, ci_high = bootstrap_ci(passed_values)
        assert ci_low <= mean <= ci_high
        assert 0.0 <= mean <= 1.0

    # Test Cliff's delta on two tiers
    tiers = sample_runs_df["tier"].unique()
    if len(tiers) >= 2:
        tier1_data = sample_runs_df[sample_runs_df["tier"] == tiers[0]]["score"]
        tier2_data = sample_runs_df[sample_runs_df["tier"] == tiers[1]]["score"]

        if len(tier1_data) > 0 and len(tier2_data) > 0:
            delta = cliffs_delta(tier1_data, tier2_data)
            assert -1.0 <= delta <= 1.0 or pd.isna(delta)

            # Test Mann-Whitney U
            u_stat, p_value = mann_whitney_u(tier1_data, tier2_data)
            assert 0.0 <= p_value <= 1.0 or pd.isna(p_value)
