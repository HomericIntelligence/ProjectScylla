"""DataFrame construction and aggregation helpers.

Converts loaded experiment data into pandas DataFrames for analysis.
Provides aggregation functions for computing tier, subtest, and judge statistics.

Python Justification: pandas is a Python-only library with no Mojo equivalent.
"""

from __future__ import annotations

import pandas as pd

from scylla.analysis.loader import RunData


def build_runs_df(experiments: dict[str, list[RunData]]) -> pd.DataFrame:
    """Build runs DataFrame with one row per run.

    Args:
        experiments: Dictionary mapping experiment name to list of runs

    Returns:
        DataFrame with ~2260 rows (113 subtests × 10 runs × 2 models)

    """
    rows = []
    for runs in experiments.values():
        for run in runs:
            rows.append(
                {
                    "experiment": run.experiment,
                    "agent_model": run.agent_model,
                    "tier": run.tier,
                    "subtest": run.subtest,
                    "run_number": run.run_number,
                    "score": run.score,
                    "passed": run.passed,
                    "grade": run.grade,
                    "cost_usd": run.cost_usd,
                    "duration_seconds": run.duration_seconds,
                    "agent_duration_seconds": run.agent_duration_seconds,
                    "judge_duration_seconds": run.judge_duration_seconds,
                    "input_tokens": run.token_stats.input_tokens,
                    "output_tokens": run.token_stats.output_tokens,
                    "cache_creation_tokens": run.token_stats.cache_creation_tokens,
                    "cache_read_tokens": run.token_stats.cache_read_tokens,
                    "total_tokens": run.token_stats.total_tokens,
                    "exit_code": run.exit_code,
                }
            )

    return pd.DataFrame(rows)


def build_judges_df(experiments: dict[str, list[RunData]]) -> pd.DataFrame:
    """Build judges DataFrame with one row per (run, judge).

    Args:
        experiments: Dictionary mapping experiment name to list of runs

    Returns:
        DataFrame with ~6780 rows (2260 runs × 3 judges)

    """
    rows = []
    for runs in experiments.values():
        for run in runs:
            for judge in run.judges:
                rows.append(
                    {
                        "experiment": run.experiment,
                        "agent_model": run.agent_model,
                        "tier": run.tier,
                        "subtest": run.subtest,
                        "run_number": run.run_number,
                        "judge_model": judge.judge_model,
                        "judge_number": judge.judge_number,
                        "judge_score": judge.score,
                        "judge_passed": judge.passed,
                        "judge_grade": judge.grade,
                        "judge_is_valid": judge.is_valid,
                        "judge_reasoning": judge.reasoning,
                    }
                )

    return pd.DataFrame(rows)


def build_criteria_df(experiments: dict[str, list[RunData]]) -> pd.DataFrame:
    """Build criteria DataFrame with one row per (run, judge, criterion).

    Args:
        experiments: Dictionary mapping experiment name to list of runs

    Returns:
        DataFrame with ~33,900 rows (6780 judge evaluations × 5 criteria)

    """
    rows = []
    for runs in experiments.values():
        for run in runs:
            for judge in run.judges:
                for criterion_name, criterion in judge.criteria.items():
                    rows.append(
                        {
                            "experiment": run.experiment,
                            "agent_model": run.agent_model,
                            "tier": run.tier,
                            "subtest": run.subtest,
                            "run_number": run.run_number,
                            "judge_model": judge.judge_model,
                            "judge_number": judge.judge_number,
                            "criterion": criterion_name,
                            "criterion_score": criterion.score,
                            "criterion_achieved": criterion.achieved,
                            "criterion_max": criterion.max_points,
                        }
                    )

    return pd.DataFrame(rows)


def build_subtests_df(runs_df: pd.DataFrame) -> pd.DataFrame:
    """Build pre-aggregated subtests DataFrame.

    Args:
        runs_df: Runs DataFrame from build_runs_df()

    Returns:
        DataFrame with one row per (experiment, tier, subtest)

    """

    def compute_subtest_stats(group: pd.DataFrame) -> pd.Series:
        """Compute statistics for a single subtest."""
        pass_rate = group["passed"].mean()
        mean_score = group["score"].mean()
        median_score = group["score"].median()
        std_score = group["score"].std()

        # Consistency: 1 - coefficient of variation
        consistency = 1 - (std_score / mean_score) if mean_score > 0 else 0.0

        mean_cost = group["cost_usd"].mean()
        total_cost = group["cost_usd"].sum()
        mean_duration = group["duration_seconds"].mean()

        # Cost-of-Pass: mean_cost / pass_rate (infinity if pass_rate == 0)
        cop = mean_cost / pass_rate if pass_rate > 0 else float("inf")

        # Grade distribution
        grade_counts = group["grade"].value_counts().to_dict()
        grade_s = grade_counts.get("S", 0)
        grade_a = grade_counts.get("A", 0)
        grade_b = grade_counts.get("B", 0)
        grade_c = grade_counts.get("C", 0)
        grade_d = grade_counts.get("D", 0)
        grade_f = grade_counts.get("F", 0)

        # Modal grade
        modal_grade = group["grade"].mode()[0] if len(group) > 0 else "F"

        return pd.Series(
            {
                "pass_rate": pass_rate,
                "mean_score": mean_score,
                "median_score": median_score,
                "std_score": std_score,
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

    # Group by experiment, agent_model, tier, subtest
    grouped = runs_df.groupby(["experiment", "agent_model", "tier", "subtest"])
    stats = grouped.apply(compute_subtest_stats, include_groups=False).reset_index()

    return stats


def tier_summary(runs_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate runs by tier.

    Args:
        runs_df: Runs DataFrame

    Returns:
        DataFrame with one row per (agent_model, tier)

    """
    grouped = runs_df.groupby(["agent_model", "tier"])

    def compute_tier_stats(group: pd.DataFrame) -> pd.Series:
        pass_rate = group["passed"].mean()
        mean_score = group["score"].mean()
        median_score = group["score"].median()
        std_score = group["score"].std()
        consistency = 1 - (std_score / mean_score) if mean_score > 0 else 0.0
        mean_cost = group["cost_usd"].mean()
        total_cost = group["cost_usd"].sum()
        cop = mean_cost / pass_rate if pass_rate > 0 else float("inf")

        return pd.Series(
            {
                "num_runs": len(group),
                "pass_rate": pass_rate,
                "mean_score": mean_score,
                "median_score": median_score,
                "std_score": std_score,
                "consistency": consistency,
                "mean_cost": mean_cost,
                "total_cost": total_cost,
                "cop": cop,
            }
        )

    return grouped.apply(compute_tier_stats, include_groups=False).reset_index()


def judge_summary(judges_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate by judge model.

    Args:
        judges_df: Judges DataFrame

    Returns:
        DataFrame with one row per judge_model

    """
    grouped = judges_df.groupby("judge_model")

    return grouped.agg(
        {
            "judge_score": ["mean", "median", "std", "min", "max"],
            "judge_passed": "mean",
        }
    ).reset_index()


def criteria_summary(criteria_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate by criterion.

    Args:
        criteria_df: Criteria DataFrame

    Returns:
        DataFrame with one row per (agent_model, tier, criterion)

    """
    grouped = criteria_df.groupby(["agent_model", "tier", "criterion"])

    return grouped.agg(
        {
            "criterion_score": ["mean", "std", "median"],
            "criterion_achieved": "sum",
            "criterion_max": "sum",
        }
    ).reset_index()


def model_comparison(runs_df: pd.DataFrame) -> pd.DataFrame:
    """Compare performance between agent models.

    Args:
        runs_df: Runs DataFrame

    Returns:
        DataFrame with one row per (agent_model, tier)

    """
    grouped = runs_df.groupby(["agent_model", "tier"])

    return grouped.agg(
        {
            "passed": "mean",
            "score": ["mean", "median", "std"],
            "cost_usd": ["mean", "sum"],
            "duration_seconds": "mean",
            "total_tokens": ["mean", "sum"],
        }
    ).reset_index()
