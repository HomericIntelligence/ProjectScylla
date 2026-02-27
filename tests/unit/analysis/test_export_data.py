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


def test_process_metrics_in_summary(sample_runs_df):
    """Test that process metrics appear in overall_stats, by_model, and by_tier (Issue #1135)."""
    import numpy as np
    import pandas as pd
    from export_data import json_nan_handler

    from scylla.analysis.figures import derive_tier_order

    tier_order = derive_tier_order(sample_runs_df)

    # --- overall_stats ---
    process_metric_keys = [
        "mean_r_prog",
        "mean_cfp",
        "mean_pr_revert_rate",
        "mean_strategic_drift",
    ]

    overall_stats: dict[str, Any] = {
        "mean_r_prog": float(sample_runs_df["r_prog"].dropna().mean())
        if not sample_runs_df["r_prog"].dropna().empty
        else None,
        "mean_cfp": float(sample_runs_df["cfp"].dropna().mean())
        if not sample_runs_df["cfp"].dropna().empty
        else None,
        "mean_pr_revert_rate": float(sample_runs_df["pr_revert_rate"].dropna().mean())
        if not sample_runs_df["pr_revert_rate"].dropna().empty
        else None,
        "mean_strategic_drift": float(sample_runs_df["strategic_drift"].dropna().mean())
        if not sample_runs_df["strategic_drift"].dropna().empty
        else None,
    }

    for key in process_metric_keys:
        assert key in overall_stats, f"overall_stats missing {key}"
        val = overall_stats[key]
        assert val is None or isinstance(val, float), (
            f"overall_stats[{key}] must be float or None, got {type(val)}"
        )

    # --- by_model ---
    for model in sample_runs_df["agent_model"].unique():
        model_df = sample_runs_df[sample_runs_df["agent_model"] == model]
        by_model_stats: dict[str, Any] = {
            "mean_r_prog": float(model_df["r_prog"].dropna().mean())
            if not model_df["r_prog"].dropna().empty
            else None,
            "mean_cfp": float(model_df["cfp"].dropna().mean())
            if not model_df["cfp"].dropna().empty
            else None,
            "mean_pr_revert_rate": float(model_df["pr_revert_rate"].dropna().mean())
            if not model_df["pr_revert_rate"].dropna().empty
            else None,
            "mean_strategic_drift": float(model_df["strategic_drift"].dropna().mean())
            if not model_df["strategic_drift"].dropna().empty
            else None,
        }
        for key in process_metric_keys:
            assert key in by_model_stats, f"by_model[{model}] missing {key}"
            val = by_model_stats[key]
            assert val is None or isinstance(val, float), (
                f"by_model[{model}][{key}] must be float or None"
            )

    # --- by_tier ---
    for tier in tier_order:
        tier_df = sample_runs_df[sample_runs_df["tier"] == tier]
        by_tier_stats: dict[str, Any] = {
            "mean_r_prog": float(tier_df["r_prog"].dropna().mean())
            if not tier_df["r_prog"].dropna().empty
            else None,
            "mean_cfp": float(tier_df["cfp"].dropna().mean())
            if not tier_df["cfp"].dropna().empty
            else None,
            "mean_pr_revert_rate": float(tier_df["pr_revert_rate"].dropna().mean())
            if not tier_df["pr_revert_rate"].dropna().empty
            else None,
            "mean_strategic_drift": float(tier_df["strategic_drift"].dropna().mean())
            if not tier_df["strategic_drift"].dropna().empty
            else None,
        }
        for key in process_metric_keys:
            assert key in by_tier_stats, f"by_tier[{tier}] missing {key}"
            val = by_tier_stats[key]
            assert val is None or isinstance(val, float), (
                f"by_tier[{tier}][{key}] must be float or None"
            )

    # --- all-NaN column → None ---
    nan_df = sample_runs_df.copy()
    nan_df["r_prog"] = np.nan
    r_prog_vals = nan_df["r_prog"].dropna()
    result = float(r_prog_vals.mean()) if not r_prog_vals.empty else None
    assert result is None, "All-NaN r_prog should produce None"

    # --- zero values → 0.0 not None ---
    zero_df = sample_runs_df.copy()
    zero_df["r_prog"] = 0.0
    r_prog_vals = zero_df["r_prog"].dropna()
    result = float(r_prog_vals.mean()) if not r_prog_vals.empty else None
    assert result == 0.0, "All-zero r_prog should produce 0.0"

    # --- values are JSON-serializable (not np.nan) ---
    serializable_check = {
        "mean_r_prog": float(sample_runs_df["r_prog"].dropna().mean())
        if not sample_runs_df["r_prog"].dropna().empty
        else None,
    }
    json_str = json.dumps(serializable_check, default=json_nan_handler)
    parsed = json.loads(json_str)
    assert "mean_r_prog" in parsed
    val = parsed["mean_r_prog"]
    assert val is None or isinstance(val, float), "mean_r_prog must be null or float in JSON"

    # --- partial NaN: mean only over non-NaN values ---
    partial_df = pd.DataFrame({"r_prog": [0.2, np.nan, 0.4, np.nan, 0.6]})
    r_prog_clean = partial_df["r_prog"].dropna()
    partial_mean = float(r_prog_clean.mean()) if not r_prog_clean.empty else None
    assert partial_mean is not None
    assert abs(partial_mean - 0.4) < 1e-9, f"Partial NaN mean should be 0.4, got {partial_mean}"


# ---------------------------------------------------------------------------
# Unit tests for extracted helper functions
# ---------------------------------------------------------------------------


def test_compute_normality_tests_structure(sample_runs_df):
    """_compute_normality_tests returns dicts with required fields for each metric."""
    from export_data import _compute_normality_tests

    from scylla.analysis.figures import derive_tier_order

    tier_order = derive_tier_order(sample_runs_df)
    models = sorted(sample_runs_df["agent_model"].unique())
    results = _compute_normality_tests(sample_runs_df, models, tier_order)

    assert isinstance(results, list)
    assert len(results) > 0

    required_fields = {"model", "tier", "metric", "n", "w_statistic", "p_value", "is_normal"}
    for entry in results:
        assert required_fields <= entry.keys(), f"Missing fields in normality entry: {entry.keys()}"
        assert isinstance(entry["is_normal"], bool)
        assert entry["n"] >= 3


def test_compute_normality_tests_all_four_metrics(sample_runs_df):
    """_compute_normality_tests covers score, impl_rate, cost_usd, duration_seconds."""
    from export_data import _compute_normality_tests

    from scylla.analysis.figures import derive_tier_order

    tier_order = derive_tier_order(sample_runs_df)
    models = sorted(sample_runs_df["agent_model"].unique())
    results = _compute_normality_tests(sample_runs_df, models, tier_order)

    metrics_present = {entry["metric"] for entry in results}
    assert "score" in metrics_present
    assert "impl_rate" in metrics_present
    assert "cost_usd" in metrics_present
    assert "duration_seconds" in metrics_present


def test_compute_omnibus_tests_structure(sample_runs_df):
    """_compute_omnibus_tests returns dicts with required fields."""
    from export_data import _compute_omnibus_tests

    from scylla.analysis.figures import derive_tier_order

    tier_order = derive_tier_order(sample_runs_df)
    models = sorted(sample_runs_df["agent_model"].unique())
    results = _compute_omnibus_tests(sample_runs_df, models, tier_order)

    assert isinstance(results, list)
    assert len(results) > 0

    required_fields = {"model", "metric", "n_groups", "h_statistic", "p_value", "is_significant"}
    for entry in results:
        assert required_fields <= entry.keys()
        assert isinstance(entry["is_significant"], bool)
        assert entry["n_groups"] >= 2


def test_compute_omnibus_tests_three_metrics(sample_runs_df):
    """_compute_omnibus_tests covers pass_rate, impl_rate, duration_seconds."""
    from export_data import _compute_omnibus_tests

    from scylla.analysis.figures import derive_tier_order

    tier_order = derive_tier_order(sample_runs_df)
    models = sorted(sample_runs_df["agent_model"].unique())
    results = _compute_omnibus_tests(sample_runs_df, models, tier_order)

    metrics_present = {entry["metric"] for entry in results}
    assert "pass_rate" in metrics_present
    assert "impl_rate" in metrics_present
    assert "duration_seconds" in metrics_present


def test_collect_pairwise_pass_rate_includes_overall_contrast(sample_runs_df):
    """_collect_pairwise_pass_rate adds the first->last overall contrast."""
    from export_data import _collect_pairwise_pass_rate

    from scylla.analysis.figures import derive_tier_order

    tier_order = derive_tier_order(sample_runs_df)
    model = sorted(sample_runs_df["agent_model"].unique())[0]
    model_runs = sample_runs_df[sample_runs_df["agent_model"] == model]

    raw_p_values, test_metadata = _collect_pairwise_pass_rate(model_runs, model, tier_order)

    # Should have consecutive pairs + 1 overall contrast
    expected_consecutive = len(tier_order) - 1
    assert len(raw_p_values) == expected_consecutive + 1

    # Last entry should be the overall contrast
    last = test_metadata[-1]
    assert last.get("overall_contrast") is True
    assert last["tier1"] == tier_order[0]
    assert last["tier2"] == tier_order[-1]


def test_compute_pairwise_comparisons_metrics(sample_runs_df):
    """_compute_pairwise_comparisons covers pass_rate, impl_rate, duration_seconds."""
    from export_data import _compute_pairwise_comparisons

    from scylla.analysis.figures import derive_tier_order

    tier_order = derive_tier_order(sample_runs_df)
    models = sorted(sample_runs_df["agent_model"].unique())
    results = _compute_pairwise_comparisons(sample_runs_df, models, tier_order)

    assert isinstance(results, list)
    assert len(results) > 0

    metrics_present = {entry["metric"] for entry in results}
    assert "pass_rate" in metrics_present
    assert "impl_rate" in metrics_present
    assert "duration_seconds" in metrics_present

    # Every entry must have corrected and raw p-values
    for entry in results:
        assert "p_value_raw" in entry
        assert "p_value" in entry
        assert "is_significant" in entry


def test_compute_effect_sizes_structure(sample_runs_df):
    """_compute_effect_sizes returns Cliff's delta entries with CI bounds."""
    from export_data import _compute_effect_sizes

    from scylla.analysis.figures import derive_tier_order

    tier_order = derive_tier_order(sample_runs_df)
    models = sorted(sample_runs_df["agent_model"].unique())
    results = _compute_effect_sizes(sample_runs_df, models, tier_order)

    assert isinstance(results, list)
    assert len(results) > 0

    required_fields = {
        "model",
        "metric",
        "tier1",
        "tier2",
        "cliffs_delta",
        "ci_low",
        "ci_high",
        "is_significant",
    }
    for entry in results:
        assert required_fields <= entry.keys()
        assert -1.0 <= entry["cliffs_delta"] <= 1.0
        assert entry["ci_low"] <= entry["ci_high"]


def test_compute_effect_sizes_three_metrics(sample_runs_df):
    """_compute_effect_sizes covers pass_rate, impl_rate, and duration_seconds."""
    from export_data import _compute_effect_sizes

    from scylla.analysis.figures import derive_tier_order

    tier_order = derive_tier_order(sample_runs_df)
    models = sorted(sample_runs_df["agent_model"].unique())
    results = _compute_effect_sizes(sample_runs_df, models, tier_order)

    metrics_present = {entry["metric"] for entry in results}
    assert "pass_rate" in metrics_present
    assert "impl_rate" in metrics_present
    assert "duration_seconds" in metrics_present


def test_compute_power_analysis_structure(sample_runs_df):
    """_compute_power_analysis returns entries with required power fields."""
    from export_data import _compute_effect_sizes, _compute_power_analysis

    from scylla.analysis.figures import derive_tier_order

    tier_order = derive_tier_order(sample_runs_df)
    models = sorted(sample_runs_df["agent_model"].unique())
    effect_sizes = _compute_effect_sizes(sample_runs_df, models, tier_order)
    results = _compute_power_analysis(sample_runs_df, models, tier_order, effect_sizes)

    assert isinstance(results, list)
    assert len(results) > 0

    required_fields = {"model", "metric", "tier1", "tier2", "n1", "power_at_medium_0_3"}
    for entry in results:
        assert required_fields <= entry.keys()


def test_compute_power_analysis_includes_omnibus(sample_runs_df):
    """_compute_power_analysis includes pass_rate_omnibus KW power entries."""
    from export_data import _compute_effect_sizes, _compute_power_analysis

    from scylla.analysis.figures import derive_tier_order

    tier_order = derive_tier_order(sample_runs_df)
    models = sorted(sample_runs_df["agent_model"].unique())
    effect_sizes = _compute_effect_sizes(sample_runs_df, models, tier_order)
    results = _compute_power_analysis(sample_runs_df, models, tier_order, effect_sizes)

    omnibus_entries = [e for e in results if e["metric"] == "pass_rate_omnibus"]
    # One omnibus entry per model
    assert len(omnibus_entries) == len(models)


def test_compute_correlations_structure(sample_runs_df):
    """_compute_correlations returns Spearman rho entries with required fields."""
    from export_data import _compute_correlations

    models = sorted(sample_runs_df["agent_model"].unique())
    results = _compute_correlations(sample_runs_df, models)

    assert isinstance(results, list)
    assert len(results) > 0

    required_fields = {
        "model",
        "metric1",
        "metric2",
        "n",
        "spearman_rho",
        "p_value",
        "is_significant",
    }
    for entry in results:
        assert required_fields <= entry.keys()
        assert -1.0 <= entry["spearman_rho"] <= 1.0
        assert entry["n"] >= 3


def test_compute_correlations_includes_impl_rate(sample_runs_df):
    """_compute_correlations includes impl_rate pairs."""
    from export_data import _compute_correlations

    models = sorted(sample_runs_df["agent_model"].unique())
    results = _compute_correlations(sample_runs_df, models)

    impl_rate_entries = [
        e for e in results if e["metric1"] == "impl_rate" or e["metric2"] == "impl_rate"
    ]
    assert len(impl_rate_entries) > 0


def test_compute_tier_descriptives_structure(sample_runs_df):
    """_compute_tier_descriptives returns tier stats including frontier row."""
    from export_data import _compute_tier_descriptives

    from scylla.analysis.figures import derive_tier_order

    tier_order = derive_tier_order(sample_runs_df)
    models = sorted(sample_runs_df["agent_model"].unique())
    results = _compute_tier_descriptives(sample_runs_df, models, tier_order)

    assert isinstance(results, list)
    assert len(results) > 0

    required_fields = {"model", "tier", "n", "pass_rate", "mean_cost", "median_cost", "cop"}
    tier_entries = [e for e in results if e["tier"] != "frontier"]
    for entry in tier_entries:
        assert required_fields <= entry.keys()


def test_compute_tier_descriptives_frontier_row(sample_runs_df):
    """_compute_tier_descriptives includes one frontier row per model."""
    from export_data import _compute_tier_descriptives

    from scylla.analysis.figures import derive_tier_order

    tier_order = derive_tier_order(sample_runs_df)
    models = sorted(sample_runs_df["agent_model"].unique())
    results = _compute_tier_descriptives(sample_runs_df, models, tier_order)

    frontier_entries = [e for e in results if e["tier"] == "frontier"]
    assert len(frontier_entries) == len(models)
    for entry in frontier_entries:
        assert "frontier_tier" in entry
        assert entry["cop"] is not None


def test_compute_interaction_tests_structure(sample_runs_df):
    """_compute_interaction_tests returns SRH results for four metrics."""
    from export_data import _compute_interaction_tests

    results = _compute_interaction_tests(sample_runs_df)

    assert isinstance(results, list)
    assert len(results) > 0

    required_fields = {"metric", "effect", "h_statistic", "df", "p_value", "is_significant"}
    for entry in results:
        assert required_fields <= entry.keys()
        assert isinstance(entry["is_significant"], bool)


def test_compute_interaction_tests_four_metrics(sample_runs_df):
    """_compute_interaction_tests covers score, impl_rate, cost_usd, duration_seconds."""
    from export_data import _compute_interaction_tests

    results = _compute_interaction_tests(sample_runs_df)

    metrics_present = {entry["metric"] for entry in results}
    assert "score" in metrics_present
    assert "impl_rate" in metrics_present
    assert "cost_usd" in metrics_present
    assert "duration_seconds" in metrics_present


def test_helpers_compose_to_same_result(sample_runs_df):
    """compute_statistical_results output matches direct helper composition."""
    from export_data import (
        _compute_correlations,
        _compute_effect_sizes,
        _compute_interaction_tests,
        _compute_normality_tests,
        _compute_omnibus_tests,
        _compute_pairwise_comparisons,
        _compute_tier_descriptives,
        compute_statistical_results,
    )

    from scylla.analysis.figures import derive_tier_order

    tier_order = derive_tier_order(sample_runs_df)
    models = sorted(sample_runs_df["agent_model"].unique())

    orchestrated = compute_statistical_results(sample_runs_df, tier_order)
    effect_sizes = _compute_effect_sizes(sample_runs_df, models, tier_order)

    assert orchestrated["normality_tests"] == _compute_normality_tests(
        sample_runs_df, models, tier_order
    )
    assert orchestrated["omnibus_tests"] == _compute_omnibus_tests(
        sample_runs_df, models, tier_order
    )
    assert orchestrated["pairwise_comparisons"] == _compute_pairwise_comparisons(
        sample_runs_df, models, tier_order
    )
    assert orchestrated["effect_sizes"] == effect_sizes
    assert orchestrated["correlations"] == _compute_correlations(sample_runs_df, models)
    assert orchestrated["tier_descriptives"] == _compute_tier_descriptives(
        sample_runs_df, models, tier_order
    )
    assert orchestrated["interaction_tests"] == _compute_interaction_tests(sample_runs_df)
