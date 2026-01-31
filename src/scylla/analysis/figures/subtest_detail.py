"""Detailed subtest analysis figures.

Generates Fig 13 (latency breakdown) and Fig 15 (subtest heatmap).
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd

from scylla.analysis.figures import derive_tier_order
from scylla.analysis.figures.spec_builder import save_figure


def fig13_latency(runs_df: pd.DataFrame, output_dir: Path, render: bool = True) -> None:
    """Generate Fig 13: Latency Breakdown.

    Stacked bar chart showing agent + judge duration.

    Args:
        runs_df: Runs DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Aggregate durations by (agent_model, tier)
    duration_agg = (
        runs_df.groupby(["agent_model", "tier"])[
            ["agent_duration_seconds", "judge_duration_seconds"]
        ]
        .mean()
        .reset_index()
    )

    # Derive tier order from data
    tier_order = derive_tier_order(duration_agg)

    # Reshape to long format for stacking
    duration_long = duration_agg.melt(
        id_vars=["agent_model", "tier"],
        value_vars=["agent_duration_seconds", "judge_duration_seconds"],
        var_name="phase",
        value_name="duration",
    )

    # Clean up phase labels
    duration_long["phase_label"] = duration_long["phase"].map(
        {
            "agent_duration_seconds": "Agent Execution",
            "judge_duration_seconds": "Judge Evaluation",
        }
    )

    # Define colors for phases
    phase_colors = {
        "Agent Execution": "#4C78A8",
        "Judge Evaluation": "#E45756",
    }

    # Create stacked bar chart
    chart = (
        alt.Chart(duration_long)
        .mark_bar()
        .encode(
            x=alt.X("tier:O", title="Tier", sort=tier_order),
            y=alt.Y("duration:Q", title="Mean Duration (seconds)"),
            color=alt.Color(
                "phase_label:N",
                title="Phase",
                scale=alt.Scale(
                    domain=list(phase_colors.keys()),
                    range=list(phase_colors.values()),
                ),
            ),
            order=alt.Order("phase:N", sort="ascending"),
            tooltip=[
                alt.Tooltip("tier:O", title="Tier"),
                alt.Tooltip("phase_label:N", title="Phase"),
                alt.Tooltip("duration:Q", title="Duration (s)", format=".2f"),
            ],
        )
        .facet(column=alt.Column("agent_model:N", title=None))
        .properties(title="Latency Breakdown by Tier")
    )

    save_figure(chart, "fig13_latency", output_dir, duration_long, render)


def fig15_subtest_heatmap(runs_df: pd.DataFrame, output_dir: Path, render: bool = True) -> None:
    """Generate Fig 15: Subtest Performance Heatmap.

    Large heatmap showing all subtests × runs, color-coded by score.

    Args:
        runs_df: Runs DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Prepare data: one row per (tier, subtest, run_number)
    heatmap_data = runs_df[["agent_model", "tier", "subtest", "run_number", "score"]].copy()

    # Create subtest labels combining tier and subtest ID
    heatmap_data["subtest_label"] = heatmap_data["tier"] + "/" + heatmap_data["subtest"]

    # Derive tier order from data and sort subtests by tier then subtest number
    tier_order = derive_tier_order(heatmap_data)
    heatmap_data["tier_sort"] = heatmap_data["tier"].map({t: i for i, t in enumerate(tier_order)})
    heatmap_data["subtest_num"] = heatmap_data["subtest"].astype(int)
    heatmap_data = heatmap_data.sort_values(["tier_sort", "subtest_num"])

    # Get sorted subtest labels
    sorted_subtests = heatmap_data["subtest_label"].unique().tolist()

    # Create heatmap per model
    charts = []
    for model in heatmap_data["agent_model"].unique():
        model_data = heatmap_data[heatmap_data["agent_model"] == model]

        heatmap = (
            alt.Chart(model_data)
            .mark_rect()
            .encode(
                x=alt.X("run_number:O", title="Run Number", axis=alt.Axis(labelAngle=0)),
                y=alt.Y(
                    "subtest_label:N",
                    title="Tier/Subtest",
                    sort=sorted_subtests,
                    axis=alt.Axis(labelFontSize=8),
                ),
                color=alt.Color(
                    "score:Q",
                    title="Score",
                    scale=alt.Scale(
                        scheme="redyellowgreen",
                        domain=[0, 1],
                    ),
                ),
                tooltip=[
                    alt.Tooltip("tier:O", title="Tier"),
                    alt.Tooltip("subtest:O", title="Subtest"),
                    alt.Tooltip("run_number:O", title="Run"),
                    alt.Tooltip("score:Q", title="Score", format=".3f"),
                ],
            )
            .properties(
                width=300,
                height=1200,  # Large height to accommodate all subtests
                title=f"{model} - All Subtests Performance",
            )
        )

        charts.append(heatmap)

    # Concatenate horizontally
    chart = alt.hconcat(*charts).resolve_scale(color="shared")

    save_figure(chart, "fig15_subtest_heatmap", output_dir, heatmap_data, render)
