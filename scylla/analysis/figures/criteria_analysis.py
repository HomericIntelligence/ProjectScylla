"""Per-criteria performance analysis.

Generates Fig 9 (criteria scores by tier).
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd

from scylla.analysis.figures import derive_tier_order, get_color_scale
from scylla.analysis.figures.spec_builder import compute_dynamic_domain, save_figure


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

    # Get colors for criteria using centralized function
    criterion_labels_list = [criterion_labels[c] for c in criterion_order]
    _, criterion_colors = get_color_scale("criteria", criterion_order)

    # Compute dynamic domain for criterion score axis
    score_domain = compute_dynamic_domain(criteria_agg["criterion_score"])

    # Create grouped bar chart
    chart = (
        alt.Chart(criteria_agg)
        .mark_bar()
        .encode(
            x=alt.X("tier:O", title="Tier", sort=tier_order),
            y=alt.Y(
                "criterion_score:Q",
                title="Mean Criterion Score",
                scale=alt.Scale(domain=score_domain),
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
