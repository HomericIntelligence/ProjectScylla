"""Cost analysis figures.

Generates Fig 6 (CoP by tier) and Fig 8 (cost vs quality Pareto).
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd

from scylla.analysis.figures import derive_tier_order, get_color_scale
from scylla.analysis.figures.spec_builder import compute_dynamic_domain, save_figure


def fig06_cop_by_tier(runs_df: pd.DataFrame, output_dir: Path, render: bool = True) -> None:
    """Generate Fig 6: Cost Distribution by Tier.

    Histogram showing cost_usd distribution with log-scale bins, one subfigure per tier.

    Args:
        runs_df: Runs DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Prepare data - filter out zero or invalid costs
    data = runs_df[["tier", "cost_usd"]].copy()
    data = data[data["cost_usd"] > 0]  # Log scale requires positive values

    # Derive tier order from data
    tier_order = derive_tier_order(data)

    # Create histogram with log-binning
    # Altair doesn't support log-binning directly, so we'll use regular bins with log scale
    histogram = (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=alt.X(
                "cost_usd:Q",
                bin=alt.Bin(maxbins=20),  # Auto-binning with max 20 bins
                title="Cost (USD)",
                scale=alt.Scale(type="log", base=10),
            ),
            y=alt.Y("count():Q", title="Count"),
        )
    )

    # Facet by tier to create per-tier subfigures
    chart = histogram.facet(column=alt.Column("tier:N", title="Tier", sort=tier_order)).properties(
        title="Cost Distribution per Tier (Log Scale)"
    )

    save_figure(chart, "fig06_cop_by_tier", output_dir, render)


def fig08_cost_quality_pareto(runs_df: pd.DataFrame, output_dir: Path, render: bool = True) -> None:
    """Generate Fig 8: Cost vs Quality Pareto Frontier.

    Scatter plot showing mean cost vs mean score, with Pareto frontier line.

    Args:
        runs_df: Runs DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Compute mean cost and score per (agent_model, tier)
    tier_stats = (
        runs_df.groupby(["agent_model", "tier"])
        .agg({"cost_usd": "mean", "score": "mean"})
        .reset_index()
    )
    tier_stats.columns = ["agent_model", "tier", "mean_cost", "mean_score"]

    # Identify Pareto frontier (higher score, lower cost is better)
    # A point is on the frontier if no other point dominates it
    def is_pareto_efficient(costs, scores):
        """Return boolean array of Pareto efficient points.

        A point (c1, s1) dominates (c2, s2) if c1 <= c2 AND s1 >= s2
        with at least one strict inequality.
        """
        is_efficient = np.ones(len(costs), dtype=bool)
        for i in range(len(costs)):
            if is_efficient[i]:
                # Point i is dominated if there exists j!=i with:
                #   cost_j <= cost_i AND score_j >= score_i (with strict inequality)
                dominated_by_others = np.logical_and(costs <= costs[i], scores >= scores[i]) & (
                    np.logical_or(costs < costs[i], scores > scores[i])
                )
                # Exclude self-comparison
                dominated_by_others[i] = False

                if np.any(dominated_by_others):
                    # Point i is dominated, mark as inefficient
                    is_efficient[i] = False
                else:
                    # Point i is not dominated, remove all points it dominates
                    dominated_by_i = np.logical_and(costs >= costs[i], scores <= scores[i]) & (
                        np.logical_or(costs > costs[i], scores < scores[i])
                    )
                    dominated_by_i[i] = False  # Don't mark self
                    is_efficient[dominated_by_i] = False

        return is_efficient

    # Compute Pareto frontier per model
    tier_stats["is_pareto"] = False
    for model in tier_stats["agent_model"].unique():
        model_mask = tier_stats["agent_model"] == model
        model_data = tier_stats[model_mask]

        pareto_mask = is_pareto_efficient(
            model_data["mean_cost"].values,
            model_data["mean_score"].values,
        )

        tier_stats.loc[model_mask, "is_pareto"] = pareto_mask

    # Get dynamic color scale for models
    models = sorted(tier_stats["agent_model"].unique())
    domain, range_ = get_color_scale("models", models)

    # Define shapes for models (cycle through available shapes)
    shape_options = ["circle", "square", "triangle-up", "diamond", "cross"]
    shape_range = [shape_options[i % len(shape_options)] for i in range(len(models))]

    # Compute dynamic domain for score axis with increased padding for text labels
    score_domain = compute_dynamic_domain(tier_stats["mean_score"], padding_fraction=0.15)

    # Create scatter plot
    scatter = (
        alt.Chart(tier_stats)
        .mark_circle(size=100)
        .encode(
            x=alt.X("mean_cost:Q", title="Mean Cost per Run (USD)", scale=alt.Scale(type="log")),
            y=alt.Y("mean_score:Q", title="Mean Score", scale=alt.Scale(domain=score_domain)),
            color=alt.Color(
                "agent_model:N",
                title="Agent Model",
                scale=alt.Scale(domain=domain, range=range_),
            ),
            shape=alt.Shape(
                "agent_model:N",
                scale=alt.Scale(domain=domain, range=shape_range),
            ),
            tooltip=[
                alt.Tooltip("tier:O", title="Tier"),
                alt.Tooltip("agent_model:N", title="Model"),
                alt.Tooltip("mean_cost:Q", title="Mean Cost", format="$.4f"),
                alt.Tooltip("mean_score:Q", title="Mean Score", format=".3f"),
                alt.Tooltip("is_pareto:N", title="Pareto Efficient"),
            ],
        )
    )

    # Add tier labels
    labels = (
        alt.Chart(tier_stats)
        .mark_text(dy=-15, fontSize=10)
        .encode(
            x="mean_cost:Q",
            y="mean_score:Q",
            text="tier:O",
            color=alt.value("black"),
        )
    )

    # Pareto frontier line (connect Pareto points, sorted by cost)
    pareto_points = tier_stats[tier_stats["is_pareto"]].copy()

    lines = []
    for model in pareto_points["agent_model"].unique():
        model_pareto = pareto_points[pareto_points["agent_model"] == model].sort_values("mean_cost")
        if len(model_pareto) > 1:
            line = (
                alt.Chart(model_pareto)
                .mark_line(strokeDash=[5, 5])
                .encode(
                    x="mean_cost:Q",
                    y="mean_score:Q",
                    color=alt.Color(
                        "agent_model:N",
                        scale=alt.Scale(domain=domain, range=range_),
                    ),
                )
            )
            lines.append(line)

    # Combine all layers
    if lines:
        chart = alt.layer(scatter, labels, *lines)
    else:
        chart = alt.layer(scatter, labels)

    chart = chart.properties(title="Cost vs Quality Pareto Frontier").configure_view(strokeWidth=0)

    save_figure(chart, "fig08_cost_quality_pareto", output_dir, render)


def fig22_cumulative_cost(runs_df: pd.DataFrame, output_dir: Path, render: bool = True) -> None:
    """Generate Fig 22: Cumulative Cost Curve.

    Line chart of cumulative cost over runs, faceted by model, colored by tier.
    Shows how total cost accumulates across the experiment.

    Args:
        runs_df: Runs DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Sort runs by execution order (if available) or by index
    # Assume runs are already in execution order
    if "run_number" in runs_df.columns:
        runs_sorted = runs_df.sort_values(["agent_model", "tier", "subtest", "run_number"])
    else:
        runs_sorted = runs_df.sort_values(["agent_model", "tier", "subtest"])

    # Compute cumulative cost per model
    cumulative_data = []

    for model in sorted(runs_sorted["agent_model"].unique()):
        model_runs = runs_sorted[runs_sorted["agent_model"] == model].copy()
        model_runs["cumulative_cost"] = model_runs["cost_usd"].cumsum()
        model_runs["run_index"] = range(len(model_runs))

        cumulative_data.append(model_runs)

    cumulative_df = pd.concat(cumulative_data, ignore_index=True)

    # Get dynamic color scale for tiers
    from scylla.analysis.figures import derive_tier_order

    tier_order = derive_tier_order(runs_df)
    domain, range_ = get_color_scale("tiers", tier_order)

    # Get dynamic color scale for models
    models = sorted(cumulative_df["agent_model"].unique())
    model_domain, model_range = get_color_scale("models", models)

    # Create line chart with both models in same graph
    # Use different line types (strokeDash) for models
    chart = (
        alt.Chart(cumulative_df)
        .mark_line()
        .encode(
            x=alt.X("run_index:Q", title="Run Index (Chronological Order)"),
            y=alt.Y("cumulative_cost:Q", title="Cumulative Cost (USD)"),
            color=alt.Color(
                "agent_model:N",
                title="Model",
                scale=alt.Scale(domain=model_domain, range=model_range),
            ),
            strokeDash=alt.StrokeDash(
                "agent_model:N",
                title="Model",
                scale=alt.Scale(
                    domain=model_domain,
                    range=[[1, 0], [5, 5]] if len(models) == 2 else [[1, 0], [5, 5], [3, 3]],
                ),
            ),
            tooltip=[
                alt.Tooltip("agent_model:N", title="Model"),
                alt.Tooltip("tier:O", title="Tier"),
                alt.Tooltip("subtest:O", title="Subtest"),
                alt.Tooltip("run_index:Q", title="Run Index"),
                alt.Tooltip("cost_usd:Q", title="Run Cost", format="$.4f"),
                alt.Tooltip("cumulative_cost:Q", title="Cumulative Cost", format="$.2f"),
            ],
        )
        .properties(title="Cumulative Cost Over Runs")
        .configure_view(strokeWidth=0)
    )

    save_figure(chart, "fig22_cumulative_cost", output_dir, render)
