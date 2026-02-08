"""Diagnostic figures for distribution analysis.

Generates Fig 23 (Q-Q plots) and Fig 24 (score histograms with KDE).
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
from scipy import stats

from scylla.analysis.figures import derive_tier_order, get_color_scale
from scylla.analysis.figures.spec_builder import save_figure


def fig23_qq_plots(runs_df: pd.DataFrame, output_dir: Path, render: bool = True) -> None:
    """Generate Fig 23: Q-Q Plots (Quantile-Quantile).

    Q-Q plots per (model, tier) to assess normality.
    Compares theoretical quantiles (normal distribution) vs observed quantiles.
    Points should fall on diagonal line if data is normally distributed.

    Args:
        runs_df: Runs DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    tier_order = derive_tier_order(runs_df)

    qq_data = []

    for model in sorted(runs_df["agent_model"].unique()):
        for tier in tier_order:
            tier_data = runs_df[(runs_df["agent_model"] == model) & (runs_df["tier"] == tier)]

            if len(tier_data) < 3:
                continue

            # Get score data
            scores = tier_data["score"].dropna().values

            if len(scores) < 3:
                continue

            # Compute theoretical quantiles (standard normal)
            theoretical_quantiles = stats.norm.ppf(
                np.linspace(0.01, 0.99, len(scores))
            )  # Avoid 0 and 1

            # Compute observed quantiles (sorted, standardized)
            observed_sorted = np.sort(scores)
            observed_mean = np.mean(scores)
            observed_std = np.std(scores)
            observed_quantiles = (
                (observed_sorted - observed_mean) / observed_std
                if observed_std > 0
                else observed_sorted
            )

            for theoretical_q, observed_q, original_score in zip(
                theoretical_quantiles, observed_quantiles, observed_sorted
            ):
                qq_data.append(
                    {
                        "agent_model": model,
                        "tier": tier,
                        "theoretical_quantile": theoretical_q,
                        "observed_quantile": observed_q,
                        "original_score": original_score,
                    }
                )

    qq_df = pd.DataFrame(qq_data)

    if len(qq_df) == 0:
        print("  Warning: No data for Q-Q plots")
        return

    # Create Q-Q scatter plot
    scatter = (
        alt.Chart(qq_df)
        .mark_circle(size=40, opacity=0.6)
        .encode(
            x=alt.X("theoretical_quantile:Q", title="Theoretical Quantiles (Normal)"),
            y=alt.Y("observed_quantile:Q", title="Observed Quantiles (Standardized Score)"),
            color=alt.Color("tier:N", title="Tier"),
            tooltip=[
                alt.Tooltip("agent_model:N", title="Model"),
                alt.Tooltip("tier:O", title="Tier"),
                alt.Tooltip("theoretical_quantile:Q", title="Theoretical Q", format=".2f"),
                alt.Tooltip("observed_quantile:Q", title="Observed Q", format=".2f"),
                alt.Tooltip("original_score:Q", title="Original Score", format=".3f"),
            ],
        )
    )

    # Add diagonal reference line (y=x)
    # Get extent of data
    q_min = min(qq_df["theoretical_quantile"].min(), qq_df["observed_quantile"].min())
    q_max = max(qq_df["theoretical_quantile"].max(), qq_df["observed_quantile"].max())

    # Build per-facet reference line data with matching column names
    ref_rows = []
    for model in sorted(runs_df["agent_model"].unique()):
        for tier in tier_order:
            ref_rows.append(
                {
                    "agent_model": model,
                    "tier": tier,
                    "theoretical_quantile": q_min,
                    "observed_quantile": q_min,
                }
            )
            ref_rows.append(
                {
                    "agent_model": model,
                    "tier": tier,
                    "theoretical_quantile": q_max,
                    "observed_quantile": q_max,
                }
            )
    ref_df = pd.DataFrame(ref_rows)

    reference_line = (
        alt.Chart(ref_df)
        .mark_line(strokeDash=[5, 5], color="red")
        .encode(x="theoretical_quantile:Q", y="observed_quantile:Q")
    )

    # Facet by (model, tier) - pass qq_df as data to facet
    chart = (
        alt.layer(reference_line, scatter)
        .facet(
            column=alt.Column("tier:N", title="Tier", sort=tier_order),
            row=alt.Row("agent_model:N", title="Agent Model"),
            data=qq_df,
        )
        .properties(title="Q-Q Plots (Normal Distribution Assessment)")
        .configure_view(strokeWidth=0)
    )

    save_figure(chart, "fig23_qq_plots", output_dir, render)


def fig24_score_histograms(runs_df: pd.DataFrame, output_dir: Path, render: bool = True) -> None:
    """Generate Fig 24: Score Histograms with KDE Overlay.

    Histograms with kernel density estimate (KDE) overlay.
    Faceted by tier, colored by model.

    Args:
        runs_df: Runs DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    tier_order = derive_tier_order(runs_df)

    # Compute KDE for each (model, tier)
    kde_data = []

    for model in sorted(runs_df["agent_model"].unique()):
        for tier in tier_order:
            tier_data = runs_df[(runs_df["agent_model"] == model) & (runs_df["tier"] == tier)]

            if len(tier_data) < 3:
                continue

            scores = tier_data["score"].dropna().values

            if len(scores) < 3:
                continue

            # Compute KDE
            try:
                kde = stats.gaussian_kde(scores)
                x_range = np.linspace(0, 1, 100)
                kde_values = kde(x_range)

                for x, density in zip(x_range, kde_values):
                    kde_data.append(
                        {"agent_model": model, "tier": tier, "score": x, "density": density}
                    )
            except Exception as e:
                print(f"  Warning: KDE failed for {model}/{tier}: {e}")
                continue

    kde_df = pd.DataFrame(kde_data)

    # Get dynamic color scale for models
    models = sorted(runs_df["agent_model"].unique())
    domain, range_ = get_color_scale("models", models)

    # Create histogram
    histogram = (
        alt.Chart(runs_df)
        .mark_bar(opacity=0.5, binSpacing=0)
        .encode(
            x=alt.X("score:Q", title="Score", bin=alt.Bin(maxbins=20)),
            y=alt.Y("count():Q", title="Frequency"),
            color=alt.Color(
                "agent_model:N",
                title="Agent Model",
                scale=alt.Scale(domain=domain, range=range_),
            ),
            tooltip=[
                alt.Tooltip("agent_model:N", title="Model"),
                alt.Tooltip("count():Q", title="Count"),
            ],
        )
    )

    # Create KDE overlay
    if len(kde_df) > 0:
        # Scale KDE to match histogram frequency per (model, tier) group
        for (model, tier), group_idx in kde_df.groupby(["agent_model", "tier"]).groups.items():
            group_mask = (kde_df["agent_model"] == model) & (kde_df["tier"] == tier)
            group_density_max = kde_df.loc[group_mask, "density"].max()
            tier_count = len(runs_df[(runs_df["agent_model"] == model) & (runs_df["tier"] == tier)])
            if group_density_max > 0:
                kde_df.loc[group_mask, "scaled_density"] = kde_df.loc[group_mask, "density"] * (
                    tier_count / group_density_max
                )

        kde_lines = (
            alt.Chart(kde_df)
            .mark_line(strokeWidth=2)
            .encode(
                x=alt.X("score:Q"),
                y=alt.Y("scaled_density:Q"),
                color=alt.Color(
                    "agent_model:N",
                    scale=alt.Scale(domain=domain, range=range_),
                ),
            )
        )

        # Facet by tier - pass runs_df as data to facet
        chart = (
            alt.layer(histogram, kde_lines)
            .facet(column=alt.Column("tier:N", title="Tier", sort=tier_order), data=runs_df)
            .properties(title="Score Distributions with KDE Overlay")
            .configure_view(strokeWidth=0)
        )
    else:
        # No KDE data, just show histogram
        chart = (
            histogram.facet(column=alt.Column("tier:N", title="Tier", sort=tier_order))
            .properties(title="Score Distributions")
            .configure_view(strokeWidth=0)
        )

    save_figure(chart, "fig24_score_histograms", output_dir, render)
