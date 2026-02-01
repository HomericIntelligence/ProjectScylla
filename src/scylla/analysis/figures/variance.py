"""Score variance and failure rate figures.

Generates Fig 1 (score variance by tier) and Fig 3 (failure rate by tier).
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd

from scylla.analysis.config import config
from scylla.analysis.figures import derive_tier_order, get_color_scale
from scylla.analysis.figures.spec_builder import save_figure


def fig01_score_variance_by_tier(
    runs_df: pd.DataFrame, output_dir: Path, render: bool = True
) -> None:
    """Generate Fig 1: Score Variance by Tier & Subtest.

    Box plots with jittered points showing score distribution.

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

    # Create base chart with faceting
    base = alt.Chart(data).encode(
        x=alt.X("tier:O", title="Tier", sort=tier_order),
        color=alt.Color(
            "agent_model:N",
            title="Agent Model",
            scale=alt.Scale(domain=domain, range=range_),
        ),
    )

    # Box plot layer
    boxplot = base.mark_boxplot(size=30).encode(
        y=alt.Y("score:Q", title="Score", scale=alt.Scale(domain=[0, 1])),
    )

    # Jittered points layer
    points = base.mark_circle(size=10, opacity=0.3).encode(
        y=alt.Y("score:Q"),
        x=alt.X("tier:O", sort=tier_order),
        xOffset="agent_model:N",
    )

    # Combine layers and facet by model
    chart = (
        (boxplot + points)
        .facet(column=alt.Column("agent_model:N", title=None))
        .properties(
            title="Score Distribution Across Tiers (T0-T6)",
        )
        .resolve_scale(x="independent")
    )

    save_figure(chart, "fig01_score_variance_by_tier", output_dir, data, render)


def fig03_failure_rate_by_tier(
    runs_df: pd.DataFrame, output_dir: Path, render: bool = True
) -> None:
    """Generate Fig 3: Failure Rate by Tier.

    Stacked bar chart showing grade proportions.

    Args:
        runs_df: Runs DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Compute grade proportions per tier
    grade_counts = (
        runs_df.groupby(["agent_model", "tier", "grade"]).size().reset_index(name="count")
    )

    # Derive tier order from data
    tier_order = derive_tier_order(grade_counts)

    # Calculate proportions within each (agent_model, tier) group
    grade_counts["total"] = grade_counts.groupby(["agent_model", "tier"])["count"].transform("sum")
    grade_counts["proportion"] = grade_counts["count"] / grade_counts["total"]

    # Get canonical grade order from config (reversed for bottom-to-top stacking)
    grade_order = list(reversed(config.grade_order))

    # Get dynamic color scale for grades
    domain, range_ = get_color_scale("grades", grade_order)

    # Create stacked bar chart
    chart = (
        alt.Chart(grade_counts)
        .mark_bar()
        .encode(
            x=alt.X("tier:O", title="Tier", sort=tier_order),
            y=alt.Y("proportion:Q", title="Proportion", stack="normalize"),
            color=alt.Color(
                "grade:O",
                title="Grade",
                sort=grade_order,
                scale=alt.Scale(domain=domain, range=range_),
            ),
            order=alt.Order("grade:O", sort="ascending"),
            tooltip=[
                alt.Tooltip("tier:O", title="Tier"),
                alt.Tooltip("grade:O", title="Grade"),
                alt.Tooltip("count:Q", title="Count"),
                alt.Tooltip("proportion:Q", title="Proportion", format=".2%"),
            ],
        )
        .facet(column=alt.Column("agent_model:N", title=None))
        .properties(title="Grade Distribution by Tier")
    )

    save_figure(chart, "fig03_failure_rate_by_tier", output_dir, grade_counts, render)


def fig16_success_variance_by_test(
    runs_df: pd.DataFrame, output_dir: Path, render: bool = True
) -> None:
    """Generate Fig 16: Success Variance by Test.

    Two-panel heatmap showing per-subtest variance, grouped by tier, faceted by model:
    - Panel A: Binary pass/fail Bernoulli variance (p*(1-p))
    - Panel B: Continuous score standard deviation

    Args:
        runs_df: Runs DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Compute variance metrics per (agent_model, tier, subtest)
    variance_data = []

    for (model, tier, subtest), group in runs_df.groupby(["agent_model", "tier", "subtest"]):
        pass_rate = group["passed"].mean()
        pass_variance = pass_rate * (1 - pass_rate)  # Bernoulli variance: p(1-p)
        score_std = group["score"].std()

        variance_data.append(
            {
                "agent_model": model,
                "tier": tier,
                "subtest": subtest,
                "pass_variance": pass_variance,
                "score_std": score_std,
                "n_runs": len(group),
            }
        )

    variance_df = pd.DataFrame(variance_data)

    # Derive tier order from data
    tier_order = derive_tier_order(variance_df)

    # Panel A: Pass/fail variance heatmap
    heatmap_pass = (
        alt.Chart(variance_df)
        .mark_rect()
        .encode(
            x=alt.X("tier:O", title="Tier", sort=tier_order),
            y=alt.Y("subtest:O", title="Subtest", sort="ascending"),
            color=alt.Color(
                "pass_variance:Q",
                title="Pass Variance",
                scale=alt.Scale(scheme="viridis", domain=[0, 0.25]),
            ),
            tooltip=[
                alt.Tooltip("tier:O", title="Tier"),
                alt.Tooltip("subtest:O", title="Subtest"),
                alt.Tooltip("pass_variance:Q", title="Pass Variance", format=".3f"),
                alt.Tooltip("n_runs:Q", title="Runs"),
            ],
        )
        .properties(title="Panel A: Pass/Fail Variance (Bernoulli)", width=400, height=600)
        .facet(row=alt.Row("agent_model:N", title=None))
        .resolve_scale(y="independent")
    )

    # Panel B: Score std dev heatmap
    heatmap_score = (
        alt.Chart(variance_df)
        .mark_rect()
        .encode(
            x=alt.X("tier:O", title="Tier", sort=tier_order),
            y=alt.Y("subtest:O", title="Subtest", sort="ascending"),
            color=alt.Color(
                "score_std:Q",
                title="Score Std Dev",
                scale=alt.Scale(scheme="plasma", domain=[0, 0.3]),
            ),
            tooltip=[
                alt.Tooltip("tier:O", title="Tier"),
                alt.Tooltip("subtest:O", title="Subtest"),
                alt.Tooltip("score_std:Q", title="Score Std Dev", format=".3f"),
                alt.Tooltip("n_runs:Q", title="Runs"),
            ],
        )
        .properties(title="Panel B: Score Standard Deviation", width=400, height=600)
        .facet(row=alt.Row("agent_model:N", title=None))
        .resolve_scale(y="independent")
    )

    # Combine faceted panels horizontally
    chart = (heatmap_pass | heatmap_score).properties(title="Success Variance by Test")

    save_figure(chart, "fig16_success_variance_by_test", output_dir, variance_df, render)


def fig18_failure_rate_by_test(
    runs_df: pd.DataFrame, output_dir: Path, render: bool = True
) -> None:
    """Generate Fig 18: Failure Rate by Test.

    Horizontal bar chart showing failure rate (1 - pass_rate) per subtest,
    color-coded by tier, faceted by model.

    Args:
        runs_df: Runs DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Compute failure rate per (agent_model, tier, subtest)
    failure_data = []

    for (model, tier, subtest), group in runs_df.groupby(["agent_model", "tier", "subtest"]):
        pass_rate = group["passed"].mean()
        failure_rate = 1 - pass_rate

        failure_data.append(
            {
                "agent_model": model,
                "tier": tier,
                "subtest": subtest,
                "subtest_label": f"{tier}-{subtest}",
                "failure_rate": failure_rate,
                "n_runs": len(group),
            }
        )

    failure_df = pd.DataFrame(failure_data)

    # Sort by tier then subtest for display
    failure_df = failure_df.sort_values(["tier", "subtest"])

    # Derive tier order from data
    tier_order = derive_tier_order(failure_df)

    # Get dynamic color scale for tiers
    domain, range_ = get_color_scale("tiers", tier_order)

    # Horizontal bar chart
    chart = (
        alt.Chart(failure_df)
        .mark_bar()
        .encode(
            y=alt.Y(
                "subtest_label:N",
                title="Subtest",
                sort=alt.EncodingSortField(field="tier", order="ascending"),
            ),
            x=alt.X("failure_rate:Q", title="Failure Rate", scale=alt.Scale(domain=[0, 1])),
            color=alt.Color(
                "tier:N",
                title="Tier",
                sort=tier_order,
                scale=alt.Scale(domain=domain, range=range_),
            ),
            tooltip=[
                alt.Tooltip("tier:O", title="Tier"),
                alt.Tooltip("subtest:O", title="Subtest"),
                alt.Tooltip("failure_rate:Q", title="Failure Rate", format=".2%"),
                alt.Tooltip("n_runs:Q", title="Runs"),
            ],
        )
        .facet(column=alt.Column("agent_model:N", title=None))
        .properties(title="Failure Rate by Test")
        .resolve_scale(y="independent")
    )

    save_figure(chart, "fig18_failure_rate_by_test", output_dir, failure_df, render)
