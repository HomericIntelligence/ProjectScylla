"""Score variance and failure rate figures.

Generates Fig 1 (score variance by tier) and Fig 3 (failure rate by tier).
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd

from scylla.analysis.figures import COLORS, TIER_ORDER
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

    # Define tier order
    # Removed: using TIER_ORDER from figures module

    # Create base chart with faceting
    base = alt.Chart(data).encode(
        x=alt.X("tier:O", title="Tier", sort=TIER_ORDER),
        color=alt.Color(
            "agent_model:N",
            title="Agent Model",
            scale=alt.Scale(
                domain=list(COLORS["models"].keys()),
                range=list(COLORS["models"].values()),
            ),
        ),
    )

    # Box plot layer
    boxplot = base.mark_boxplot(size=30).encode(
        y=alt.Y("score:Q", title="Score", scale=alt.Scale(domain=[0, 1])),
    )

    # Jittered points layer
    points = base.mark_circle(size=10, opacity=0.3).encode(
        y=alt.Y("score:Q"),
        x=alt.X("tier:O", sort=TIER_ORDER),
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

    # Calculate proportions within each (agent_model, tier) group
    grade_counts["total"] = grade_counts.groupby(["agent_model", "tier"])["count"].transform("sum")
    grade_counts["proportion"] = grade_counts["count"] / grade_counts["total"]

    # Define grade order (F at bottom, S at top)
    grade_order = ["F", "D", "C", "B", "A", "S"]
    # Removed: using TIER_ORDER from figures module

    # Create stacked bar chart
    chart = (
        alt.Chart(grade_counts)
        .mark_bar()
        .encode(
            x=alt.X("tier:O", title="Tier", sort=TIER_ORDER),
            y=alt.Y("proportion:Q", title="Proportion", stack="normalize"),
            color=alt.Color(
                "grade:O",
                title="Grade",
                sort=grade_order,
                scale=alt.Scale(
                    domain=grade_order,
                    range=[COLORS["grades"][g] for g in grade_order],
                ),
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
