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
    """Sample subtests DataFrame (pre-aggregated)."""
    aggregated = (
        sample_runs_df.groupby(["experiment", "agent_model", "tier", "subtest"])
        .agg(
            {
                "passed": "mean",
                "score": ["mean", "std"],
                "cost_usd": ["mean", "std"],
                "input_tokens": "sum",
                "output_tokens": "sum",
                "total_tokens": "sum",
            }
        )
        .reset_index()
    )

    # Flatten multi-index columns
    aggregated.columns = [
        "experiment",
        "agent_model",
        "tier",
        "subtest",
        "pass_rate",
        "mean_score",
        "std_score",
        "mean_cost",
        "std_cost",
        "total_input_tokens",
        "total_output_tokens",
        "total_tokens",
    ]

    return aggregated
