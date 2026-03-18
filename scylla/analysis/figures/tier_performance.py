"""Tier performance figures.

Generates Fig 4 (pass-rate), Fig 5 (grade heatmap), Fig 31 (experiment-tier heatmap),
Fig 32 (tier win count), and Fig 33 (convergence analysis).
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd

from scylla.analysis.config import config
from scylla.analysis.figures import derive_tier_order, get_color_scale
from scylla.analysis.figures.spec_builder import save_figure


def fig04_pass_rate_by_tier(
    runs_df: pd.DataFrame,
    output_dir: Path,
    render: bool = True,
    pass_threshold: float | None = None,
) -> None:
    """Generate Fig 4: Pass-Rate by Tier.

    Histogram showing score distribution with 0.05 bin width and reference line at pass_threshold,
    one subfigure per tier.

    Args:
        runs_df: Runs DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF
        pass_threshold: Reference line threshold (default: from config.yaml)

    """
    # Use config default if not provided
    if pass_threshold is None:
        pass_threshold = config.pass_threshold

    # Prepare data
    data = runs_df[["tier", "score"]].copy()

    # Derive tier order from data
    tier_order = derive_tier_order(data)

    # Build reference line data with tier column (one row per tier)
    ref_data = pd.DataFrame([{"tier": tier, "threshold": pass_threshold} for tier in tier_order])

    # Create histogram with 0.05 bin width
    histogram = (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=alt.X("score:Q", bin=alt.Bin(step=0.05), title="Score"),
            y=alt.Y("count():Q", title="Count"),
        )
    )

    # Create reference line at pass_threshold
    threshold_line = (
        alt.Chart(ref_data).mark_rule(color="red", strokeDash=[5, 5]).encode(x="threshold:Q")
    )

    # Layer histogram and reference line, then facet by tier
    chart = (
        alt.layer(histogram, threshold_line)
        .facet(column=alt.Column("tier:N", title="Tier", sort=tier_order), data=data)
        .properties(title="Score Distribution per Tier (Pass Threshold Marked)")
    )

    save_figure(chart, "fig04_pass_rate_by_tier", output_dir, render)


def fig05_grade_heatmap(runs_df: pd.DataFrame, output_dir: Path, render: bool = True) -> None:
    """Generate Fig 5: Grade Distribution Heatmap.

    Heatmap showing proportion of each grade per tier.

    Args:
        runs_df: Runs DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Compute grade proportions
    grade_counts = (
        runs_df.groupby(["agent_model", "tier", "grade"]).size().reset_index(name="count")
    )

    # Calculate proportions
    grade_counts["total"] = grade_counts.groupby(["agent_model", "tier"])["count"].transform("sum")
    grade_counts["proportion"] = grade_counts["count"] / grade_counts["total"]

    # Derive tier order from data
    tier_order = derive_tier_order(grade_counts)
    # Get canonical grade order from config
    grade_order = config.grade_order

    # Create heatmap
    heatmap = (
        alt.Chart(grade_counts)
        .mark_rect()
        .encode(
            x=alt.X("grade:O", title="Grade", sort=grade_order),
            y=alt.Y("tier:O", title="Tier", sort=tier_order),
            color=alt.Color(
                "proportion:Q",
                title="Proportion",
                scale=alt.Scale(scheme="viridis", domain=[0, 1]),
            ),
            tooltip=[
                alt.Tooltip("tier:O", title="Tier"),
                alt.Tooltip("grade:O", title="Grade"),
                alt.Tooltip("count:Q", title="Count"),
                alt.Tooltip("proportion:Q", title="Proportion", format=".2%"),
            ],
        )
    )

    # Add text annotations with better contrast for viridis colormap
    # Viridis goes dark purple (0.0) -> green (0.5) -> yellow (1.0)
    # Use white text for dark colors (proportion < 0.7), black for light colors
    text = (
        alt.Chart(grade_counts)
        .mark_text(baseline="middle", fontSize=12)
        .encode(
            x=alt.X("grade:O", sort=grade_order),
            y=alt.Y("tier:O", sort=tier_order),
            text=alt.Text("count:Q"),
            color=alt.condition(
                alt.datum.proportion > 0.7,  # Black text only on light yellow backgrounds
                alt.value("black"),
                alt.value("white"),  # White text on dark purple/green backgrounds
            ),
        )
    )

    # Combine and facet
    chart = (
        (heatmap + text)
        .facet(column=alt.Column("agent_model:N", title=None))
        .properties(
            title={
                "text": "Grade Distribution Heatmap by Tier",
                "subtitle": "Empty cells indicate no runs with that grade for the tier",
            }
        )
    )

    save_figure(chart, "fig05_grade_heatmap", output_dir, render)


def fig31_experiment_tier_heatmap(
    runs_df: pd.DataFrame, output_dir: Path, render: bool = True
) -> None:
    """Generate Fig 31: Experiment-Tier Pass Rate Heatmap.

    Heatmap with experiments on Y axis, tiers on X axis, colored by pass rate.
    Shows tier ranking stability across diverse tasks.

    Args:
        runs_df: Runs DataFrame (must contain 'experiment', 'tier', 'passed')
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    tier_order = derive_tier_order(runs_df)

    # Compute pass rate per (experiment, tier)
    pass_rates = (
        runs_df.groupby(["experiment", "tier"])["passed"]
        .mean()
        .reset_index()
        .rename(columns={"passed": "pass_rate"})
    )

    # Sort experiments naturally
    exp_order = sorted(pass_rates["experiment"].unique())

    heatmap = (
        alt.Chart(pass_rates)
        .mark_rect()
        .encode(
            x=alt.X("tier:O", title="Tier", sort=tier_order),
            y=alt.Y("experiment:O", title="Experiment", sort=exp_order),
            color=alt.Color(
                "pass_rate:Q",
                title="Pass Rate",
                scale=alt.Scale(scheme="viridis", domain=[0, 1]),
            ),
            tooltip=[
                alt.Tooltip("experiment:O", title="Experiment"),
                alt.Tooltip("tier:O", title="Tier"),
                alt.Tooltip("pass_rate:Q", title="Pass Rate", format=".2%"),
            ],
        )
        .properties(
            title="Pass Rate by Experiment and Tier",
            height=max(300, len(exp_order) * 14),
        )
    )

    save_figure(heatmap, "fig31_experiment_tier_heatmap", output_dir, render)

    # Export data
    csv_path = output_dir / "fig31_experiment_tier_heatmap.csv"
    pass_rates.to_csv(csv_path, index=False)


def fig32_tier_win_count(runs_df: pd.DataFrame, output_dir: Path, render: bool = True) -> None:
    """Generate Fig 32: Tier Win Count Bar Chart.

    For each tier, count how many experiments it wins (highest pass rate).

    Args:
        runs_df: Runs DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    tier_order = derive_tier_order(runs_df)

    # Compute pass rate per (experiment, tier)
    pass_rates = (
        runs_df.groupby(["experiment", "tier"])["passed"]
        .mean()
        .reset_index()
        .rename(columns={"passed": "pass_rate"})
    )

    # Find winning tier per experiment (ties: all winners counted)
    wins: dict[str, int] = dict.fromkeys(tier_order, 0)
    for exp in pass_rates["experiment"].unique():
        exp_data = pass_rates[pass_rates["experiment"] == exp]
        max_rate = exp_data["pass_rate"].max()
        winning_tiers = exp_data[exp_data["pass_rate"] == max_rate]["tier"]
        for tier in winning_tiers:
            wins[tier] = wins.get(tier, 0) + 1

    win_df = pd.DataFrame([{"tier": tier, "wins": count} for tier, count in wins.items()])

    domain, range_ = get_color_scale("tiers", tier_order)

    chart = (
        alt.Chart(win_df)
        .mark_bar()
        .encode(
            x=alt.X("tier:O", title="Tier", sort=tier_order),
            y=alt.Y("wins:Q", title="Number of Experiment Wins"),
            color=alt.Color(
                "tier:O",
                scale=alt.Scale(domain=domain, range=range_),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("tier:O", title="Tier"),
                alt.Tooltip("wins:Q", title="Wins"),
            ],
        )
        .properties(title="Tier Win Count Across Experiments")
    )

    save_figure(chart, "fig32_tier_win_count", output_dir, render)

    csv_path = output_dir / "fig32_tier_win_count.csv"
    win_df.to_csv(csv_path, index=False)


def fig33_convergence_analysis(
    runs_df: pd.DataFrame, output_dir: Path, render: bool = True
) -> None:
    """Generate Fig 33: Convergence Analysis.

    Running mean pass rate per tier as experiments are added 1 to N.
    Shows whether N tests is sufficient (curves should flatten).

    Args:
        runs_df: Runs DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    tier_order = derive_tier_order(runs_df)
    exp_order = sorted(runs_df["experiment"].unique())

    if len(exp_order) < 2:
        return  # Need at least 2 experiments for convergence

    # Compute pass rate per (experiment, tier)
    pass_rates = (
        runs_df.groupby(["experiment", "tier"])["passed"]
        .mean()
        .reset_index()
        .rename(columns={"passed": "pass_rate"})
    )

    # Build running mean: for each tier, accumulate experiments in sorted order
    convergence_rows = []
    for tier in tier_order:
        tier_data = pass_rates[pass_rates["tier"] == tier].set_index("experiment")
        cumulative_rates: list[float] = []
        for i, exp in enumerate(exp_order, 1):
            if exp in tier_data.index:
                cumulative_rates.append(tier_data.loc[exp, "pass_rate"])
            if cumulative_rates:
                convergence_rows.append(
                    {
                        "tier": tier,
                        "n_experiments": i,
                        "running_mean": float(np.mean(cumulative_rates)),
                    }
                )

    convergence_df = pd.DataFrame(convergence_rows)

    domain, range_ = get_color_scale("tiers", tier_order)

    chart = (
        alt.Chart(convergence_df)
        .mark_line()
        .encode(
            x=alt.X("n_experiments:Q", title="Number of Experiments"),
            y=alt.Y(
                "running_mean:Q",
                title="Running Mean Pass Rate",
                scale=alt.Scale(domain=[0, 1]),
            ),
            color=alt.Color(
                "tier:O",
                title="Tier",
                sort=tier_order,
                scale=alt.Scale(domain=domain, range=range_),
            ),
            tooltip=[
                alt.Tooltip("tier:O", title="Tier"),
                alt.Tooltip("n_experiments:Q", title="Experiments"),
                alt.Tooltip("running_mean:Q", title="Running Mean", format=".3f"),
            ],
        )
        .properties(title="Convergence: Running Mean Pass Rate by Tier")
    )

    save_figure(chart, "fig33_convergence_analysis", output_dir, render)

    csv_path = output_dir / "fig33_convergence_analysis.csv"
    convergence_df.to_csv(csv_path, index=False)
