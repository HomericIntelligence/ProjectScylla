"""Detailed subtest analysis figures.

Generates Fig 13 (latency breakdown) and Fig 15a/b/c (subtest heatmaps).
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd

from scylla.analysis.figures import derive_tier_order, get_color_scale
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

    # Get colors for phases from centralized palette
    phase_labels = ["Agent Execution", "Judge Evaluation"]
    domain, range_ = get_color_scale("phases", phase_labels)

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
                scale=alt.Scale(domain=domain, range=range_),
            ),
            order=alt.Order("phase:N", sort="ascending"),
            tooltip=[
                alt.Tooltip("tier:O", title="Tier"),
                alt.Tooltip("phase_label:N", title="Phase"),
                alt.Tooltip("duration:Q", title="Duration (s)", format=".2f"),
            ],
        )
        .properties(width=350, height=250)
        .facet(column=alt.Column("agent_model:N", title=None))
        .properties(title="Latency Breakdown by Tier")
    )

    save_figure(chart, "fig13_latency", output_dir, render)


def fig15a_subtest_run_heatmap(
    runs_df: pd.DataFrame, output_dir: Path, render: bool = True
) -> None:
    """Generate Fig 15a: Per-Tier Subtest/Run Heatmap (All Runs).

    Large heatmap showing all subtests × runs, color-coded by score.
    Maximum granularity - shows performance variation across all runs.

    Args:
        runs_df: Runs DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Prepare data: one row per (tier, subtest, run_number)
    heatmap_data = runs_df[["agent_model", "tier", "subtest", "run_number", "score"]].copy()

    # Derive tier order from data
    tier_order = derive_tier_order(heatmap_data)

    # Sort subtests numerically within each tier
    heatmap_data["subtest_num"] = heatmap_data["subtest"].astype(int)
    subtest_order = sorted(heatmap_data["subtest"].unique(), key=lambda x: int(x))

    # Create heatmap with faceting by tier
    heatmap = (
        alt.Chart(heatmap_data)
        .mark_rect()
        .encode(
            x=alt.X("run_number:O", title="Run Number", axis=alt.Axis(labelAngle=0)),
            y=alt.Y(
                "subtest:O",
                title="Subtest",
                sort=subtest_order,
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
        .properties(width=300, height=200)
    )

    # Facet by tier and agent_model
    chart = (
        heatmap.facet(
            row=alt.Row("tier:O", title="Tier", sort=tier_order),
            column=alt.Column("agent_model:N", title=None),
        )
        .properties(title="Subtest/Run Scores by Tier (All Runs)")
        .resolve_scale(y="independent")
    )

    save_figure(chart, "fig15a_subtest_run_heatmap", output_dir, render)


def fig15b_subtest_best_heatmap(
    runs_df: pd.DataFrame, output_dir: Path, render: bool = True
) -> None:
    """Generate Fig 15b: Per-Tier Subtest Heatmap (Best Run Only).

    Shows only the best-performing run for each subtest.
    Mid-level granularity - removes run variance, focuses on capability ceiling.

    Args:
        runs_df: Runs DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # For each (agent_model, tier, subtest), keep only the run with highest score
    best_runs = (
        runs_df.sort_values("score", ascending=False)
        .groupby(["agent_model", "tier", "subtest"])
        .first()
        .reset_index()
    )

    # Prepare data
    heatmap_data = best_runs[["agent_model", "tier", "subtest", "run_number", "score"]].copy()

    # Derive tier order from data
    tier_order = derive_tier_order(heatmap_data)

    # Sort subtests numerically within each tier
    heatmap_data["subtest_num"] = heatmap_data["subtest"].astype(int)
    subtest_order = sorted(heatmap_data["subtest"].unique(), key=lambda x: int(x))

    # Create heatmap with faceting by tier (single column since only best run)
    heatmap = (
        alt.Chart(heatmap_data)
        .mark_rect()
        .encode(
            x=alt.X(
                "agent_model:N",
                title=None,
                axis=alt.Axis(labels=False, ticks=False),
            ),
            y=alt.Y(
                "subtest:O",
                title="Subtest",
                sort=subtest_order,
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
                alt.Tooltip("run_number:O", title="Best Run"),
                alt.Tooltip("score:Q", title="Score", format=".3f"),
            ],
        )
        .properties(width=100, height=200)
    )

    # Facet by tier and agent_model
    chart = (
        heatmap.facet(
            row=alt.Row("tier:O", title="Tier", sort=tier_order),
            column=alt.Column("agent_model:N", title=None),
        )
        .properties(title="Best Subtest Scores by Tier")
        .resolve_scale(y="independent")
    )

    save_figure(chart, "fig15b_subtest_best_heatmap", output_dir, render)


def fig15c_tier_summary_heatmap(
    runs_df: pd.DataFrame, output_dir: Path, render: bool = True
) -> None:
    """Generate Fig 15c: Per-Tier Summary Heatmap (Aggregated).

    Aggregates scores across all subtests within each tier.
    Minimum granularity - focuses on tier-level performance patterns.

    Args:
        runs_df: Runs DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Aggregate scores by (agent_model, tier, run_number)
    tier_summary = (
        runs_df.groupby(["agent_model", "tier", "run_number"])["score"].mean().reset_index()
    )

    # Derive tier order
    tier_order = derive_tier_order(tier_summary)

    # Create heatmap with faceting by model
    heatmap = (
        alt.Chart(tier_summary)
        .mark_rect()
        .encode(
            x=alt.X("run_number:O", title="Run Number", axis=alt.Axis(labelAngle=0)),
            y=alt.Y(
                "tier:O",
                title="Tier",
                sort=tier_order,
            ),
            color=alt.Color(
                "score:Q",
                title="Mean Score",
                scale=alt.Scale(
                    scheme="redyellowgreen",
                    domain=[0, 1],
                ),
            ),
            tooltip=[
                alt.Tooltip("agent_model:N", title="Model"),
                alt.Tooltip("tier:O", title="Tier"),
                alt.Tooltip("run_number:O", title="Run"),
                alt.Tooltip("score:Q", title="Mean Score", format=".3f"),
            ],
        )
        .properties(width=300, height=200)
    )

    # Facet by agent_model
    chart = (
        heatmap.facet(column=alt.Column("agent_model:N", title=None))
        .properties(title="Tier Summary (Mean Across Subtests)")
        .resolve_scale(color="shared")
    )

    save_figure(chart, "fig15c_tier_summary_heatmap", output_dir, render)
