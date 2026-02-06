"""Implementation Rate analysis figures.

Generates figures for Impl-Rate metric analysis:
- Fig 25: Impl-Rate by tier (bar chart with CIs)
- Fig 26: Impl-Rate vs Pass-Rate scatter
- Fig 27: Impl-Rate distribution by tier

Python Justification: Uses altair for Vega-Lite visualization.
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd

from scylla.analysis.figures import derive_tier_order, get_color_scale
from scylla.analysis.figures.spec_builder import compute_dynamic_domain, save_figure
from scylla.analysis.stats import bootstrap_ci


def fig25_impl_rate_by_tier(
    runs_df: pd.DataFrame,
    output_dir: Path,
    render: bool = True,
) -> None:
    """Generate Fig 25: Implementation Rate by Tier.

    Grouped bar chart with 95% bootstrap confidence intervals.
    Analogous to fig04 but for Impl-Rate instead of Pass-Rate.

    Args:
        runs_df: Runs DataFrame (must include impl_rate column)
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Check if impl_rate column exists
    if "impl_rate" not in runs_df.columns:
        print("Warning: impl_rate column not found in runs_df, skipping fig25")
        return

    # Derive tier order from data
    tier_order = derive_tier_order(runs_df)

    stats = []
    for model in runs_df["agent_model"].unique():
        for tier in tier_order:
            subset = runs_df[(runs_df["agent_model"] == model) & (runs_df["tier"] == tier)]
            if len(subset) == 0:
                continue

            impl_rate = subset["impl_rate"].dropna()
            if len(impl_rate) == 0:
                continue

            mean, ci_low, ci_high = bootstrap_ci(impl_rate)

            stats.append(
                {
                    "agent_model": model,
                    "tier": tier,
                    "impl_rate": mean,
                    "ci_low": ci_low,
                    "ci_high": ci_high,
                    "n": len(impl_rate),
                }
            )

    df = pd.DataFrame(stats)

    # Get color scale for models
    models = sorted(df["agent_model"].unique())
    domain, range_ = get_color_scale("models", models)

    # Compute dynamic domain for impl_rate axis
    impl_rate_domain = compute_dynamic_domain(df["impl_rate"])

    # Vega-Lite spec
    bars = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X(
                "tier:N",
                title="Tier",
                axis=alt.Axis(labelAngle=0),
                sort=tier_order,
            ),
            y=alt.Y(
                "impl_rate:Q",
                title="Implementation Rate",
                scale=alt.Scale(domain=impl_rate_domain),
            ),
            color=alt.Color(
                "agent_model:N",
                title="Model",
                scale=alt.Scale(domain=domain, range=range_),
            ),
            xOffset="agent_model:N",
            tooltip=[
                alt.Tooltip("agent_model:N", title="Model"),
                alt.Tooltip("tier:N", title="Tier"),
                alt.Tooltip("impl_rate:Q", title="Impl-Rate", format=".3f"),
                alt.Tooltip("ci_low:Q", title="95% CI Low", format=".3f"),
                alt.Tooltip("ci_high:Q", title="95% CI High", format=".3f"),
                alt.Tooltip("n:Q", title="N"),
            ],
        )
    )

    # Error bars (95% CI)
    error_bars = (
        alt.Chart(df)
        .mark_errorbar()
        .encode(
            x=alt.X("tier:N", sort=tier_order),
            y=alt.Y("ci_low:Q", title="Implementation Rate"),
            y2="ci_high:Q",
            xOffset="agent_model:N",
        )
    )

    chart = (bars + error_bars).properties(
        title="Implementation Rate by Tier (95% Bootstrap CI)",
        width=400,
        height=300,
    )

    save_figure(chart, "fig25_impl_rate_by_tier", output_dir, df, render=render)


def fig26_impl_rate_vs_pass_rate(
    runs_df: pd.DataFrame,
    output_dir: Path,
    render: bool = True,
) -> None:
    """Generate Fig 26: Implementation Rate vs Pass-Rate Scatter.

    Scatter plot showing relationship between Impl-Rate and Pass-Rate
    with tier coloring and linear regression line.

    Args:
        runs_df: Runs DataFrame (must include impl_rate and passed columns)
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Check required columns
    if "impl_rate" not in runs_df.columns:
        print("Warning: impl_rate column not found in runs_df, skipping fig26")
        return

    # Filter out NaN impl_rate values
    df = runs_df[["agent_model", "tier", "passed", "impl_rate"]].dropna()

    if len(df) == 0:
        print("Warning: No valid data for fig26")
        return

    # Convert passed to numeric for plotting
    df = df.copy()
    df["pass_rate"] = df["passed"].astype(int)

    # Derive tier order for color scale
    tier_order = derive_tier_order(runs_df)
    domain, range_ = get_color_scale("tiers", tier_order)

    # Compute dynamic domain for impl_rate axis
    impl_rate_domain = compute_dynamic_domain(df["impl_rate"])

    # Scatter plot
    points = (
        alt.Chart(df)
        .mark_circle(size=60, opacity=0.6)
        .encode(
            x=alt.X(
                "impl_rate:Q",
                title="Implementation Rate",
                scale=alt.Scale(domain=impl_rate_domain),
            ),
            y=alt.Y(
                "pass_rate:Q",
                title="Pass-Rate (Binary)",
                scale=alt.Scale(domain=[-0.1, 1.1]),
            ),
            color=alt.Color(
                "tier:N",
                title="Tier",
                scale=alt.Scale(domain=domain, range=range_),
                sort=tier_order,
            ),
            tooltip=[
                alt.Tooltip("agent_model:N", title="Model"),
                alt.Tooltip("tier:N", title="Tier"),
                alt.Tooltip("impl_rate:Q", title="Impl-Rate", format=".3f"),
                alt.Tooltip("pass_rate:Q", title="Passed", format="d"),
            ],
        )
    )

    # Linear regression line
    regression = (
        alt.Chart(df)
        .mark_line(color="black", strokeDash=[5, 5])
        .transform_regression("impl_rate", "pass_rate")
        .encode(
            x="impl_rate:Q",
            y="pass_rate:Q",
        )
    )

    # Diagonal reference line (perfect correlation)
    diagonal_data = pd.DataFrame({"x": [0, 1], "y": [0, 1]})
    diagonal = (
        alt.Chart(diagonal_data)
        .mark_line(color="gray", strokeDash=[2, 2], opacity=0.5)
        .encode(x="x:Q", y="y:Q")
    )

    chart = (points + regression + diagonal).properties(
        title="Implementation Rate vs Pass-Rate",
        width=400,
        height=300,
    )

    save_figure(chart, "fig26_impl_rate_vs_pass_rate", output_dir, df, render=render)


def fig27_impl_rate_distribution(
    runs_df: pd.DataFrame,
    output_dir: Path,
    render: bool = True,
) -> None:
    """Generate Fig 27: Implementation Rate Distribution by Tier.

    Violin plot showing distribution of Impl-Rate across tiers.

    Args:
        runs_df: Runs DataFrame (must include impl_rate column)
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Check if impl_rate column exists
    if "impl_rate" not in runs_df.columns:
        print("Warning: impl_rate column not found in runs_df, skipping fig27")
        return

    # Filter out NaN values
    df = runs_df[["agent_model", "tier", "impl_rate"]].dropna()

    if len(df) == 0:
        print("Warning: No valid data for fig27")
        return

    # Derive tier order from data
    tier_order = derive_tier_order(runs_df)

    # Get color scale for models
    models = sorted(df["agent_model"].unique())
    domain, range_ = get_color_scale("models", models)

    # Compute dynamic domain for impl_rate axis
    impl_rate_domain = compute_dynamic_domain(df["impl_rate"])

    # Create base layered chart without faceting
    base_violin = (
        alt.Chart(df)
        .transform_density(
            density="impl_rate",
            groupby=["tier", "agent_model"],
            as_=["impl_rate", "density"],
        )
        .mark_area(orient="horizontal", opacity=0.5)
        .encode(
            x=alt.X(
                "density:Q",
                title=None,
                axis=alt.Axis(labels=False, ticks=False, grid=False),
            ),
            y=alt.Y(
                "impl_rate:Q",
                title="Implementation Rate",
                scale=alt.Scale(domain=impl_rate_domain),
            ),
            color=alt.Color(
                "agent_model:N",
                title="Model",
                scale=alt.Scale(domain=domain, range=range_),
            ),
        )
    )

    base_box = (
        alt.Chart(df)
        .mark_boxplot(size=20, opacity=0.7)
        .encode(
            x=alt.X(
                "agent_model:N",
                title="Model",
                axis=alt.Axis(labels=False, ticks=False),
            ),
            y=alt.Y(
                "impl_rate:Q",
                scale=alt.Scale(domain=impl_rate_domain),
            ),
            color=alt.Color(
                "agent_model:N",
                scale=alt.Scale(domain=domain, range=range_),
            ),
        )
    )

    # Layer first, then facet
    chart = (
        (base_violin + base_box)
        .properties(
            title="Implementation Rate Distribution by Tier",
            width=300,
            height=100,
        )
        .facet(
            row=alt.Row(
                "tier:N",
                title="Tier",
                sort=tier_order,
            ),
        )
    )

    save_figure(chart, "fig27_impl_rate_distribution", output_dir, df, render=render)
