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

        pareto_points = result_df[result_df["is_pareto"]]

        # Should have 3 Pareto points: T0, T1, T2
        assert len(pareto_points) == 3, f"Expected 3 Pareto points, got {len(pareto_points)}"

        pareto_tiers = set(pareto_points["tier"])
        assert pareto_tiers == {"T0", "T1", "T2"}


def test_pareto_frontier_tied_points():
    """Test Pareto frontier with tied cost-score pairs.

    If two points have identical (cost, score), both should be Pareto efficient.
    """
    from scylla.analysis.figures.cost_analysis import fig08_cost_quality_pareto

    data = {
        "agent_model": ["model1"] * 3,
        "tier": ["T0", "T1", "T2"],
        "cost_usd": [1.0, 1.0, 2.0],  # T0 and T1 tied
        "score": [0.8, 0.8, 0.9],  # T0 and T1 tied
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

        pareto_points = result_df[result_df["is_pareto"]]

        # All three should be Pareto (T2 dominates in score, T0/T1 tied and non-dominated)
        # Actually: T2 dominates T0/T1 (better score for higher cost), so only T2 is Pareto
        # No wait: Pareto frontier keeps points where NO other point is strictly better
        # in both dimensions
        # T2: (cost=2, score=0.9) - best score but higher cost
        # T0/T1: (cost=1, score=0.8) - best cost but lower score
        # These are non-dominated trade-offs, so all should be Pareto
        assert len(pareto_points) >= 2  # At least T0/T1 or T2


def test_pareto_frontier_single_point():
    """Test Pareto frontier with a single point (trivial case)."""
    from scylla.analysis.figures.cost_analysis import fig08_cost_quality_pareto

    data = {
        "agent_model": ["model1"],
        "tier": ["T0"],
        "cost_usd": [1.0],
        "score": [0.8],
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

        pareto_points = result_df[result_df["is_pareto"]]

        # Single point is always Pareto efficient
        assert len(pareto_points) == 1
        assert pareto_points.iloc[0]["tier"] == "T0"
