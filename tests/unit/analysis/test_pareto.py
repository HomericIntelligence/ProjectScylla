"""Unit tests for Pareto frontier calculation."""

import numpy as np
import pandas as pd


def test_pareto_frontier_basic():
    """Test Pareto frontier with clear domination relationships.

    Counterexample that exposed the bug:
    - A(cost=1, score=0.8): Best point (low cost, high score)
    - B(cost=2, score=0.6): Dominated by A
    - C(cost=3, score=0.4): Dominated by both A and B

    Expected frontier: {A}
    Buggy implementation returned: {C} (anti-Pareto set)
    """
    # Import the function from the module
    from scylla.analysis.figures.cost_analysis import fig08_cost_quality_pareto

    # Create test data with known Pareto relationships
    data = {
        "agent_model": ["model1", "model1", "model1"],
        "tier": ["T0", "T1", "T2"],
        "cost_usd": [1.0, 2.0, 3.0],
        "score": [0.8, 0.6, 0.4],
        "passed": [1, 1, 1],  # Required column
    }
    runs_df = pd.DataFrame(data)

    # Create a temporary output directory
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        # Generate the figure (render=False to skip PNG/PDF)
        fig08_cost_quality_pareto(runs_df, output_dir, render=False)

        # Read the generated data CSV to check Pareto classification
        data_csv = output_dir / "fig08_cost_quality_pareto.csv"
        result_df = pd.read_csv(data_csv)

        # Check which points are marked as Pareto efficient
        pareto_points = result_df[result_df["is_pareto"]]

        # Should have exactly 1 Pareto point: T0 (cost=1.0, score=0.8)
        assert len(pareto_points) == 1, (
            f"Expected 1 Pareto point, got {len(pareto_points)}: "
            f"{pareto_points[['tier', 'mean_cost', 'mean_score']].to_dict('records')}"
        )

        assert (
            pareto_points.iloc[0]["tier"] == "T0"
        ), f"Expected T0 to be Pareto efficient, got {pareto_points.iloc[0]['tier']}"
        assert np.isclose(pareto_points.iloc[0]["mean_cost"], 1.0)
        assert np.isclose(pareto_points.iloc[0]["mean_score"], 0.8)


def test_pareto_frontier_multiple_efficient():
    """Test Pareto frontier with multiple non-dominated points.

    Points:
    - A(cost=1, score=0.6): Pareto (cheapest)
    - B(cost=2, score=0.8): Pareto (better score for moderate cost)
    - C(cost=3, score=0.9): Pareto (best score)
    - D(cost=2.5, score=0.7): Dominated by B (higher cost, lower score)

    Expected frontier: {A, B, C}
    """
    from scylla.analysis.figures.cost_analysis import fig08_cost_quality_pareto

    data = {
        "agent_model": ["model1"] * 4,
        "tier": ["T0", "T1", "T2", "T3"],
        "cost_usd": [1.0, 2.0, 3.0, 2.5],
        "score": [0.6, 0.8, 0.9, 0.7],
        "passed": [1, 1, 1, 1],
    }
    runs_df = pd.DataFrame(data)

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        fig08_cost_quality_pareto(runs_df, output_dir, render=False)

        data_csv = output_dir / "fig08_cost_quality_pareto.csv"
        result_df = pd.read_csv(data_csv)

        pareto_points = result_df[result_df["is_pareto"]].sort_values("mean_cost")
        pareto_tiers = pareto_points["tier"].tolist()

        assert pareto_tiers == [
            "T0",
            "T1",
            "T2",
        ], f"Expected Pareto points [T0, T1, T2], got {pareto_tiers}"


def test_pareto_frontier_tied_points():
    """Test Pareto frontier with identical points (all should be Pareto)."""
    from scylla.analysis.figures.cost_analysis import fig08_cost_quality_pareto

    data = {
        "agent_model": ["model1"] * 3,
        "tier": ["T0", "T1", "T2"],
        "cost_usd": [2.0, 2.0, 2.0],
        "score": [0.7, 0.7, 0.7],
        "passed": [1, 1, 1],
    }
    runs_df = pd.DataFrame(data)

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        fig08_cost_quality_pareto(runs_df, output_dir, render=False)

        data_csv = output_dir / "fig08_cost_quality_pareto.csv"
        result_df = pd.read_csv(data_csv)

        # All tied points should be Pareto efficient
        assert result_df["is_pareto"].all(), "All identical points should be Pareto efficient"


def test_pareto_frontier_single_point():
    """Test Pareto frontier with only one point (trivially Pareto)."""
    from scylla.analysis.figures.cost_analysis import fig08_cost_quality_pareto

    data = {
        "agent_model": ["model1"],
        "tier": ["T0"],
        "cost_usd": [1.5],
        "score": [0.75],
        "passed": [1],
    }
    runs_df = pd.DataFrame(data)

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        fig08_cost_quality_pareto(runs_df, output_dir, render=False)

        data_csv = output_dir / "fig08_cost_quality_pareto.csv"
        result_df = pd.read_csv(data_csv)

        assert result_df["is_pareto"].iloc[0], "Single point should be Pareto efficient"
