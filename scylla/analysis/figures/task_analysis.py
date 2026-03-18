"""Task-level analysis figures for multi-experiment datasets.

Generates Fig 35 (task difficulty distribution), Fig 36 (tier rank stability heatmap),
Fig 37 (task complexity vs tier differentiation), and Fig 38 (full-ablation comparison).
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd

from scylla.analysis.figures import derive_tier_order, get_color_scale
from scylla.analysis.figures.spec_builder import save_figure


def fig35_task_difficulty_distribution(
    runs_df: pd.DataFrame, output_dir: Path, render: bool = True
) -> None:
    """Generate Fig 35: Task Difficulty Distribution.

    Histogram of per-experiment overall pass rates across all experiments.
    Shows the difficulty spectrum of the test suite.

    Args:
        runs_df: Runs DataFrame (must contain 'experiment', 'passed')
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    if "experiment" not in runs_df.columns or "passed" not in runs_df.columns:
        return

    # Compute overall pass rate per experiment
    exp_pass_rates = (
        runs_df.groupby("experiment")["passed"]
        .mean()
        .reset_index()
        .rename(columns={"passed": "pass_rate"})
    )

    if len(exp_pass_rates) < 2:
        return  # Need multiple experiments for a meaningful histogram

    chart = (
        alt.Chart(exp_pass_rates)
        .mark_bar()
        .encode(
            x=alt.X(
                "pass_rate:Q",
                bin=alt.Bin(step=0.1),
                title="Overall Pass Rate",
                scale=alt.Scale(domain=[0, 1]),
            ),
            y=alt.Y("count():Q", title="Number of Experiments"),
            tooltip=[
                alt.Tooltip("pass_rate:Q", bin=alt.Bin(step=0.1), title="Pass Rate Bin"),
                alt.Tooltip("count():Q", title="Count"),
            ],
        )
        .properties(title="Task Difficulty Distribution (Pass Rate per Experiment)")
    )

    save_figure(chart, "fig35_task_difficulty_distribution", output_dir, render)

    csv_path = output_dir / "fig35_task_difficulty_distribution.csv"
    exp_pass_rates.to_csv(csv_path, index=False)


def fig36_tier_rank_stability(runs_df: pd.DataFrame, output_dir: Path, render: bool = True) -> None:
    """Generate Fig 36: Tier Rank Stability Heatmap.

    Heatmap showing tier rank (1=best, 7=worst) per experiment, sorted by difficulty.
    Visualizes whether tier ordering is consistent across tasks.

    Args:
        runs_df: Runs DataFrame (must contain 'experiment', 'tier', 'passed')
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    required = {"experiment", "tier", "passed"}
    if not required.issubset(runs_df.columns):
        return

    tier_order = derive_tier_order(runs_df)

    # Compute pass rate per (experiment, tier)
    pass_rates = (
        runs_df.groupby(["experiment", "tier"])["passed"]
        .mean()
        .reset_index()
        .rename(columns={"passed": "pass_rate"})
    )

    # Compute rank per experiment (1=best pass rate, ties get average rank)
    pass_rates["rank"] = pass_rates.groupby("experiment")["pass_rate"].rank(
        ascending=False, method="average"
    )

    # Sort experiments by overall difficulty (mean pass rate across tiers)
    exp_difficulty = (
        pass_rates.groupby("experiment")["pass_rate"].mean().sort_values(ascending=False)
    )
    exp_order = list(exp_difficulty.index)

    n_tiers = len(tier_order)

    heatmap = (
        alt.Chart(pass_rates)
        .mark_rect()
        .encode(
            x=alt.X("tier:O", title="Tier", sort=tier_order),
            y=alt.Y("experiment:O", title="Experiment (sorted by difficulty)", sort=exp_order),
            color=alt.Color(
                "rank:Q",
                title="Rank (1=Best)",
                scale=alt.Scale(scheme="redyellowgreen", domain=[n_tiers, 1]),
            ),
            tooltip=[
                alt.Tooltip("experiment:O", title="Experiment"),
                alt.Tooltip("tier:O", title="Tier"),
                alt.Tooltip("pass_rate:Q", title="Pass Rate", format=".2%"),
                alt.Tooltip("rank:Q", title="Rank"),
            ],
        )
        .properties(
            title="Tier Rank Stability Across Experiments",
            height=max(300, len(exp_order) * 14),
        )
    )

    save_figure(heatmap, "fig36_tier_rank_stability", output_dir, render)

    csv_path = output_dir / "fig36_tier_rank_stability.csv"
    pass_rates.to_csv(csv_path, index=False)


def fig37_complexity_vs_differentiation(
    runs_df: pd.DataFrame, output_dir: Path, render: bool = True
) -> None:
    """Generate Fig 37: Task Complexity vs Tier Differentiation.

    Scatter of task difficulty (mean pass rate) vs tier differentiation
    (std dev of tier pass rates). Shows whether harder tasks differentiate tiers more.

    Args:
        runs_df: Runs DataFrame (must contain 'experiment', 'tier', 'passed')
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    required = {"experiment", "tier", "passed"}
    if not required.issubset(runs_df.columns):
        return

    # Compute pass rate per (experiment, tier)
    pass_rates = (
        runs_df.groupby(["experiment", "tier"])["passed"]
        .mean()
        .reset_index()
        .rename(columns={"passed": "pass_rate"})
    )

    # Per-experiment: mean pass rate (difficulty) and std of tier pass rates (differentiation)
    exp_stats = pass_rates.groupby("experiment")["pass_rate"].agg(["mean", "std"]).reset_index()
    exp_stats.columns = ["experiment", "mean_pass_rate", "tier_std"]
    exp_stats["tier_std"] = exp_stats["tier_std"].fillna(0)

    if len(exp_stats) < 2:
        return

    scatter = (
        alt.Chart(exp_stats)
        .mark_circle(size=60, opacity=0.7)
        .encode(
            x=alt.X(
                "mean_pass_rate:Q",
                title="Task Difficulty (Mean Pass Rate)",
                scale=alt.Scale(domain=[0, 1]),
            ),
            y=alt.Y(
                "tier_std:Q",
                title="Tier Differentiation (Std Dev of Tier Pass Rates)",
            ),
            tooltip=[
                alt.Tooltip("experiment:O", title="Experiment"),
                alt.Tooltip("mean_pass_rate:Q", title="Mean Pass Rate", format=".2%"),
                alt.Tooltip("tier_std:Q", title="Tier Std Dev", format=".3f"),
            ],
        )
        .properties(title="Task Complexity vs Tier Differentiation")
    )

    save_figure(scatter, "fig37_complexity_vs_differentiation", output_dir, render)

    csv_path = output_dir / "fig37_complexity_vs_differentiation.csv"
    exp_stats.to_csv(csv_path, index=False)


def fig38_full_ablation_comparison(
    runs_df: pd.DataFrame,
    output_dir: Path,
    render: bool = True,
    full_ablation_experiments: list[str] | None = None,
) -> None:
    """Generate Fig 38: Full-Ablation Comparison.

    Grouped bar chart comparing full-ablation experiments (all subtests)
    vs standard experiments (max 3 subtests). Evaluates whether max_subtests=3
    sampling misses optimal subtests.

    Args:
        runs_df: Runs DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF
        full_ablation_experiments: List of experiment names that used full ablation.
            If None, auto-detects by counting subtests (>3 per tier = full ablation).

    """
    required = {"experiment", "tier", "passed", "subtest"}
    if not required.issubset(runs_df.columns):
        return

    tier_order = derive_tier_order(runs_df)

    # Auto-detect full-ablation experiments if not provided
    if full_ablation_experiments is None:
        subtests_per_exp_tier = (
            runs_df.groupby(["experiment", "tier"])["subtest"].nunique().reset_index()
        )
        # Full ablation = any tier has >3 subtests
        max_subtests = subtests_per_exp_tier.groupby("experiment")["subtest"].max()
        full_ablation_experiments = list(max_subtests[max_subtests > 3].index)

    if not full_ablation_experiments:
        return  # No full-ablation experiments to compare

    # Label experiments
    runs_df = runs_df.copy()
    runs_df["ablation_type"] = runs_df["experiment"].apply(
        lambda e: "Full Ablation" if e in full_ablation_experiments else "Standard (max 3)"
    )

    # Need both types for comparison
    if runs_df["ablation_type"].nunique() < 2:
        return

    # Compute pass rate per (ablation_type, tier)
    comparison = (
        runs_df.groupby(["ablation_type", "tier"])["passed"]
        .mean()
        .reset_index()
        .rename(columns={"passed": "pass_rate"})
    )

    domain, range_ = get_color_scale("tiers", tier_order)

    chart = (
        alt.Chart(comparison)
        .mark_bar()
        .encode(
            x=alt.X("tier:O", title="Tier", sort=tier_order),
            y=alt.Y("pass_rate:Q", title="Pass Rate", scale=alt.Scale(domain=[0, 1])),
            color=alt.Color(
                "tier:O",
                scale=alt.Scale(domain=domain, range=range_),
                legend=None,
            ),
            column=alt.Column("ablation_type:N", title=None),
            tooltip=[
                alt.Tooltip("tier:O", title="Tier"),
                alt.Tooltip("ablation_type:N", title="Type"),
                alt.Tooltip("pass_rate:Q", title="Pass Rate", format=".2%"),
            ],
        )
        .properties(title="Full-Ablation vs Standard Sampling")
    )

    save_figure(chart, "fig38_full_ablation_comparison", output_dir, render)

    csv_path = output_dir / "fig38_full_ablation_comparison.csv"
    comparison.to_csv(csv_path, index=False)
