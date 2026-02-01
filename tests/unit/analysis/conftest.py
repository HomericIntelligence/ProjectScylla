"""Shared fixtures for analysis tests."""

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest


@pytest.fixture(scope="function", autouse=True)
def clear_patches():
    """Clear all mock patches between tests to prevent pollution."""
    yield
    patch.stopall()


@pytest.fixture
def sample_runs_df():
    """Sample runs DataFrame for testing (~70 rows).

    Covers 2 models, 3 tiers, 2 subtests, 5 runs per combination.
    """
    np.random.seed(42)
    data = []

    models = ["Sonnet 4.5", "Haiku 4.5"]
    tiers = ["T0", "T1", "T2"]
    subtests = ["00", "01"]

    for model in models:
        for tier in tiers:
            for subtest in subtests:
                for run in range(1, 6):
                    # Generate semi-realistic data
                    passed = np.random.choice([0, 1], p=[0.3, 0.7])
                    score = np.random.uniform(0.5, 1.0) if passed else np.random.uniform(0.0, 0.5)

                    # impl_rate: usually close to score, but not identical
                    # Represents achieved/max across all criteria
                    impl_rate = score + np.random.uniform(-0.05, 0.05)
                    impl_rate = max(0.0, min(1.0, impl_rate))  # Clamp to [0, 1]

                    grade = (
                        np.random.choice(["S", "A", "B"])
                        if passed
                        else np.random.choice(["C", "D", "F"])
                    )
                    cost = np.random.uniform(0.01, 0.1)

                    # Token stats matching production schema
                    input_tokens = np.random.randint(1000, 10000)
                    output_tokens = np.random.randint(500, 5000)
                    cache_creation_tokens = np.random.randint(0, 2000)
                    cache_read_tokens = np.random.randint(0, 5000)
                    total_tokens = (
                        input_tokens + output_tokens + cache_creation_tokens + cache_read_tokens
                    )

                    # Duration stats matching production schema
                    agent_duration = np.random.uniform(5.0, 25.0)
                    judge_duration = np.random.uniform(1.0, 5.0)
                    duration_seconds = agent_duration + judge_duration

                    # Calculate CoP and consistency for completeness
                    consistency = 1 - (np.random.uniform(0.05, 0.15) / score) if score > 0 else 0
                    consistency = max(0.0, min(1.0, consistency))

                    data.append(
                        {
                            "experiment": f"test001-{model.lower().replace(' ', '-')}",
                            "agent_model": model,
                            "tier": tier,
                            "subtest": subtest,
                            "run_number": run,
                            "passed": passed,
                            "score": score,
                            "impl_rate": impl_rate,
                            "grade": grade,
                            "cost_usd": cost,
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens,
                            "cache_creation_tokens": cache_creation_tokens,
                            "cache_read_tokens": cache_read_tokens,
                            "total_tokens": total_tokens,
                            "duration_seconds": duration_seconds,
                            "agent_duration_seconds": agent_duration,
                            "judge_duration_seconds": judge_duration,
                            "consistency": consistency,
                            "exit_code": 0,
                        }
                    )

    return pd.DataFrame(data)


@pytest.fixture
def sample_judges_df(sample_runs_df):
    """Sample judges DataFrame (3 judges per run)."""
    np.random.seed(42)
    data = []

    judge_models = [
        "claude-opus-4-5-20251101",
        "claude-sonnet-4-5-20250129",
        "claude-haiku-4-5-20241223",
    ]

    for idx, row in sample_runs_df.iterrows():
        for judge_idx, judge_model in enumerate(judge_models, start=1):
            # Generate correlated scores (± 0.1 from run score)
            judge_score = np.clip(row["score"] + np.random.uniform(-0.1, 0.1), 0.0, 1.0)

            # Generate judge_impl_rate (correlated to impl_rate, ± 0.1)
            judge_impl_rate = np.clip(row["impl_rate"] + np.random.uniform(-0.1, 0.1), 0.0, 1.0)

            judge_passed = judge_score >= 0.6  # Threshold for passing
            judge_grade = (
                "S"
                if judge_score >= 1.0
                else "A"
                if judge_score >= 0.8
                else "B"
                if judge_score >= 0.6
                else "C"
                if judge_score >= 0.4
                else "D"
                if judge_score >= 0.2
                else "F"
            )

            data.append(
                {
                    "experiment": row["experiment"],
                    "agent_model": row["agent_model"],
                    "tier": row["tier"],
                    "subtest": row["subtest"],
                    "run_number": row["run_number"],
                    "judge_number": judge_idx,
                    "judge_model": judge_model,
                    "judge_score": judge_score,
                    "judge_impl_rate": judge_impl_rate,
                    "judge_passed": judge_passed,
                    "judge_grade": judge_grade,
                    "judge_is_valid": True,
                    "judge_reasoning": f"Judge {judge_idx} evaluation",
                }
            )

    return pd.DataFrame(data)


@pytest.fixture
def sample_criteria_df(sample_judges_df):
    """Sample criteria DataFrame (5 criteria per judge)."""
    np.random.seed(42)
    data = []

    criteria = [
        "functional",
        "code_quality",
        "proportionality",
        "build_pipeline",
        "overall_quality",
    ]

    for idx, row in sample_judges_df.iterrows():
        for criterion in criteria:
            # Generate correlated scores (± 0.15 from judge score)
            criterion_score = np.clip(row["judge_score"] + np.random.uniform(-0.15, 0.15), 0.0, 1.0)
            # Generate achieved and max points based on criterion score
            max_points = 10.0  # Example max points
            criterion_achieved = criterion_score * max_points

            data.append(
                {
                    "experiment": row["experiment"],
                    "agent_model": row["agent_model"],
                    "tier": row["tier"],
                    "subtest": row["subtest"],
                    "run_number": row["run_number"],
                    "judge_number": row["judge_number"],
                    "judge_model": row["judge_model"],
                    "criterion": criterion,
                    "criterion_score": criterion_score,
                    "criterion_achieved": criterion_achieved,
                    "criterion_max": max_points,
                }
            )

    return pd.DataFrame(data)


@pytest.fixture
def sample_subtests_df(sample_runs_df):
    """Sample subtests DataFrame matching production build_subtests_df schema.

    Must match columns produced by dataframes.build_subtests_df().
    """
    from scylla.analysis.stats import compute_consistency, compute_cop

    def compute_subtest_stats(group):
        """Compute statistics for a subtest group (matches production)."""
        pass_rate = group["passed"].mean()
        mean_score = group["score"].mean()
        median_score = group["score"].median()
        std_score = group["score"].std()

        # Impl-rate statistics
        mean_impl_rate = group["impl_rate"].mean() if "impl_rate" in group.columns else np.nan
        median_impl_rate = group["impl_rate"].median() if "impl_rate" in group.columns else np.nan
        std_impl_rate = group["impl_rate"].std() if "impl_rate" in group.columns else np.nan

        # Consistency
        consistency = compute_consistency(mean_score, std_score)

        # Cost metrics
        mean_cost = group["cost_usd"].mean()
        total_cost = group["cost_usd"].sum()
        mean_duration = group["duration_seconds"].mean()
        cop = compute_cop(mean_cost, pass_rate)

        # Grade distribution
        grade_counts = group["grade"].value_counts().to_dict()
        grade_s = grade_counts.get("S", 0)
        grade_a = grade_counts.get("A", 0)
        grade_b = grade_counts.get("B", 0)
        grade_c = grade_counts.get("C", 0)
        grade_d = grade_counts.get("D", 0)
        grade_f = grade_counts.get("F", 0)

        # Modal grade
        mode_result = group["grade"].mode()
        modal_grade = mode_result[0] if len(mode_result) > 0 else "F"

        return pd.Series(
            {
                "pass_rate": pass_rate,
                "mean_score": mean_score,
                "median_score": median_score,
                "std_score": std_score,
                "mean_impl_rate": mean_impl_rate,
                "median_impl_rate": median_impl_rate,
                "std_impl_rate": std_impl_rate,
                "consistency": consistency,
                "mean_cost": mean_cost,
                "total_cost": total_cost,
                "mean_duration": mean_duration,
                "cop": cop,
                "grade_S": grade_s,
                "grade_A": grade_a,
                "grade_B": grade_b,
                "grade_C": grade_c,
                "grade_D": grade_d,
                "grade_F": grade_f,
                "modal_grade": modal_grade,
            }
        )

    # Group by experiment, agent_model, tier, subtest (same as production)
    grouped = sample_runs_df.groupby(["experiment", "agent_model", "tier", "subtest"])
    return grouped.apply(compute_subtest_stats, include_groups=False).reset_index()


# Degenerate input fixtures for edge case testing
@pytest.fixture
def degenerate_single_element():
    """Single-element array for testing n=1 edge cases."""
    return np.array([0.5])


@pytest.fixture
def degenerate_all_same():
    """Array with all identical values for testing zero variance."""
    return np.array([0.7, 0.7, 0.7, 0.7, 0.7])


@pytest.fixture
def degenerate_all_pass():
    """Array with all passing (1) values."""
    return np.array([1, 1, 1, 1, 1])


@pytest.fixture
def degenerate_all_fail():
    """Array with all failing (0) values."""
    return np.array([0, 0, 0, 0, 0])


@pytest.fixture
def degenerate_unbalanced_groups():
    """Two groups with severely unbalanced sizes (n1=2, n2=50)."""
    return {
        "small": np.array([0.3, 0.4]),
        "large": np.random.RandomState(42).uniform(0.5, 0.9, size=50),
    }


@pytest.fixture
def degenerate_empty_array():
    """Empty array for testing n=0 edge cases."""
    return np.array([])


@pytest.fixture
def degenerate_nan_values():
    """Array containing NaN values for testing missing data handling."""
    return np.array([0.5, np.nan, 0.7, np.nan, 0.9])


@pytest.fixture
def degenerate_inf_values():
    """Array containing infinite values for testing boundary conditions."""
    return np.array([0.5, 0.7, np.inf, 0.9, -np.inf])


@pytest.fixture
def degenerate_binary_data():
    """Binary (0/1) data for testing categorical/boolean edge cases."""
    return np.array([0, 1, 0, 1, 1, 0, 0, 1])


@pytest.fixture
def degenerate_boundary_values():
    """Return data at exact boundaries (0.0, 1.0) for testing threshold logic."""
    return np.array([0.0, 0.0, 1.0, 1.0, 0.5])


@pytest.fixture
def degenerate_near_zero():
    """Very small positive values for testing numerical stability."""
    return np.array([1e-10, 1e-9, 1e-8, 1e-7, 1e-6])


@pytest.fixture
def degenerate_high_variance():
    """Return data with extremely high variance for testing statistical robustness."""
    return np.array([0.01, 0.02, 0.98, 0.99, 0.5])
