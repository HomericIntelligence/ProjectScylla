"""Tests for export_data.py script."""

import json
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))


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
        assert "tier1" in pairwise
        assert "tier2" in pairwise
        assert "u_statistic" in pairwise
        assert "p_value" in pairwise
        assert "is_significant" in pairwise

    # Verify effect sizes have expected fields
    if len(results["effect_sizes"]) > 0:
        effect = results["effect_sizes"][0]
        assert "model" in effect
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
    for model, stats in by_model.items():
        assert "median_score" in stats
        assert "std_score" in stats
        assert "q1_score" in stats
        assert "q3_score" in stats
        assert "total_tokens" in stats
        assert "mean_duration" in stats
        assert "n_subtests" in stats
        assert "tiers" in stats

    # Build by_tier section
    by_tier = {}
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
    for tier, stats in by_tier.items():
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
