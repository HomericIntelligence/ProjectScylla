"""Correlation analysis figures.

Generates Fig 20 (metric correlation heatmap) and Fig 21 (cost vs quality regression).
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd

from scylla.analysis.config import config
from scylla.analysis.figures import get_color_scale
from scylla.analysis.figures.spec_builder import compute_dynamic_domain, save_figure
from scylla.analysis.stats import holm_bonferroni_correction, ols_regression, spearman_correlation


def fig20_metric_correlation_heatmap(
    runs_df: pd.DataFrame, output_dir: Path, render: bool = True
) -> None:
    """Generate Fig 20: Metric Correlation Heatmap.

    Spearman correlation heatmap of score, cost, tokens, duration.
    Annotated with coefficients. Faceted by model.

    Args:
        runs_df: Runs DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Get metrics from centralized config
    metrics = config.correlation_metrics

    # Compute correlations per model
    correlations = []

    for model in sorted(runs_df["agent_model"].unique()):
        model_data = runs_df[runs_df["agent_model"] == model]

        # Compute pairwise Spearman correlations
        for metric1_col, metric1_name in metrics.items():
            for metric2_col, metric2_name in metrics.items():
                if metric1_col not in model_data.columns or metric2_col not in model_data.columns:
                    continue

                data1 = model_data[metric1_col].dropna()
                data2 = model_data[metric2_col].dropna()

                # Align on common indices
                common_idx = data1.index.intersection(data2.index)
                if len(common_idx) < 3:
                    continue

                rho, p_value = spearman_correlation(
                    model_data.loc[common_idx, metric1_col],
                    model_data.loc[common_idx, metric2_col],
                )

                correlations.append(
                    {
                        "agent_model": model,
                        "metric1": metric1_name,
                        "metric2": metric2_name,
                        "rho": rho,
                        "p_value": p_value,
                        "label": f"{rho:.2f}",
                    }
                )

    corr_df = pd.DataFrame(correlations)

    # Apply Holm-Bonferroni correction for multiple comparisons
    if len(corr_df) > 0:
        raw_p_values = corr_df["p_value"].tolist()
        corrected_p_values = holm_bonferroni_correction(raw_p_values)
        corr_df["p_value_corrected"] = corrected_p_values
        # Use corrected p-values for significance testing
        corr_df["significant"] = corr_df["p_value_corrected"] < 0.05
    else:
        corr_df["p_value_corrected"] = []
        corr_df["significant"] = []

    # Create heatmap
    heatmap = (
        alt.Chart(corr_df)
        .mark_rect()
        .encode(
            x=alt.X("metric1:O", title="", sort=list(metrics.values())),
            y=alt.Y("metric2:O", title="", sort=list(metrics.values())),
            color=alt.Color(
                "rho:Q",
                title="Spearman ρ",
                scale=alt.Scale(domain=[-1, 1], scheme="redblue", reverse=True),
            ),
            tooltip=[
                alt.Tooltip("metric1:O", title="Metric 1"),
                alt.Tooltip("metric2:O", title="Metric 2"),
                alt.Tooltip("rho:Q", title="Spearman ρ", format=".3f"),
                alt.Tooltip("p_value:Q", title="p-value", format=".4f"),
            ],
        )
    )

    # Add text labels
    text = (
        alt.Chart(corr_df)
        .mark_text(baseline="middle", fontSize=10)
        .encode(
            x=alt.X("metric1:O", sort=list(metrics.values())),
            y=alt.Y("metric2:O", sort=list(metrics.values())),
            text="label:N",
            color=alt.condition(
                alt.datum.rho > 0 | alt.datum.rho < -0.5,
                alt.value("white"),
                alt.value("black"),
            ),
        )
    )

    # Facet by model if multiple models
    if corr_df["agent_model"].nunique() > 1:
        chart = (
            alt.layer(heatmap, text)
            .facet(column=alt.Column("agent_model:N", title="Agent Model"))
            .properties(title="Metric Correlation Heatmap (Spearman ρ)")
            .configure_view(strokeWidth=0)
        )
    else:
        chart = (
            alt.layer(heatmap, text)
            .properties(title="Metric Correlation Heatmap (Spearman ρ)")
            .configure_view(strokeWidth=0)
        )

    save_figure(chart, "fig20_metric_correlation_heatmap", output_dir, corr_df, render)


def fig21_cost_quality_regression(
    runs_df: pd.DataFrame, output_dir: Path, render: bool = True
) -> None:
    """Generate Fig 21: Cost vs Quality Regression.

    Scatter plot + OLS regression line with R² annotation.
    Cost vs quality at subtest level.

    Args:
        runs_df: Runs DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Aggregate to subtest level (mean cost, mean score)
    subtest_stats = (
        runs_df.groupby(["agent_model", "tier", "subtest"])
        .agg({"cost_usd": "mean", "score": "mean"})
        .reset_index()
    )
    subtest_stats.columns = ["agent_model", "tier", "subtest", "mean_cost", "mean_score"]

    # Compute regression per model
    regressions = []

    for model in sorted(subtest_stats["agent_model"].unique()):
        model_data = subtest_stats[subtest_stats["agent_model"] == model]

        # OLS regression
        result = ols_regression(model_data["mean_cost"], model_data["mean_score"])

        regressions.append(
            {
                "agent_model": model,
                "slope": result["slope"],
                "intercept": result["intercept"],
                "r_squared": result["r_squared"],
                "p_value": result["p_value"],
            }
        )

        # Generate regression line points
        cost_range = model_data["mean_cost"]
        x_min, x_max = cost_range.min(), cost_range.max()

        for x in [x_min, x_max]:
            y = result["slope"] * x + result["intercept"]
            regressions.append(
                {
                    "agent_model": model,
                    "x": x,
                    "y": y,
                    "type": "regression_line",
                }
            )

    reg_df = pd.DataFrame(regressions)

    # Get dynamic color scale for models
    models = sorted(subtest_stats["agent_model"].unique())
    domain, range_ = get_color_scale("models", models)

    # Compute dynamic domain for score axis
    score_domain = compute_dynamic_domain(subtest_stats["mean_score"])

    # Create scatter plot
    scatter = (
        alt.Chart(subtest_stats)
        .mark_circle(size=60, opacity=0.6)
        .encode(
            x=alt.X("mean_cost:Q", title="Mean Cost per Subtest (USD)"),
            y=alt.Y(
                "mean_score:Q", title="Mean Score per Subtest", scale=alt.Scale(domain=score_domain)
            ),
            color=alt.Color(
                "agent_model:N",
                title="Agent Model",
                scale=alt.Scale(domain=domain, range=range_),
            ),
            tooltip=[
                alt.Tooltip("agent_model:N", title="Model"),
                alt.Tooltip("tier:O", title="Tier"),
                alt.Tooltip("subtest:O", title="Subtest"),
                alt.Tooltip("mean_cost:Q", title="Mean Cost", format="$.4f"),
                alt.Tooltip("mean_score:Q", title="Mean Score", format=".3f"),
            ],
        )
    )

    # Add regression lines
    reg_lines_df = reg_df[reg_df["type"] == "regression_line"].copy()

    regression_lines = (
        alt.Chart(reg_lines_df)
        .mark_line(strokeWidth=2)
        .encode(
            x=alt.X("x:Q"),
            y=alt.Y("y:Q"),
            color=alt.Color(
                "agent_model:N",
                scale=alt.Scale(domain=domain, range=range_),
            ),
        )
    )

    # Add R² annotations
    reg_stats_df = reg_df[reg_df["type"].isna()].copy()
    reg_stats_df["annotation"] = reg_stats_df.apply(
        lambda row: f"R² = {row['r_squared']:.3f}, p = {row['p_value']:.4f}", axis=1
    )

    # Position annotations at top-left of chart per model
    annotations = (
        alt.Chart(reg_stats_df)
        .mark_text(align="left", dx=10, dy=10, fontSize=11)
        .encode(
            x=alt.value(10),
            y=alt.value(10),
            text="annotation:N",
            color=alt.Color(
                "agent_model:N",
                scale=alt.Scale(domain=domain, range=range_),
            ),
        )
    )

    # Facet by model if multiple models
    if subtest_stats["agent_model"].nunique() > 1:
        # Need to combine data for layering
        chart = (
            alt.layer(scatter, regression_lines, annotations, data=subtest_stats)
            .facet(row=alt.Row("agent_model:N", title="Agent Model"))
            .properties(title="Cost vs Quality Regression (Subtest Level)")
            .configure_view(strokeWidth=0)
        )
    else:
        chart = (
            alt.layer(scatter, regression_lines, annotations)
            .properties(title="Cost vs Quality Regression (Subtest Level)")
            .configure_view(strokeWidth=0)
        )

    save_figure(chart, "fig21_cost_quality_regression", output_dir, subtest_stats, render)
