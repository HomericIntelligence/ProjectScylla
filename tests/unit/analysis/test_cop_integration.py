"""Tests for CoP and Frontier CoP integration (Issue #325)."""


def test_cop_frontier_cop_integration(sample_runs_df):
    """Test that CoP and Frontier CoP are integrated (Issue #325)."""
    from export_data import compute_statistical_results

    from scylla.analysis.figures import derive_tier_order

    tier_order = derive_tier_order(sample_runs_df)
    results = compute_statistical_results(sample_runs_df, tier_order)

    # Verify tier_descriptives section exists
    assert "tier_descriptives" in results, "tier_descriptives should be in statistical_results"
    assert len(results["tier_descriptives"]) > 0, "tier_descriptives should have entries"

    # Verify CoP computed per tier
    tier_descriptives = [d for d in results["tier_descriptives"] if d["tier"] != "frontier"]
    assert len(tier_descriptives) > 0, "Should have tier-level CoP entries"

    # Verify each tier descriptive has required fields
    for desc in tier_descriptives:
        assert "model" in desc
        assert "tier" in desc
        assert "n" in desc
        assert "pass_rate" in desc
        assert "mean_cost" in desc
        assert "cop" in desc

    # Verify Frontier CoP computed per model
    frontier_entries = [d for d in results["tier_descriptives"] if d["tier"] == "frontier"]
    assert len(frontier_entries) > 0, "Should have Frontier CoP entries"

    # Verify Frontier CoP has required fields
    for frontier in frontier_entries:
        assert "model" in frontier
        assert frontier["tier"] == "frontier"
        assert "cop" in frontier
        assert "frontier_tier" in frontier
