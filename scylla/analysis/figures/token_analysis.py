"""Token distribution analysis figure.

Generates Fig 7 (token distribution stacked bars).
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd

from scylla.analysis.figures import derive_tier_order, get_color_scale
from scylla.analysis.figures.spec_builder import save_figure


def fig07_token_distribution(runs_df: pd.DataFrame, output_dir: Path, render: bool = True) -> None:
    """Generate Fig 7: Token Distribution by Tier.

    Stacked bar chart showing token breakdown by type using normalized percentages.

    **Note on T4/T6 Fresh Input Tokens**: Higher-tier architectures (T4, T6) show minimal
    or invisible "Input (Fresh)" tokens due to extreme cache efficiency. For example:
    - T4: ~23 fresh tokens vs ~92K cached tokens (0.02% fresh)
    - T6: ~29 fresh tokens vs ~219K cached tokens (0.01% fresh)

    This is expected behavior demonstrating that hierarchical/super-tier architectures
    maximize prompt caching, with nearly all input coming from cache rather than fresh
    parsing. The tooltip still shows absolute token counts for precise comparison.

    Args:
        runs_df: Runs DataFrame with token columns (input_tokens, output_tokens,
                 cache_creation_tokens, cache_read_tokens)
        output_dir: Output directory for figure files
        render: Whether to render to PNG/PDF (default: True)

    """
    # Aggregate tokens by (agent_model, tier)
    token_cols = ["input_tokens", "output_tokens", "cache_creation_tokens", "cache_read_tokens"]

    token_agg = runs_df.groupby(["agent_model", "tier"])[token_cols].mean().reset_index()

    # Derive tier order from data
    tier_order = derive_tier_order(token_agg)

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

    # Get colors for token types from centralized palette
    token_type_labels = ["Input (Fresh)", "Input (Cached)", "Output", "Cache Creation"]
    domain, range_ = get_color_scale("token_types", token_type_labels)

    # Create stacked bar chart with normalized percentages
    # NOTE: stack="normalize" causes very small token counts to become invisible.
    # This is expected for T4/T6 fresh input tokens (~0.01-0.02% of total).
    # The tooltip preserves absolute counts for detailed inspection.
    chart = (
        alt.Chart(token_long)
        .mark_bar()
        .encode(
            x=alt.X("tier:O", title="Tier", sort=tier_order),
            y=alt.Y("tokens:Q", title="Token Distribution (%)", stack="normalize"),
            color=alt.Color(
                "token_type_label:N",
                title="Token Type",
                scale=alt.Scale(domain=domain, range=range_),
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

    save_figure(chart, "fig07_token_distribution", output_dir, render)
