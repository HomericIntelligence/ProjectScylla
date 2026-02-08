"""Effect size analysis figures.

Generates Fig 19 (effect size forest plot with confidence intervals).
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd

from scylla.analysis.figures import derive_tier_order
from scylla.analysis.figures.spec_builder import save_figure
from scylla.analysis.stats import cliffs_delta_ci


def fig19_effect_size_forest(runs_df: pd.DataFrame, output_dir: Path, render: bool = True) -> None:
    """Generate Fig 19: Effect Size Forest Plot.

    Horizontal dot plot with error bars showing Cliff's delta + 95% CI
    for each tier transition. Vertical dashed line at delta=0.
    Color indicates significance.

    Args:
        runs_df: Runs DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Derive tier order from data
    tier_order = derive_tier_order(runs_df)

    # Compute effect sizes for consecutive tier transitions
    effect_sizes = []

    for model in sorted(runs_df["agent_model"].unique()):
        model_runs = runs_df[runs_df["agent_model"] == model]

        for i in range(len(tier_order) - 1):
            tier1, tier2 = tier_order[i], tier_order[i + 1]
            tier1_data = model_runs[model_runs["tier"] == tier1]
            tier2_data = model_runs[model_runs["tier"] == tier2]

            if len(tier1_data) == 0 or len(tier2_data) == 0:
                continue

            # Cliff's delta with 95% CI
            delta, ci_low, ci_high = cliffs_delta_ci(
                tier2_data["passed"].astype(int),
                tier1_data["passed"].astype(int),
                confidence=0.95,
                n_resamples=10000,
            )

            # Determine significance (CI excludes zero)
            is_significant = not (ci_low <= 0 <= ci_high)

            effect_sizes.append(
                {
                    "agent_model": model,
                    "transition": f"{tier1}→{tier2}",
                    "tier1": tier1,
                    "tier2": tier2,
                    "delta": delta,
                    "ci_low": ci_low,
                    "ci_high": ci_high,
                    "significant": "Yes" if is_significant else "No",
                }
            )

    effect_df = pd.DataFrame(effect_sizes)

    # Get dynamic color scale for significance
    sig_domain = ["No", "Yes"]
    sig_range = ["#999999", "#d62728"]  # Gray for non-sig, red for significant

    # Create base points for effect sizes
    points = (
        alt.Chart(effect_df)
        .mark_circle(size=100)
        .encode(
            y=alt.Y("transition:O", title="Tier Transition", sort=None),
            x=alt.X(
                "delta:Q", title="Cliff's Delta (Effect Size)", scale=alt.Scale(domain=[-1, 1])
            ),
            color=alt.Color(
                "significant:N",
                title="Significant?",
                scale=alt.Scale(domain=sig_domain, range=sig_range),
            ),
            tooltip=[
                alt.Tooltip("agent_model:N", title="Model"),
                alt.Tooltip("transition:O", title="Transition"),
                alt.Tooltip("delta:Q", title="Cliff's δ", format=".3f"),
                alt.Tooltip("ci_low:Q", title="95% CI Low", format=".3f"),
                alt.Tooltip("ci_high:Q", title="95% CI High", format=".3f"),
                alt.Tooltip("significant:N", title="Significant"),
            ],
        )
    )

    # Add error bars for confidence intervals
    error_bars = (
        alt.Chart(effect_df)
        .mark_errorbar()
        .encode(
            y=alt.Y("transition:O", sort=None),
            x=alt.X("ci_low:Q"),
            x2=alt.X2("ci_high:Q"),
            color=alt.Color(
                "significant:N",
                scale=alt.Scale(domain=sig_domain, range=sig_range),
            ),
        )
    )

    # Add vertical line at delta=0 (no effect)
    # Facet by model if multiple models
    if effect_df["agent_model"].nunique() > 1:
        # Build zero line data with agent_model facet column
        zero_data = pd.DataFrame(
            [{"agent_model": m, "x": 0} for m in effect_df["agent_model"].unique()]
        )
        zero_line = alt.Chart(zero_data).mark_rule(strokeDash=[5, 5], color="black").encode(x="x:Q")

        chart = (
            alt.layer(zero_line, error_bars, points)
            .facet(row=alt.Row("agent_model:N", title="Agent Model"), data=effect_df)
            .properties(title="Effect Size Forest Plot (Cliff's Delta with 95% CI)")
            .configure_view(strokeWidth=0)
        )
    else:
        zero_line = (
            alt.Chart(pd.DataFrame({"x": [0]}))
            .mark_rule(strokeDash=[5, 5], color="black")
            .encode(x="x:Q")
        )
        chart = (
            alt.layer(zero_line, error_bars, points)
            .properties(title="Effect Size Forest Plot (Cliff's Delta with 95% CI)")
            .configure_view(strokeWidth=0)
        )

    save_figure(chart, "fig19_effect_size_forest", output_dir, render)
