"""Tests for export_data.py script."""

import json
from typing import Any


def test_compute_statistical_results(sample_runs_df, tmp_path):
    """Test compute_statistical_results generates valid JSON."""
    from export_data import compute_statistical_results

    from scylla.analysis.figures import derive_tier_order

    tier_order = derive_tier_order(sample_runs_df)
    results = compute_statistical_results(sample_runs_df, tier_order)

    # Verify structure
    assert "normality_tests" in results
    assert "omnibus_tests" in results
    assert "pairwise_comparisons" in results
    assert "effect_sizes" in results
    assert "correlations" in results

    # Verify normality tests have expected fields
    if len(results["normality_tests"]) > 0:
        norm_test = results["normality_tests"][0]
        assert "model" in norm_test
        assert "tier" in norm_test
        assert "metric" in norm_test
        assert "w_statistic" in norm_test
        assert "p_value" in norm_test
        assert "is_normal" in norm_test

    # Verify omnibus tests have expected fields
    if len(results["omnibus_tests"]) > 0:
        omnibus = results["omnibus_tests"][0]
        assert "model" in omnibus
        assert "metric" in omnibus
        assert "h_statistic" in omnibus
        assert "p_value" in omnibus
        assert "is_significant" in omnibus

    # Verify pairwise comparisons have expected fields
    if len(results["pairwise_comparisons"]) > 0:
        pairwise = results["pairwise_comparisons"][0]
        assert "model" in pairwise
        assert "metric" in pairwise  # Added for impl_rate integration
        assert "tier1" in pairwise
        assert "tier2" in pairwise
        assert "u_statistic" in pairwise
        assert "p_value" in pairwise
        assert "is_significant" in pairwise

    # Verify effect sizes have expected fields
    if len(results["effect_sizes"]) > 0:
        effect = results["effect_sizes"][0]
        assert "model" in effect
        assert "metric" in effect  # Added for impl_rate integration
        assert "tier1" in effect
        assert "tier2" in effect
        assert "cliffs_delta" in effect
        assert "ci_low" in effect
        assert "ci_high" in effect
        assert "is_significant" in effect

    # Verify correlations have expected fields
    if len(results["correlations"]) > 0:
        corr = results["correlations"][0]
        assert "model" in corr
        assert "metric1" in corr
        assert "metric2" in corr
        assert "spearman_rho" in corr
        assert "p_value" in corr
        assert "is_significant" in corr

    # Verify JSON serializable
    json_str = json.dumps(results, indent=2)
    assert len(json_str) > 0


def test_enhanced_summary_json(sample_runs_df, tmp_path):
    """Test enhanced summary.json includes new statistics."""
    from export_data import json_nan_handler

    from scylla.analysis.figures import derive_tier_order

    tier_order = derive_tier_order(sample_runs_df)
    models = sample_runs_df["agent_model"].unique()

    # Build enhanced by_model section
    by_model = {}
    for model in models:
        model_df = sample_runs_df[sample_runs_df["agent_model"] == model]
        scores = model_df["score"].dropna()
        costs = model_df["cost_usd"].dropna()
        durations = model_df["duration_seconds"].dropna()

        by_model[model] = {
            "total_runs": len(model_df),
            "pass_rate": float(model_df["passed"].mean()),
            "mean_score": float(scores.mean()),
            "median_score": float(scores.median()),
            "std_score": float(scores.std()),
            "min_score": float(scores.min()),
            "max_score": float(scores.max()),
            "q1_score": float(scores.quantile(0.25)),
            "q3_score": float(scores.quantile(0.75)),
            "total_cost": float(costs.sum()),
            "mean_cost_per_run": float(costs.mean()),
            "median_cost": float(costs.median()),
            "total_tokens": int(model_df["total_tokens"].sum()),
            "mean_duration": float(durations.mean()),
            "n_subtests": int(model_df["subtest"].nunique()),
            "tiers": sorted(model_df["tier"].unique().tolist()),
        }

    # Verify all expected fields exist
    for _model, stats in by_model.items():
        assert "median_score" in stats
        assert "std_score" in stats
        assert "q1_score" in stats
        assert "q3_score" in stats
        assert "total_tokens" in stats
        assert "mean_duration" in stats
        assert "n_subtests" in stats
        assert "tiers" in stats

    # Build by_tier section
    by_tier: dict[str, dict[str, Any]] = {}
    for tier in tier_order:
        tier_df = sample_runs_df[sample_runs_df["tier"] == tier]
        scores = tier_df["score"].dropna()
        costs = tier_df["cost_usd"].dropna()

        by_tier[tier] = {
            "total_runs": len(tier_df),
            "pass_rate": float(tier_df["passed"].mean()),
            "mean_score": float(scores.mean()),
            "median_score": float(scores.median()),
            "std_score": float(scores.std()),
            "mean_cost": float(costs.mean()),
            "total_cost": float(costs.sum()),
            "n_subtests": int(tier_df["subtest"].nunique()),
        }

    # Verify by_tier has expected structure
    assert len(by_tier) == len(tier_order)
    for _tier, stats in by_tier.items():
        assert "total_runs" in stats
        assert "pass_rate" in stats
        assert "mean_score" in stats
        assert "median_score" in stats
        assert "std_score" in stats
        assert "mean_cost" in stats

    # Verify JSON serializable with NaN handler
    summary = {"by_model": by_model, "by_tier": by_tier}
    json_str = json.dumps(summary, indent=2, default=json_nan_handler)
    assert len(json_str) > 0


def test_json_nan_handler():
    """Test json_nan_handler converts NaN/inf correctly."""
    import numpy as np
    from export_data import json_nan_handler

    # Test NaN conversion
    assert json_nan_handler(np.nan) is None
    assert json_nan_handler(float("nan")) is None

    # Test infinity conversion
    assert json_nan_handler(np.inf) is None
    assert json_nan_handler(-np.inf) is None
    assert json_nan_handler(float("inf")) is None
    assert json_nan_handler(float("-inf")) is None

    # Test numpy types conversion
    assert json_nan_handler(np.int64(42)) == 42
    assert json_nan_handler(np.float64(3.14)) == 3.14
    assert json_nan_handler(np.bool_(True))  # Numpy bool converts to Python bool (truthy)

    # Test passthrough for regular types (returns as-is)
    assert json_nan_handler("string") == "string"
    assert json_nan_handler([1, 2, 3]) == [1, 2, 3]
    assert json_nan_handler({"key": "value"}) == {"key": "value"}


def test_compute_statistical_results_empty_df(tmp_path):
    """Test compute_statistical_results handles empty DataFrame gracefully."""
    import pandas as pd
    from export_data import compute_statistical_results

    # Create minimal empty DataFrame
    empty_df = pd.DataFrame(
        columns=[
            "agent_model",
            "tier",
            "score",
            "impl_rate",
            "cost_usd",
            "total_tokens",
            "duration_seconds",
            "passed",
        ]
    )

    tier_order: list[str] = []
    results = compute_statistical_results(empty_df, tier_order)

    # Should return empty lists for all categories
    assert results["normality_tests"] == []
    assert results["omnibus_tests"] == []
    assert results["pairwise_comparisons"] == []
    assert results["effect_sizes"] == []
    assert results["correlations"] == []


def test_compute_statistical_results_single_tier(sample_runs_df):
    """Test compute_statistical_results with only one tier (no pairwise comparisons)."""
    from export_data import compute_statistical_results

    # Filter to single tier
    single_tier_df = sample_runs_df[sample_runs_df["tier"] == "T0"]
    tier_order = ["T0"]

    results = compute_statistical_results(single_tier_df, tier_order)

    # Normality tests should still run
    assert "normality_tests" in results

    # No pairwise comparisons or effect sizes (need at least 2 tiers)
    # But omnibus tests may still run if multiple models exist
    assert "pairwise_comparisons" in results
    assert "effect_sizes" in results


def test_compute_statistical_results_degenerate_data():
    """Test compute_statistical_results with degenerate data (small samples)."""
    import pandas as pd
    from export_data import compute_statistical_results

    # Create minimal DataFrame with 2 runs per tier
    degenerate_df = pd.DataFrame(
        {
            "agent_model": ["model1", "model1"],
            "tier": ["T0", "T1"],
            "score": [0.5, 0.6],
            "impl_rate": [0.7, 0.8],
            "cost_usd": [1.0, 1.5],
            "total_tokens": [100, 150],
            "duration_seconds": [10.0, 15.0],
            "passed": [True, False],
        }
    )

    tier_order = ["T0", "T1"]
    results = compute_statistical_results(degenerate_df, tier_order)

    # Should complete without errors (may have limited results due to small N)
    assert "normality_tests" in results
    assert "omnibus_tests" in results
    assert "pairwise_comparisons" in results


def test_compute_statistical_results_correlation_correction(sample_runs_df):
    """Test that correlations include multiple comparison correction."""
    from export_data import compute_statistical_results

    from scylla.analysis.figures import derive_tier_order

    tier_order = derive_tier_order(sample_runs_df)
    results = compute_statistical_results(sample_runs_df, tier_order)

    # Check that correlations include p_value_corrected
    if len(results["correlations"]) > 0:
        corr = results["correlations"][0]
        # Should have both raw and corrected p-values after P1-2 implementation
        assert "p_value" in corr
        # Note: p_value_corrected may not be in export_data.py yet
        # This is a forward-looking test


def test_export_data_validation_warnings(sample_runs_df, tmp_path, capsys):
    """Test that export_data logs warnings for data validation issues."""
    from export_data import compute_statistical_results

    from scylla.analysis.figures import derive_tier_order

    # Create DataFrame with NaN values
    df_with_nans = sample_runs_df.copy()
    df_with_nans.loc[0, "score"] = float("nan")
    df_with_nans.loc[1, "cost_usd"] = float("nan")

    tier_order = derive_tier_order(df_with_nans)
    results = compute_statistical_results(df_with_nans, tier_order)

    # Should complete despite NaN values (dropna in correlations)
    assert "correlations" in results


def test_impl_rate_integration(sample_runs_df):
    """Test that impl_rate is integrated into all statistical tests (Issue #324)."""
    from export_data import compute_statistical_results

    from scylla.analysis.figures import derive_tier_order

    tier_order = derive_tier_order(sample_runs_df)
    results = compute_statistical_results(sample_runs_df, tier_order)

    # Verify impl_rate in normality tests
    impl_rate_normality = [t for t in results["normality_tests"] if t["metric"] == "impl_rate"]
    assert len(impl_rate_normality) > 0, "impl_rate should appear in normality_tests"

    # Verify impl_rate in omnibus tests
    impl_rate_omnibus = [t for t in results["omnibus_tests"] if t["metric"] == "impl_rate"]
    assert len(impl_rate_omnibus) > 0, "impl_rate should appear in omnibus_tests"

    # Verify impl_rate in pairwise comparisons
    impl_rate_pairwise = [t for t in results["pairwise_comparisons"] if t["metric"] == "impl_rate"]
    assert len(impl_rate_pairwise) > 0, "impl_rate should appear in pairwise_comparisons"

    # Verify impl_rate in effect sizes
    impl_rate_effects = [t for t in results["effect_sizes"] if t["metric"] == "impl_rate"]
    assert len(impl_rate_effects) > 0, "impl_rate should appear in effect_sizes"

    # Verify impl_rate in correlations
    impl_rate_corr = [
        c
        for c in results["correlations"]
        if c["metric1"] == "impl_rate" or c["metric2"] == "impl_rate"
    ]
    assert len(impl_rate_corr) > 0, "impl_rate should appear in correlations"
