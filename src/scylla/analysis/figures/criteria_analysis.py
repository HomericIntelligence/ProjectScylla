"""Per-criteria performance analysis.

Generates Fig 9 (criteria scores by tier).
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd

from scylla.analysis.figures import COLORS
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
    # Aggregate by (agent_model, tier, criterion)
    tier_order = ["T0", "T1", "T2", "T3", "T4", "T5", "T6"]
    criterion_order = [
        "functional",
        "code_quality",
        "proportionality",
        "build_pipeline",
        "overall_quality",
    ]

    criterion_labels = {
        "functional": "Functional",
        "code_quality": "Code Quality",
        "proportionality": "Proportionality",
        "build_pipeline": "Build Pipeline",
        "overall_quality": "Overall Quality",
    }

    # Filter to ensure criterion_score is numeric (not "N/A")
    criteria_numeric = criteria_df[
        pd.to_numeric(criteria_df["criterion_score"], errors="coerce").notna()
    ].copy()

    criteria_agg = (
        criteria_numeric.groupby(["agent_model", "tier", "criterion"])["criterion_score"]
        .mean()
        .reset_index()
    )
    criteria_agg["criterion_label"] = criteria_agg["criterion"].map(criterion_labels)

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
                    domain=[criterion_labels[c] for c in criterion_order],
                    range=[COLORS["criteria"][c] for c in criterion_order],
                ),
                sort=[criterion_labels[c] for c in criterion_order],
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
