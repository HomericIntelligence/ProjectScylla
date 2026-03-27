"""Per-criteria performance analysis.

Generates Fig 9 (criteria scores by tier).
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd

from scylla.analysis.figures import derive_tier_order
from scylla.analysis.figures.spec_builder import compute_dynamic_domain, save_figure


def fig09_criteria_by_tier(
    criteria_df: pd.DataFrame, output_dir: Path, render: bool = True
) -> None:
    """Generate Fig 9: Per-Criteria Scores by Tier.

    Faceted bar chart with one subplot per criterion, showing mean scores by tier.
    Uses row faceting to create a vertical stack of 5 criterion panels for improved
    readability compared to the previous grouped bar chart.

    Args:
        criteria_df: Criteria DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Filter to ensure criterion_score is numeric (not "N/A")
    criteria_numeric = criteria_df[
        pd.to_numeric(criteria_df["criterion_score"], errors="coerce").notna()
    ].copy()

    # Filter out criteria with no data (empty after grouping)
    criteria_agg_temp = (
        criteria_numeric.groupby(["agent_model", "tier", "criterion"])["criterion_score"]
        .mean()
        .reset_index()
    )

    # Only keep criteria that have at least one data point
    valid_criteria = criteria_agg_temp["criterion"].unique()

    # Derive criterion order from data (only valid criteria with data)
    criterion_order = sorted(valid_criteria)

    # Generate display labels from criterion names
    criterion_labels = {c: c.replace("_", " ").title() for c in criterion_order}

    # Use the pre-computed aggregation (already filtered to valid criteria)
    criteria_agg = criteria_agg_temp
    criteria_agg["criterion_label"] = criteria_agg["criterion"].map(criterion_labels)

    # Derive tier order from aggregated data
    tier_order = derive_tier_order(criteria_agg)

    # Get colors for tiers (not criteria, since each criterion is now a separate subplot)
    tier_colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2"]

    # Dynamic domain rounded to nearest 0.1 for clean axis labels
    raw_domain = compute_dynamic_domain(criteria_agg["criterion_score"])
    score_domain = [round(raw_domain[0] / 0.1) * 0.1, round(raw_domain[1] / 0.1) * 0.1]

    # Sort criteria labels for consistent ordering
    criterion_labels_list = [criterion_labels[c] for c in criterion_order]

    # Create base chart with tier-based coloring
    base_chart = (
        alt.Chart(criteria_agg)
        .mark_bar()
        .encode(
            x=alt.X("tier:O", title="Tier", sort=tier_order),
            y=alt.Y(
                "criterion_score:Q",
                title="Mean Score",
                scale=alt.Scale(domain=score_domain),
            ),
            color=alt.Color(
                "tier:O",
                title="Tier",
                scale=alt.Scale(domain=tier_order, range=tier_colors[: len(tier_order)]),
                sort=tier_order,
                legend=None,  # Remove legend since tier is already on x-axis
            ),
            tooltip=[
                alt.Tooltip("tier:O", title="Tier"),
                alt.Tooltip("criterion_label:N", title="Criterion"),
                alt.Tooltip("criterion_score:Q", title="Mean Score", format=".3f"),
            ],
        )
        .properties(
            height=150,  # Individual subplot height for readability
            width=180,  # Individual subplot width
        )
    )

    # Facet by criterion (row) and agent_model (column)
    chart = (
        base_chart.facet(
            row=alt.Row(
                "criterion_label:N",
                title="Criterion",
                sort=criterion_labels_list,
                header=alt.Header(labelAngle=0, labelAlign="left"),
            ),
            column=alt.Column("agent_model:N", title=None),
        )
        .properties(title="Per-Criteria Performance by Tier")
        .resolve_scale(
            y="independent"  # Allow each criterion to have its own y-axis scale if needed
        )
    )

    save_figure(chart, "fig09_criteria_by_tier", output_dir, render)
