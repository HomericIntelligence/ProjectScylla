"""Token distribution analysis figure.

Generates Fig 7 (token distribution stacked bars).
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd

from scylla.analysis.figures import TIER_ORDER
from scylla.analysis.figures.spec_builder import save_figure


def fig07_token_distribution(runs_df: pd.DataFrame, output_dir: Path, render: bool = True) -> None:
    """Generate Fig 7: Token Distribution by Tier.

    Stacked bar chart showing token breakdown by type.

    Args:
        runs_df: Runs DataFrame
        output_dir: Output directory
        render: Whether to render to PNG/PDF

    """
    # Aggregate tokens by (agent_model, tier)
    token_cols = ["input_tokens", "output_tokens", "cache_creation_tokens", "cache_read_tokens"]
    # Removed: using TIER_ORDER from figures module

    token_agg = runs_df.groupby(["agent_model", "tier"])[token_cols].mean().reset_index()

    # Reshape to long format for stacking
    token_long = token_agg.melt(
        id_vars=["agent_model", "tier"],
        value_vars=token_cols,
        var_name="token_type",
        value_name="tokens",
    )

    # Define token type labels
    token_type_labels = {
        "input_tokens": "Input (Fresh)",
        "cache_read_tokens": "Input (Cached)",
        "output_tokens": "Output",
        "cache_creation_tokens": "Cache Creation",
    }
    token_long["token_type_label"] = token_long["token_type"].map(token_type_labels)

    # Add sorting order column
    token_type_sort_order = {
        "input_tokens": 0,
        "cache_read_tokens": 1,
        "output_tokens": 2,
        "cache_creation_tokens": 3,
    }
    token_long["token_type_order"] = token_long["token_type"].map(token_type_sort_order)

    # Define colors for token types
    token_colors = {
        "Input (Fresh)": "#4C78A8",
        "Input (Cached)": "#72B7B2",
        "Output": "#E45756",
        "Cache Creation": "#F58518",
    }

    # Create stacked bar chart
    chart = (
        alt.Chart(token_long)
        .mark_bar()
        .encode(
            x=alt.X("tier:O", title="Tier", sort=TIER_ORDER),
            y=alt.Y("tokens:Q", title="Mean Tokens per Run"),
            color=alt.Color(
                "token_type_label:N",
                title="Token Type",
                scale=alt.Scale(
                    domain=list(token_colors.keys()),
                    range=list(token_colors.values()),
                ),
            ),
            order=alt.Order("token_type_order:Q"),  # Use numeric order
            tooltip=[
                alt.Tooltip("tier:O", title="Tier"),
                alt.Tooltip("token_type_label:N", title="Token Type"),
                alt.Tooltip("tokens:Q", title="Mean Tokens", format=",d"),
            ],
        )
        .facet(column=alt.Column("agent_model:N", title=None))
        .properties(title="Token Distribution by Tier")
    )

    save_figure(chart, "fig07_token_distribution", output_dir, token_long, render)
