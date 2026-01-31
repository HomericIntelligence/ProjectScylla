"""Per-criteria performance analysis.

Generates Fig 9 (criteria scores by tier).
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd

from scylla.analysis.figures import COLORS, derive_tier_order
from scylla.analysis.figures.spec_builder import save_figure


def fig09_criteria_by_tier(
    criteria_df: pd.DataFrame, output_dir: Path, render: bool = True
) -> None:
    """Generate Fig 9: Per-Criteria Scores by Tier.

    Grouped bar chart showing mean criterion scores.

    Args:
        criteria_df: Criteria DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Filter to ensure criterion_score is numeric (not "N/A")
    criteria_numeric = criteria_df[
        pd.to_numeric(criteria_df["criterion_score"], errors="coerce").notna()
    ].copy()

    # Derive criterion order from data instead of hardcoding
    criterion_order = sorted(criteria_numeric["criterion"].unique())

    # Generate display labels from criterion names
    criterion_labels = {c: c.replace("_", " ").title() for c in criterion_order}

    criteria_agg = (
        criteria_numeric.groupby(["agent_model", "tier", "criterion"])["criterion_score"]
        .mean()
        .reset_index()
    )
    criteria_agg["criterion_label"] = criteria_agg["criterion"].map(criterion_labels)

    # Derive tier order from aggregated data
    tier_order = derive_tier_order(criteria_agg)

    # Get colors for criteria (use COLORS if available, otherwise use get_color_scale)
    criterion_labels_list = [criterion_labels[c] for c in criterion_order]
    criterion_colors = []
    for c in criterion_order:
        if c in COLORS["criteria"]:
            criterion_colors.append(COLORS["criteria"][c])
        else:
            # Use dynamic color assignment via hash for unknown criteria
            from scylla.analysis.figures import get_color

            criterion_colors.append(get_color("criteria", c))

    # Create grouped bar chart
    chart = (
        alt.Chart(criteria_agg)
        .mark_bar()
        .encode(
            x=alt.X("tier:O", title="Tier", sort=tier_order),
            y=alt.Y(
                "criterion_score:Q",
                title="Mean Criterion Score",
                scale=alt.Scale(domain=[0, 1]),
            ),
            color=alt.Color(
                "criterion_label:N",
                title="Criterion",
                scale=alt.Scale(
                    domain=criterion_labels_list,
                    range=criterion_colors,
                ),
                sort=criterion_labels_list,
            ),
            xOffset="criterion_label:N",
            tooltip=[
                alt.Tooltip("tier:O", title="Tier"),
                alt.Tooltip("criterion_label:N", title="Criterion"),
                alt.Tooltip("criterion_score:Q", title="Mean Score", format=".3f"),
            ],
        )
        .facet(column=alt.Column("agent_model:N", title=None))
        .properties(title="Per-Criteria Performance by Tier")
    )

    save_figure(chart, "fig09_criteria_by_tier", output_dir, criteria_agg, render)
