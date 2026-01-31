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
                    grade = (
                        np.random.choice(["S", "A", "B"])
                        if passed
                        else np.random.choice(["C", "D", "F"])
                    )
                    cost = np.random.uniform(0.01, 0.1)
                    tokens_in = np.random.randint(1000, 10000)
                    tokens_out = np.random.randint(500, 5000)
                    latency = np.random.uniform(5.0, 30.0)

                    # Calculate CoP and consistency for completeness
                    consistency = 1 - (np.random.uniform(0.05, 0.15) / score) if score > 0 else 0
                    consistency = max(0.0, min(1.0, consistency))

                    # Total tokens for model_comparison
                    total_tokens = tokens_in + tokens_out

                    # Duration (alias for latency for compatibility)
                    duration_seconds = latency

                    data.append(
                        {
                            "experiment": f"test001-{model.lower().replace(' ', '-')}",
                            "agent_model": model,
                            "tier": tier,
                            "subtest": subtest,
                            "run_number": run,
                            "passed": passed,
                            "score": score,
                            "grade": grade,
                            "cost_usd": cost,
                            "tokens_in": tokens_in,
                            "tokens_out": tokens_out,
                            "total_tokens": total_tokens,
                            "latency_seconds": latency,
                            "duration_seconds": duration_seconds,
                            "consistency": consistency,
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

            data.append(
                {
                    "experiment": row["experiment"],
                    "agent_model": row["agent_model"],
                    "tier": row["tier"],
                    "subtest": row["subtest"],
                    "run_number": row["run_number"],
                    "judge_number": judge_idx,
                    "judge_model": judge_model,
                    "score": judge_score,
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
            criterion_score = np.clip(row["score"] + np.random.uniform(-0.15, 0.15), 0.0, 1.0)

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
                    "score": criterion_score,
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
                "tokens_in": "sum",
                "tokens_out": "sum",
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
        "total_tokens_in",
        "total_tokens_out",
    ]

    return aggregated
