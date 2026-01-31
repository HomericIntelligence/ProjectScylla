"""Tier performance figures.

Generates Fig 4 (pass-rate), Fig 5 (grade heatmap), and Fig 10 (score violin).
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd

from scylla.analysis.figures import derive_tier_order, get_color_scale
from scylla.analysis.figures.spec_builder import save_figure
from scylla.analysis.stats import bootstrap_ci


def fig04_pass_rate_by_tier(runs_df: pd.DataFrame, output_dir: Path, render: bool = True) -> None:
    """Generate Fig 4: Pass-Rate by Tier.

    Grouped bar chart with 95% bootstrap confidence intervals.

    Args:
        runs_df: Runs DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Compute pass rate and CI per (agent_model, tier)
    # Derive tier order from data
    tier_order = derive_tier_order(runs_df)

    stats = []
    for model in runs_df["agent_model"].unique():
        for tier in tier_order:
            subset = runs_df[(runs_df["agent_model"] == model) & (runs_df["tier"] == tier)]
            if len(subset) == 0:
                continue

            passed = subset["passed"].astype(int)
            mean, ci_low, ci_high = bootstrap_ci(passed)

            stats.append(
                {
                    "agent_model": model,
                    "tier": tier,
                    "pass_rate": mean,
                    "ci_low": ci_low,
                    "ci_high": ci_high,
                    "ci_error_low": mean - ci_low,
                    "ci_error_high": ci_high - mean,
                }
            )

    stats_df = pd.DataFrame(stats)

    # Get dynamic color scale for models
    models = sorted(stats_df["agent_model"].unique())
    domain, range_ = get_color_scale("models", models)

    # Create grouped bar chart
    bars = (
        alt.Chart(stats_df)
        .mark_bar()
        .encode(
            x=alt.X("tier:O", title="Tier", sort=tier_order),
            y=alt.Y("pass_rate:Q", title="Pass Rate", scale=alt.Scale(domain=[0, 1])),
            color=alt.Color(
                "agent_model:N",
                title="Agent Model",
                scale=alt.Scale(domain=domain, range=range_),
            ),
            xOffset="agent_model:N",
            tooltip=[
                alt.Tooltip("tier:O", title="Tier"),
                alt.Tooltip("agent_model:N", title="Model"),
                alt.Tooltip("pass_rate:Q", title="Pass Rate", format=".2%"),
                alt.Tooltip("ci_low:Q", title="95% CI Low", format=".2%"),
                alt.Tooltip("ci_high:Q", title="95% CI High", format=".2%"),
            ],
        )
    )

    # Error bars
    error_bars = (
        alt.Chart(stats_df)
        .mark_errorbar()
        .encode(
            x=alt.X("tier:O", sort=tier_order),
            y=alt.Y("ci_low:Q", title=""),
            y2="ci_high:Q",
            xOffset="agent_model:N",
        )
    )

    # Reference line at 0.60
    rule_data = pd.DataFrame({"y": [0.60]})
    rule = alt.Chart(rule_data).mark_rule(color="gray", strokeDash=[5, 5]).encode(y="y:Q")

    # Combine layers
    chart = (
        (bars + error_bars + rule)
        .properties(title="Pass Rate by Tier with 95% Confidence Intervals")
        .configure_view(strokeWidth=0)
    )

    save_figure(chart, "fig04_pass_rate_by_tier", output_dir, stats_df, render)


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
    grade_order = ["S", "A", "B", "C", "D", "F"]

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

    # Add text annotations
    text = (
        alt.Chart(grade_counts)
        .mark_text(baseline="middle")
        .encode(
            x=alt.X("grade:O", sort=grade_order),
            y=alt.Y("tier:O", sort=tier_order),
            text=alt.Text("count:Q"),
            color=alt.condition(
                alt.datum.proportion > 0.5,
                alt.value("white"),
                alt.value("black"),
            ),
        )
    )

    # Combine and facet
    chart = (
        (heatmap + text)
        .facet(column=alt.Column("agent_model:N", title=None))
        .properties(title="Grade Distribution Heatmap by Tier")
    )

    save_figure(chart, "fig05_grade_heatmap", output_dir, grade_counts, render)


def fig10_score_violin(runs_df: pd.DataFrame, output_dir: Path, render: bool = True) -> None:
    """Generate Fig 10: Score Distribution Violin Plots.

    Violin plots showing score distribution per tier.

    Args:
        runs_df: Runs DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Prepare data
    data = runs_df[["agent_model", "tier", "score"]].copy()

    # Derive tier order from data
    tier_order = derive_tier_order(data)

    # Get dynamic color scale for models
    models = sorted(data["agent_model"].unique())
    domain, range_ = get_color_scale("models", models)

    # Create violin plot using density transform
    # Note: Altair doesn't have native violin plots, so we approximate with area + line
    base = alt.Chart(data).transform_density(
        density="score",
        as_=["score_value", "density"],
        groupby=["agent_model", "tier"],
    )

    violin = base.mark_area(orient="horizontal", opacity=0.5).encode(
        x=alt.X("tier:O", title="Tier", sort=tier_order),
        y=alt.Y(
            "score_value:Q",
            title="Score",
            scale=alt.Scale(domain=[0, 1]),
        ),
        color=alt.Color(
            "agent_model:N",
            title="Agent Model",
            scale=alt.Scale(domain=domain, range=range_),
        ),
        xOffset="agent_model:N",
    )

    # Overlay median markers
    medians = data.groupby(["agent_model", "tier"])["score"].median().reset_index()

    median_points = (
        alt.Chart(medians)
        .mark_point(filled=True, size=50, color="black")
        .encode(
            x=alt.X("tier:O", sort=tier_order),
            y=alt.Y("score:Q"),
            xOffset="agent_model:N",
        )
    )

    # Combine
    chart = (
        (violin + median_points)
        .properties(title="Score Distribution Violin Plots by Tier")
        .configure_view(strokeWidth=0)
    )

    save_figure(chart, "fig10_score_violin", output_dir, data, render)
