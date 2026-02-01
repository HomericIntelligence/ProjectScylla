"""Tests for duration_seconds integration (Issue #327 partial)."""

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))


def test_duration_seconds_integration(sample_runs_df):
    """Test that duration_seconds is integrated into statistical tests (Issue #327)."""
    from export_data import compute_statistical_results

    from scylla.analysis.figures import derive_tier_order

    tier_order = derive_tier_order(sample_runs_df)
    results = compute_statistical_results(sample_runs_df, tier_order)

    # Verify duration_seconds in normality tests
    duration_normality = [
        t for t in results["normality_tests"] if t["metric"] == "duration_seconds"
    ]
    assert len(duration_normality) > 0, "duration_seconds should appear in normality_tests"

    # Verify duration_seconds in omnibus tests
    duration_omnibus = [t for t in results["omnibus_tests"] if t["metric"] == "duration_seconds"]
    assert len(duration_omnibus) > 0, "duration_seconds should appear in omnibus_tests"

    # Verify duration_seconds in pairwise comparisons
    duration_pairwise = [
        t for t in results["pairwise_comparisons"] if t["metric"] == "duration_seconds"
    ]
    assert len(duration_pairwise) > 0, "duration_seconds should appear in pairwise_comparisons"

    # Verify duration_seconds in effect sizes
    duration_effects = [t for t in results["effect_sizes"] if t["metric"] == "duration_seconds"]
    assert len(duration_effects) > 0, "duration_seconds should appear in effect_sizes"

    # Verify duration_seconds in correlations (already there from impl_rate integration)
    duration_corr = [
        c
        for c in results["correlations"]
        if c["metric1"] == "duration_seconds" or c["metric2"] == "duration_seconds"
    ]
    assert len(duration_corr) > 0, "duration_seconds should appear in correlations"
