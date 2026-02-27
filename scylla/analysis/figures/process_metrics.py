"""Process metrics figures.

Generates Fig_RProg (R_Prog by tier), Fig_CFP (CFP by tier),
and Fig_PRRevert (PR Revert Rate by tier).
"""

from __future__ import annotations

import logging
from pathlib import Path

import altair as alt
import pandas as pd

from scylla.analysis.figures import derive_tier_order, get_color_scale
from scylla.analysis.figures.spec_builder import save_figure

logger = logging.getLogger(__name__)

_MIN_COVERAGE_ROWS = 5


def _filter_process_data(runs_df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Filter runs_df to rows where column is non-null.

    Warns if coverage is very sparse (< _MIN_COVERAGE_ROWS rows).

    Args:
        runs_df: Runs DataFrame
        column: Column name to filter on

    Returns:
        Filtered DataFrame with non-null values for column

    """
    filtered = runs_df.dropna(subset=[column])
    if len(filtered) < _MIN_COVERAGE_ROWS:
        logger.warning(
            "Process metric '%s' has only %d non-null rows; figure may be uninformative.",
            column,
            len(filtered),
        )
    return filtered


def fig_r_prog_by_tier(runs_df: pd.DataFrame, output_dir: Path, render: bool = True) -> None:
    """Generate Fig_RProg: Fine-Grained Progress Rate by Tier.

    Box plot showing r_prog distribution per tier, faceted by agent_model.
    Skips gracefully if r_prog column is missing or all-null.

    Args:
        runs_df: Runs DataFrame (must contain 'r_prog', 'tier', 'agent_model' columns)
        output_dir: Output directory for figure files
        render: Whether to render to PNG/PDF (default: True)

    """
    if "r_prog" not in runs_df.columns:
        logger.warning("r_prog column not found in runs_df; skipping fig_r_prog_by_tier")
        return

    data = _filter_process_data(runs_df[["tier", "agent_model", "r_prog"]], "r_prog")
    if data.empty:
        logger.warning("No r_prog data available; skipping fig_r_prog_by_tier")
        return

    tier_order = derive_tier_order(data)
    models = sorted(data["agent_model"].unique())
    domain, range_ = get_color_scale("models", models)

    chart = (
        alt.Chart(data)
        .mark_boxplot()
        .encode(
            x=alt.X("tier:N", sort=tier_order, title="Tier"),
            y=alt.Y("r_prog:Q", scale=alt.Scale(domain=[0, 1]), title="R_Prog"),
            color=alt.Color(
                "agent_model:N",
                scale=alt.Scale(domain=domain, range=range_),
                title="Model",
            ),
        )
        .facet(
            column=alt.Column("agent_model:N", title="Model"),
        )
        .properties(title="Fine-Grained Progress Rate (R_Prog) by Tier")
    )

    save_figure(chart, "fig_r_prog_by_tier", output_dir, render)


def fig_cfp_by_tier(runs_df: pd.DataFrame, output_dir: Path, render: bool = True) -> None:
    """Generate Fig_CFP: Change Fail Percentage by Tier.

    Bar chart of mean CFP per tier with error bars, faceted by agent_model.
    Skips gracefully if cfp column is missing or all-null.

    Args:
        runs_df: Runs DataFrame (must contain 'cfp', 'tier', 'agent_model' columns)
        output_dir: Output directory for figure files
        render: Whether to render to PNG/PDF (default: True)

    """
    if "cfp" not in runs_df.columns:
        logger.warning("cfp column not found in runs_df; skipping fig_cfp_by_tier")
        return

    data = _filter_process_data(runs_df[["tier", "agent_model", "cfp"]], "cfp")
    if data.empty:
        logger.warning("No cfp data available; skipping fig_cfp_by_tier")
        return

    tier_order = derive_tier_order(data)
    models = sorted(data["agent_model"].unique())
    domain, range_ = get_color_scale("models", models)

    # Mean bars
    bars = (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=alt.X("tier:N", sort=tier_order, title="Tier"),
            y=alt.Y("mean(cfp):Q", scale=alt.Scale(domain=[0, 1]), title="Mean CFP"),
            color=alt.Color(
                "agent_model:N",
                scale=alt.Scale(domain=domain, range=range_),
                title="Model",
            ),
            tooltip=[
                alt.Tooltip("tier:N", title="Tier"),
                alt.Tooltip("mean(cfp):Q", title="Mean CFP", format=".3f"),
            ],
        )
    )

    # Error bars (95% CI via stderr)
    error_bars = (
        alt.Chart(data)
        .mark_errorbar(extent="stderr")
        .encode(
            x=alt.X("tier:N", sort=tier_order),
            y=alt.Y("cfp:Q"),
        )
    )

    chart = (
        alt.layer(bars, error_bars)
        .facet(column=alt.Column("agent_model:N", title="Model"))
        .properties(title="Change Fail Percentage (CFP) by Tier")
    )

    save_figure(chart, "fig_cfp_by_tier", output_dir, render)


def fig_pr_revert_by_tier(runs_df: pd.DataFrame, output_dir: Path, render: bool = True) -> None:
    """Generate Fig_PRRevert: PR Revert Rate by Tier.

    Bar chart of mean PR revert rate per tier with error bars, faceted by agent_model.
    Skips gracefully if pr_revert_rate column is missing or all-null.

    Args:
        runs_df: Runs DataFrame (must contain 'pr_revert_rate', 'tier', 'agent_model' columns)
        output_dir: Output directory for figure files
        render: Whether to render to PNG/PDF (default: True)

    """
    if "pr_revert_rate" not in runs_df.columns:
        logger.warning("pr_revert_rate column not found in runs_df; skipping fig_pr_revert_by_tier")
        return

    data = _filter_process_data(
        runs_df[["tier", "agent_model", "pr_revert_rate"]], "pr_revert_rate"
    )
    if data.empty:
        logger.warning("No pr_revert_rate data available; skipping fig_pr_revert_by_tier")
        return

    tier_order = derive_tier_order(data)
    models = sorted(data["agent_model"].unique())
    domain, range_ = get_color_scale("models", models)

    # Mean bars
    bars = (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=alt.X("tier:N", sort=tier_order, title="Tier"),
            y=alt.Y(
                "mean(pr_revert_rate):Q",
                scale=alt.Scale(domain=[0, 1]),
                title="Mean PR Revert Rate",
            ),
            color=alt.Color(
                "agent_model:N",
                scale=alt.Scale(domain=domain, range=range_),
                title="Model",
            ),
            tooltip=[
                alt.Tooltip("tier:N", title="Tier"),
                alt.Tooltip("mean(pr_revert_rate):Q", title="Mean PR Revert Rate", format=".3f"),
            ],
        )
    )

    # Error bars (95% CI via stderr)
    error_bars = (
        alt.Chart(data)
        .mark_errorbar(extent="stderr")
        .encode(
            x=alt.X("tier:N", sort=tier_order),
            y=alt.Y("pr_revert_rate:Q"),
        )
    )

    chart = (
        alt.layer(bars, error_bars)
        .facet(column=alt.Column("agent_model:N", title="Model"))
        .properties(title="PR Revert Rate by Tier")
    )

    save_figure(chart, "fig_pr_revert_by_tier", output_dir, render)
