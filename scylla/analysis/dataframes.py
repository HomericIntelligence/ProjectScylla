"""DataFrame construction and aggregation helpers.

Converts loaded experiment data into pandas DataFrames for analysis.
Provides aggregation functions for computing tier, subtest, and judge statistics.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from scylla.analysis.loader import JudgeEvaluation, RunData
from scylla.analysis.stats import compute_consistency, compute_cop, compute_impl_rate

__all__ = [
    "build_criteria_df",
    "build_judges_df",
    "build_runs_df",
    "build_subtests_df",
    "compute_consensus_impl_rate",
    "compute_judge_impl_rate",
    "criteria_summary",
    "judge_summary",
    "model_comparison",
    "tier_summary",
]


def _compute_delegation_cost_ratio(run: RunData) -> float | None:
    """Compute ratio of delegated model cost to primary model cost.

    Returns None if model_usage data is not available or has < 2 models.

    Args:
        run: Run data with optional model_usage field

    Returns:
        Delegation cost ratio (0.0 to 1.0) or None

    """
    if not run.model_usage or len(run.model_usage) < 2:
        return None

    total_cost = sum(u.cost_usd for u in run.model_usage)
    if total_cost == 0:
        return None

    # Primary model = first in list (highest cost typically)
    primary_cost = run.model_usage[0].cost_usd
    delegated_cost = total_cost - primary_cost
    return delegated_cost / total_cost


def compute_judge_impl_rate(judge: JudgeEvaluation) -> float:
    """Compute implementation rate for a single judge.

    Gracefully handles data quality issues:
    - String values in achieved/max_points are coerced to float
    - Invalid values (non-numeric strings) are treated as 0.0
    - This defensive approach ensures analysis continues despite source data issues
    - PRINCIPLE: Never modify source data, make analysis code robust

    Args:
        judge: Judge evaluation with criteria scores

    Returns:
        Implementation rate (achieved / max_points)

    """

    # Defensive data loading: coerce to float, treating invalid values as 0.0
    # This handles cases where judgment data has string values like "N/A" or numeric strings
    def safe_float(value: Any, default: float = 0.0) -> float:
        """Convert value to float, returning default for invalid inputs."""
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    total_achieved = sum(safe_float(criterion.achieved) for criterion in judge.criteria.values())
    total_max = sum(safe_float(criterion.max_points) for criterion in judge.criteria.values())
    return compute_impl_rate(total_achieved, total_max)


def compute_consensus_impl_rate(judges: list[JudgeEvaluation]) -> float:
    """Compute consensus implementation rate across judges (median).

    Args:
        judges: List of judge evaluations

    Returns:
        Median implementation rate across judges, or NaN if no judges

    """
    if not judges:
        return np.nan

    judge_impl_rates = [compute_judge_impl_rate(judge) for judge in judges]
    return float(np.median(judge_impl_rates))


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
            # Consensus impl_rate: median across judges (matching consensus score logic)
            consensus_impl_rate = compute_consensus_impl_rate(run.judges)

            rows.append(
                {
                    "experiment": run.experiment,
                    "agent_model": run.agent_model,
                    "tier": run.tier,
                    "subtest": run.subtest,
                    "run_number": run.run_number,
                    "score": run.score,
                    "impl_rate": consensus_impl_rate,
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
                    # Optional delegation metrics (T3-T6)
                    "api_calls": run.api_calls,
                    "num_turns": run.num_turns,
                    "num_models": len(run.model_usage) if run.model_usage else None,
                    "delegation_cost_ratio": _compute_delegation_cost_ratio(run),
                    # Optional process metrics (R_Prog, CFP, PR revert rate, strategic drift)
                    "r_prog": run.r_prog,
                    "strategic_drift": run.strategic_drift,
                    "cfp": run.cfp,
                    "pr_revert_rate": run.pr_revert_rate,
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
                # Calculate impl_rate for this judge
                judge_impl_rate = compute_judge_impl_rate(judge)

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
                        "judge_impl_rate": judge_impl_rate,
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

        # Implementation Rate statistics
        mean_impl_rate = group["impl_rate"].mean()
        median_impl_rate = group["impl_rate"].median()
        std_impl_rate = group["impl_rate"].std()

        # Consistency: 1 - coefficient of variation (clamped to [0, 1])
        consistency = compute_consistency(mean_score, std_score)

        mean_cost = group["cost_usd"].mean()
        total_cost = group["cost_usd"].sum()
        mean_duration = group["duration_seconds"].mean()

        # Cost-of-Pass: mean_cost / pass_rate (infinity if pass_rate == 0)
        cop = compute_cop(mean_cost, pass_rate)

        # Process metrics (nullable — NaN when data not yet collected)
        mean_r_prog = group["r_prog"].mean()
        median_r_prog = group["r_prog"].median()
        std_r_prog = group["r_prog"].std()
        mean_cfp = group["cfp"].mean()
        median_cfp = group["cfp"].median()
        std_cfp = group["cfp"].std()
        mean_pr_revert_rate = group["pr_revert_rate"].mean()
        median_pr_revert_rate = group["pr_revert_rate"].median()
        std_pr_revert_rate = group["pr_revert_rate"].std()
        mean_strategic_drift = group["strategic_drift"].mean()
        median_strategic_drift = group["strategic_drift"].median()
        std_strategic_drift = group["strategic_drift"].std()

        # Grade distribution
        grade_counts = group["grade"].value_counts().to_dict()
        grade_s = grade_counts.get("S", 0)
        grade_a = grade_counts.get("A", 0)
        grade_b = grade_counts.get("B", 0)
        grade_c = grade_counts.get("C", 0)
        grade_d = grade_counts.get("D", 0)
        grade_f = grade_counts.get("F", 0)

        # Modal grade (handle case where mode() returns empty Series)
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
                "mean_r_prog": mean_r_prog,
                "median_r_prog": median_r_prog,
                "std_r_prog": std_r_prog,
                "mean_cfp": mean_cfp,
                "median_cfp": median_cfp,
                "std_cfp": std_cfp,
                "mean_pr_revert_rate": mean_pr_revert_rate,
                "median_pr_revert_rate": median_pr_revert_rate,
                "std_pr_revert_rate": std_pr_revert_rate,
                "mean_strategic_drift": mean_strategic_drift,
                "median_strategic_drift": median_strategic_drift,
                "std_strategic_drift": std_strategic_drift,
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
        mean_impl_rate = group["impl_rate"].mean()
        median_impl_rate = group["impl_rate"].median()
        std_impl_rate = group["impl_rate"].std()
        consistency = compute_consistency(mean_score, std_score)
        mean_cost = group["cost_usd"].mean()
        total_cost = group["cost_usd"].sum()
        cop = compute_cop(mean_cost, pass_rate)

        # Process metrics (nullable — NaN when data not yet collected)
        mean_r_prog = group["r_prog"].mean()
        median_r_prog = group["r_prog"].median()
        std_r_prog = group["r_prog"].std()
        mean_cfp = group["cfp"].mean()
        median_cfp = group["cfp"].median()
        std_cfp = group["cfp"].std()
        mean_pr_revert_rate = group["pr_revert_rate"].mean()
        median_pr_revert_rate = group["pr_revert_rate"].median()
        std_pr_revert_rate = group["pr_revert_rate"].std()
        mean_strategic_drift = group["strategic_drift"].mean()
        median_strategic_drift = group["strategic_drift"].median()
        std_strategic_drift = group["strategic_drift"].std()

        return pd.Series(
            {
                "num_runs": len(group),
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
                "cop": cop,
                "mean_r_prog": mean_r_prog,
                "median_r_prog": median_r_prog,
                "std_r_prog": std_r_prog,
                "mean_cfp": mean_cfp,
                "median_cfp": median_cfp,
                "std_cfp": std_cfp,
                "mean_pr_revert_rate": mean_pr_revert_rate,
                "median_pr_revert_rate": median_pr_revert_rate,
                "std_pr_revert_rate": std_pr_revert_rate,
                "mean_strategic_drift": mean_strategic_drift,
                "median_strategic_drift": median_strategic_drift,
                "std_strategic_drift": std_strategic_drift,
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
