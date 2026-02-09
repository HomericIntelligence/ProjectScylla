"""Tier performance figures.

Generates Fig 4 (pass-rate) and Fig 5 (grade heatmap).
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd

from scylla.analysis.config import config
from scylla.analysis.figures import derive_tier_order
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
