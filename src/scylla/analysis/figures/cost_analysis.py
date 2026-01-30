"""Cost analysis figures.

Generates Fig 6 (CoP by tier) and Fig 8 (cost vs quality Pareto).
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd

from scylla.analysis.figures import COLORS
from scylla.analysis.figures.spec_builder import save_figure


def fig06_cop_by_tier(runs_df: pd.DataFrame, output_dir: Path, render: bool = True) -> None:
    """Generate Fig 6: Cost-of-Pass by Tier.

    Grouped bar chart with log scale, showing CoP per tier.

    Args:
        runs_df: Runs DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Compute CoP per (agent_model, tier)
    tier_order = ["T0", "T1", "T2", "T3", "T4", "T5", "T6"]

    stats = []
    for model in runs_df["agent_model"].unique():
        for tier in tier_order:
            subset = runs_df[(runs_df["agent_model"] == model) & (runs_df["tier"] == tier)]
            if len(subset) == 0:
                continue

            pass_rate = subset["passed"].mean()
            mean_cost = subset["cost_usd"].mean()

            if pass_rate > 0:
                cop = mean_cost / pass_rate
                is_inf = False
            else:
                cop = float("inf")
                is_inf = True

            stats.append(
                {
                    "agent_model": model,
                    "tier": tier,
                    "cop": cop if not is_inf else np.nan,  # NaN for plotting
                    "pass_rate": pass_rate,
                    "mean_cost": mean_cost,
                    "is_inf": is_inf,
                }
            )

    stats_df = pd.DataFrame(stats)

    # Compute frontier CoP per model
    frontier_cops = []
    for model in stats_df["agent_model"].unique():
        model_stats = stats_df[stats_df["agent_model"] == model]
        finite_cops = model_stats[~model_stats["is_inf"]]["cop"]
        if len(finite_cops) > 0:
            frontier_cop = finite_cops.min()
            frontier_cops.append({"agent_model": model, "frontier_cop": frontier_cop})

    frontier_df = pd.DataFrame(frontier_cops)

    # Create bar chart (exclude infinite values)
    finite_stats = stats_df[~stats_df["is_inf"]].copy()

    bars = (
        alt.Chart(finite_stats)
        .mark_bar()
        .encode(
            x=alt.X("tier:O", title="Tier", sort=tier_order),
            y=alt.Y(
                "cop:Q",
                title="Cost-of-Pass (USD, log scale)",
                scale=alt.Scale(type="log", base=10),
            ),
            color=alt.Color(
                "agent_model:N",
                title="Agent Model",
                scale=alt.Scale(
                    domain=list(COLORS["models"].keys()),
                    range=list(COLORS["models"].values()),
                ),
            ),
            xOffset="agent_model:N",
            tooltip=[
                alt.Tooltip("tier:O", title="Tier"),
                alt.Tooltip("agent_model:N", title="Model"),
                alt.Tooltip("cop:Q", title="CoP (USD)", format="$.4f"),
                alt.Tooltip("pass_rate:Q", title="Pass Rate", format=".2%"),
                alt.Tooltip("mean_cost:Q", title="Mean Cost", format="$.4f"),
            ],
        )
    )

    # Add infinity markers for tiers with zero pass rate
    inf_stats = stats_df[stats_df["is_inf"]].copy()
    if len(inf_stats) > 0:
        # Place infinity markers at top of chart
        max_finite_cop = finite_stats["cop"].max() if len(finite_stats) > 0 else 1.0
        inf_stats["cop_plot"] = max_finite_cop * 1.5

        inf_markers = (
            alt.Chart(inf_stats)
            .mark_text(text="∞", size=20, dy=-10)
            .encode(
                x=alt.X("tier:O", sort=tier_order),
                y=alt.Y("cop_plot:Q"),
                xOffset="agent_model:N",
                color=alt.Color(
                    "agent_model:N",
                    scale=alt.Scale(
                        domain=list(COLORS["models"].keys()),
                        range=list(COLORS["models"].values()),
                    ),
                ),
            )
        )
        chart = bars + inf_markers
    else:
        chart = bars

    chart = chart.properties(title="Cost-of-Pass by Tier (Log Scale)").configure_view(strokeWidth=0)

    save_figure(chart, "fig06_cop_by_tier", output_dir, stats_df, render)

    # Also save frontier CoP table
    frontier_csv = output_dir / "fig06_frontier_cop.csv"
    frontier_df.to_csv(frontier_csv, index=False)
    print(f"  Saved frontier CoP: {frontier_csv}")


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
        """Return boolean array of Pareto efficient points."""
        is_efficient = np.ones(len(costs), dtype=bool)
        for i, (cost_i, score_i) in enumerate(zip(costs, scores)):
            if is_efficient[i]:
                # Point i is dominated if there exists j with lower cost and higher score
                is_efficient[is_efficient] = np.logical_not(
                    np.logical_and(
                        costs[is_efficient] <= cost_i,
                        scores[is_efficient] >= score_i,
                    )
                    & (
                        np.logical_or(
                            costs[is_efficient] < cost_i,
                            scores[is_efficient] > score_i,
                        )
                    )
                )
                is_efficient[i] = True
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

    # Create scatter plot
    scatter = (
        alt.Chart(tier_stats)
        .mark_circle(size=100)
        .encode(
            x=alt.X("mean_cost:Q", title="Mean Cost per Run (USD)", scale=alt.Scale(type="log")),
            y=alt.Y("mean_score:Q", title="Mean Score", scale=alt.Scale(domain=[0, 1])),
            color=alt.Color(
                "agent_model:N",
                title="Agent Model",
                scale=alt.Scale(
                    domain=list(COLORS["models"].keys()),
                    range=list(COLORS["models"].values()),
                ),
            ),
            shape=alt.Shape(
                "agent_model:N",
                scale=alt.Scale(domain=list(COLORS["models"].keys()), range=["circle", "square"]),
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
                        scale=alt.Scale(
                            domain=list(COLORS["models"].keys()),
                            range=list(COLORS["models"].values()),
                        ),
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

    save_figure(chart, "fig08_cost_quality_pareto", output_dir, tier_stats, render)
